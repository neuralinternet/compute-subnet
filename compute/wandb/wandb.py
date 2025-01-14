import bittensor as bt
import wandb
import pathlib
import os
import hashlib
import json
from collections import Counter

from dotenv import load_dotenv
from compute.utils.db import ComputeDb
from neurons.Validator.database.pog import retrieve_stats, write_stats
from neurons.Validator.script import get_perf_info

PUBLIC_WANDB_NAME = "opencompute"
PUBLIC_WANDB_ENTITY = "neuralinternet"


class ComputeWandb:
    run = None

    def __init__(self, config: bt.config, wallet: bt.wallet, role: str):
        self.config = config.copy()

        keys_to_delete = ["logging", "wallet", "full_path", "axon"]
        for key in keys_to_delete:
            if key in self.config:
                del self.config[key]

        self.wallet = wallet
        self.hotkey = wallet.hotkey.ss58_address
        self.role = os.path.splitext(role)[0]
        self.entity = PUBLIC_WANDB_ENTITY

        # ComputeDB to store run_id
        self.db = ComputeDb()

        # Check wandb API key
        load_dotenv()
        netrc_path = pathlib.Path.home() / ".netrc"
        wandb_api_key = os.getenv("WANDB_API_KEY")

        if not wandb_api_key and not netrc_path.exists():
            raise ValueError("Please log in to wandb using `wandb login` or set the WANDB_API_KEY environment variable.")
        
        self.api = wandb.Api()
        self.project = self.api.project(PUBLIC_WANDB_NAME, entity=PUBLIC_WANDB_ENTITY)
        self.project_run_id = f"{self.entity}/{self.project.name}"
        self.run_name = f"{self.role}-{self.hotkey}"

        # Try to get an existing run_id for the hotkey
        self.run_id = self.get_run_id(self.hotkey)
        try:
            if self.run_id is None:
                filter_rule = {
                    "$and": [
                        {"config.config.netuid": self.config.netuid},
                        {"display_name": self.run_name},
                    ]
                }
                # Get all runs with the run_name
                runs = self.api.runs(f"{PUBLIC_WANDB_ENTITY}/{PUBLIC_WANDB_NAME}", filters=filter_rule)
                # Get the latest run and init from the found run on wandb
                if len(runs)>=1:
                    latest_run = runs[0]
                    self.run_id = latest_run.id
                    # Store the new run_id in the database
                    self.save_run_id(self.hotkey, self.run_id)
                    # Remove the unused run_id from the database
                    if len(runs) > 1:
                        for run in runs:
                            if run.id != self.run_id and run.state != "running":
                                run.delete(delete_artifacts=(True))
                    wandb.finish()
                # run can't be found on wandb either, so initialize a new run
                elif len(runs)==0:
                    # No existing run_id, so initialize a new run
                    run = wandb.init(project=self.project.name, entity=self.entity, name=self.run_name)
                    self.run_id = run.id
                    # Store the new run_id in the database
                    self.save_run_id(self.hotkey, self.run_id)
                    wandb.finish()

            self.run = wandb.init(project=self.project.name, entity=self.entity, id=self.run_id, resume="allow")
        except Exception as e:
            bt.logging.warning(f"wandb init failed: {e}")

        self.update_config()

    def update_config(self):
        if self.run:
            self.run.name = self.run_name

            update_dict = {
                "hotkey": self.hotkey,
                "role": self.role,
                "config": self.config
            }
            self.run.config.update(update_dict, allow_val_change=True)
            # wandb.log({"dummy_metric": 0})

            # Sign the run to ensure it's from the correct hotkey
            self.sign_run()

        else:
            bt.logging.warning(f"wandb init failed, update config not possible.")

    def save_run_id(self, hotkey, run_id):
        cursor = self.db.get_cursor()
        try:
            # Check if the hotkey already exists in the database
            cursor.execute("SELECT run_id FROM wandb_runs WHERE hotkey = ?", (hotkey,))
            result = cursor.fetchone()
            if result is None:
                # If the hotkey does not exist, insert the new run_id
                cursor.execute("INSERT INTO wandb_runs (hotkey, run_id) VALUES (?, ?)", (hotkey, run_id))
                self.db.conn.commit()
            else:
                # If the hotkey exists, log a message and do not update the run_id
                bt.logging.info(f"Hotkey {hotkey} already exists in the wandb. Run ID not updated.")
        except Exception as e:
            self.db.conn.rollback()
            bt.logging.error(f"ComputeDb error: {e}")
        finally:
            cursor.close()

    def get_run_id(self, hotkey):
        cursor = self.db.get_cursor()
        try:
            cursor.execute("SELECT run_id FROM wandb_runs WHERE hotkey = ?", (hotkey,))
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            bt.logging.error(f"ComputeDb error: {e}")
            return None
        finally:
            cursor.close()

    def update_specs(self):
        """
        You can fake these information. Do it at your own risk.
        The validators will send the number of challenges accordingly to the specifications provided here.
        So if you fake something you'll end with a very degraded score :clown:.
        Also, when your miner is allocated, the allocated user can give back a mark of reliability.
        The smaller reliability is, the faster you'll be dereg.
        """
        if self.run:
            update_dict = {
                "specs": get_perf_info(encrypted=False),
            }
            self.run.config.update(update_dict, allow_val_change=True)
            
            # Sign the run
            self.sign_run()

            bt.logging.info(f"✅ Hardware details uploaded to Wandb.")
        else:
            bt.logging.warning(f"wandb init failed, update specs not possible.")

    def log_chain_data(self, data):
        if self.run:
            self.run.log(data)
            bt.logging.info(f"✅ Logging chain data to Wandb.")
        else:
            bt.logging.warning(f"wandb init failed, logging not possible.")

    def update_allocated(self, allocated):
        """
        This function update the allocated value on miner side.
        It's useless to fake this information because its only used as public purpose.
        Not used by the validators to calculate your steak :meat:.
        allocated: hotkey of the validator allocating
        """
        if self.run:
            update_dict = {
                "allocated": allocated
            }
            self.run.config.update(update_dict, allow_val_change=True)

            # Sign the run
            self.sign_run()
        else:
            bt.logging.warning(f"wandb init failed, update allocated not possible.")

    def update_stats(self, stats: dict):
        """
        This function updates the challenge stats for all miners on validator side.
        It's useless to alter this information as it's only used for data analysis.
        Not used by the validators to calculate your steak :meat:.
        """
        if self.run:
            self.run.log({"stats": stats})
            bt.logging.info(f"✅ Logging stats to Wandb.")
        else:
            bt.logging.warning(f"wandb init failed, logging stats not possible.")

    def update_allocated_hotkeys(self, hotkey_list):
        """
        This function updates the allocated hotkeys on the validator side and syncs the allocation with the database.
        """
        self.api.flush()

        # Retrieve current stats from the database
        stats = retrieve_stats(self.db)

        # Update the `allocated` field in stats based on `hotkey_list`
        for uid, data in stats.items():
            hotkey = data.get("hotkey")
            if hotkey in hotkey_list:
                data["allocated"] = True  # Mark as allocated if the hotkey is in the list
            else:
                data["allocated"] = False  # Mark as not allocated if the hotkey is not in the list

        # Write the updated stats back to the database
        write_stats(self.db, stats)

        # Prepare the update dictionary for the configuration
        update_dict = {
            "allocated_hotkeys": hotkey_list,  # Update allocated hotkeys
            "stats": stats  # Updated stats with allocation status
        }
        self.run.config.update(update_dict, allow_val_change=True)

        # Log the allocated hotkeys for tracking
        self.run.log({"allocated_hotkeys": self.run.config["allocated_hotkeys"]})

        # Sign the run
        self.sign_run()


    def update_penalized_hotkeys_checklist(self, hotkey_list):
        """
        This function updates the penalized hotkeys checklist on validator side.
        It's useless to alter this information as it needs to be signed by a valid validator hotkey.
        """
        self.api.flush()

        # Update the configuration with the new keys
        update_dict = {
                "penalized_hotkeys_checklist": hotkey_list
            }
        self.run.config.update(update_dict, allow_val_change=True)

        # Track penalized hotkeys checklist over time
        self.run.log({"penalized_hotkeys_checklist": self.run.config["penalized_hotkeys_checklist"]})

        # Sign the run
        self.sign_run()

    def update_penalized_hotkeys(self, hotkey_list):
        """
        This function updates the allocated hotkeys on validator side.
        It's useless to alter this information as it needs to be signed by a valid validator hotkey.
        """
        self.api.flush()

        # Update the configuration with the new keys
        update_dict = {
                "penalized_hotkeys": hotkey_list
            }
        self.run.config.update(update_dict, allow_val_change=True)

        # Track allocated hotkeys over time
        self.run.log({"penalized_hotkeys": self.run.config["penalized_hotkeys"]})

        # Sign the run
        self.sign_run()
        
    def update_miner_port_open(self, is_port_open):
        """
        This function updates the port on miner side.
        It's useless to alter this information as it needs to be signed by a valid miner hotkey.
        """
        if self.run:
            update_dict = {
                "is_port_open": is_port_open,
            }
            self.run.config.update(update_dict, allow_val_change=True)

            # Track is_port_open
            self.run.log({"is_port_open": self.run.config["is_port_open"]})
            
            # Sign the run
            self.sign_run()

            bt.logging.info(f"✅ Miner's server port uploaded to Wandb.")
        else:
            bt.logging.warning(f"wandb init failed, update port not possible.")

    def get_allocated_hotkeys(self, valid_validator_hotkeys, flag):
        """
        This function gets all allocated hotkeys from all validators.
        Only relevant for validators.
        """
        # Query all runs in the project and Filter runs where the role is 'validator'
        self.api.flush()
        validator_runs = self.api.runs(path=f"{PUBLIC_WANDB_ENTITY}/{PUBLIC_WANDB_NAME}",
                                       filters={"$and": [{"config.role": "validator"},
                                                         {"config.config.netuid": self.config.netuid},
                                                         {"config.allocated_hotkeys": {"$exists": True}},]
                                                })

         # Check if the runs list is empty
        if not validator_runs:
            bt.logging.info("No validator info found in the project opencompute.")
            return []

        # Initialize an empty list to store allocated keys from runs with a valid signature
        allocated_keys_list = []

        # Verify the signature for each validator run
        for run in validator_runs:
            try:
                # Access the run's configuration
                run_config = run.config
                hotkey = run_config.get('hotkey')
                allocated_keys = run_config.get('allocated_hotkeys')

                valid_validator_hotkey = hotkey in valid_validator_hotkeys
                
                # Allow all validator hotkeys for data retrieval only if flag == false
                if not flag:
                    valid_validator_hotkey = True

                if self.verify_run(run) and allocated_keys and valid_validator_hotkey:
                            allocated_keys_list.extend(allocated_keys)  # Add the keys to the list

            except Exception as e:
                bt.logging.info(f"Run ID: {run.id}, Name: {run.name}, Error: {e}")

        return allocated_keys_list

    def get_stats_allocated(self, valid_validator_hotkeys, flag):
        """
        Aggregates stats from all validator runs on wandb, returning a dict keyed by UID.
        Only includes entries where 'own_score' == True (and optionally 'allocated' == True).
        Then picks one 'dominant' entry per UID and preserves all fields (e.g., allocated).
        """

        # Query all validator runs
        self.api.flush()
        validator_runs = self.api.runs(
            path=f"{PUBLIC_WANDB_ENTITY}/{PUBLIC_WANDB_NAME}",
            filters={
                "$and": [
                    {"config.role": "validator"},
                    {"config.config.netuid": self.config.netuid},
                    {"config.stats": {"$exists": True}},
                ]
            }
        )

        if not validator_runs:
            bt.logging.info("No validator info found in the project opencompute.")
            return {}

        # aggregator[uid] = list of dicts
        aggregator = {}

        for run in validator_runs:
            try:
                run_config = run.config
                hotkey = run_config.get("hotkey")
                stats_data = run_config.get("stats", {})

                valid_validator_hotkey = (hotkey in valid_validator_hotkeys)
                # If flag == False, allow *all* runs for data retrieval
                if not flag:
                    valid_validator_hotkey = True

                # Only accept data if run verified, we have stats, and hotkey is valid
                if self.verify_run(run) and stats_data and valid_validator_hotkey:
                    # Iterate over the stats in that run
                    for uid, data in stats_data.items():
                        # If you also want allocated == True, re-enable that check:
                        # if data.get("own_score") is True and data.get("allocated") is True:
                        if data.get("own_score") is True:
                            aggregator.setdefault(uid, []).append(data)

            except Exception as e:
                bt.logging.info(f"Run ID: {run.id}, Name: {run.name}, Error: {e}")

        # Helper function: pick the single "dominant" dict from valid_entries
        def pick_dominant_dict(valid_entries):
            """
            Groups by (gpu_name, num_gpus, score), finds the combo that appears most often.
            In case of tie, picks the highest score. Returns the original dict.
            """
            combos = []
            for d in valid_entries:
                specs = d.get("gpu_specs", {})
                combo_key = (specs.get("gpu_name"), specs.get("num_gpus"), d.get("score", 0))
                combos.append(combo_key)

            c = Counter(combos)
            if not c:
                # Fallback if everything is zero or something else is wrong
                return max(valid_entries, key=lambda x: x.get('score', 0))

            # Find the top combo
            top_combo, top_count = c.most_common(1)[0][0], c.most_common(1)[0][1]

            # Check for ties and resolve
            all_top_combos = [combo for combo, count in c.items() if count == top_count]
            if len(all_top_combos) == 1:
                chosen_combo = all_top_combos[0]
            else:
                # Tie: pick the one with the highest score
                chosen_combo = max(all_top_combos, key=lambda x: x[2])  # Index 2 is the score

            # Find the original dict in valid_entries matching the chosen combo
            for d in valid_entries:
                specs = d.get("gpu_specs", {})
                triple = (specs.get("gpu_name"), specs.get("num_gpus"), d.get("score", 0))
                if triple == chosen_combo:
                    # Do not overwrite "allocated", keep it as is
                    d["own_score"] = True  # Mark as chosen
                    return d

        final_stats = {}

        for uid, entries in aggregator.items():
            # Filter out zero-score entries if you want
            valid_entries = [d for d in entries if d.get('score', 0) != 0]
            if not valid_entries:
                continue

            # If there's exactly one valid entry, pick it
            if len(valid_entries) == 1:
                valid_entries[0]["own_score"] = True  # Mark as chosen
                final_stats[uid] = valid_entries[0]
            else:
                # Otherwise pick a single "dominant" dict
                chosen_dict = pick_dominant_dict(valid_entries)
                final_stats[uid] = chosen_dict

        # Convert string UIDs to int if needed
        final_stats_int_keys = {}
        for uid_str, data in final_stats.items():
            uid_int = int(uid_str)
            final_stats_int_keys[uid_int] = data

        return final_stats_int_keys

    def get_penalized_hotkeys(self, valid_validator_hotkeys, flag):
        """
        This function gets all allocated hotkeys from all validators.
        Only relevant for validators.
        """
        # Query all runs in the project and Filter runs where the role is 'validator'
        self.api.flush()
        validator_runs = self.api.runs(path=f"{PUBLIC_WANDB_ENTITY}/{PUBLIC_WANDB_NAME}",
                                    filters={"$and": [{"config.role": "validator"},
                                                        {"config.config.netuid": self.config.netuid},
                                                        {"config.penalized_hotkeys": {"$exists": True}},]
                                                })

        # Check if the runs list is empty
        if not validator_runs:
            bt.logging.info("No validator info found in the project opencompute.")
            return []

        # Initialize an empty list to store allocated keys from runs with a valid signature
        penalized_keys_list = []

        # Verify the signature for each validator run
        for run in validator_runs:
            try:
                # Access the run's configuration
                run_config = run.config
                hotkey = run_config.get('hotkey')
                penalized_keys = run_config.get('penalized_hotkeys')

                valid_validator_hotkey = hotkey in valid_validator_hotkeys

                # Allow all validator hotkeys for data retrieval only
                if not flag:
                    valid_validator_hotkey = True

                if self.verify_run(run) and penalized_keys and valid_validator_hotkey:
                            penalized_keys_list.extend(penalized_keys)  # Add the keys to the list

            except Exception as e:
                bt.logging.info(f"Run ID: {run.id}, Name: {run.name}, Error: {e}")

        return penalized_keys_list
    
    def get_penalized_hotkeys_checklist_bak(self, valid_validator_hotkeys, flag):
        """
        This function gets all penalized hotkeys checklist from all validators.
        Only relevant for validators.
        """
        # Query all runs in the project and Filter runs where the role is 'validator'
        self.api.flush()
        validator_runs = self.api.runs(path=f"{PUBLIC_WANDB_ENTITY}/{PUBLIC_WANDB_NAME}",
                                       filters={"$and": [{"config.role": "validator"},
                                                         {"config.config.netuid": self.config.netuid},
                                                         {"config.penalized_hotkeys_checklist": {"$exists": True}},]
                                                })

         # Check if the runs list is empty
        if not validator_runs:
            bt.logging.info("No validator info found in the project opencompute.")
            return []

        # Initialize an empty list to store penalized hotkeys checklist from runs with a valid signature
        all_penalized_hotkeys_checklist = []

        # Verify the signature for each validator run
        for run in validator_runs:
            try:
                # Access the run's configuration
                run_config = run.config
                hotkey = run_config.get('hotkey')
                penalized_hotkeys_checklist = run_config.get('penalized_hotkeys_checklist')

                valid_validator_hotkey = hotkey in valid_validator_hotkeys

                # Allow all validator hotkeys for data retrieval only
                if not flag:
                    valid_validator_hotkey = True

                if self.verify_run(run) and penalized_hotkeys_checklist and valid_validator_hotkey:
                    all_penalized_hotkeys_checklist.extend(penalized_hotkeys_checklist)  # Add the keys to the list

            except Exception as e:
                bt.logging.info(f"Run ID: {run.id}, Name: {run.name}, Error: {e}")

        return all_penalized_hotkeys_checklist

    def get_miner_specs(self, queryable_uids):
        """
        This function gets all specs from miners.
        Only relevant for validators.
        """
        # Dictionary to store the (hotkey, specs) from wandb runs
        db_specs_dict = {}

        self.api.flush()
        runs = self.api.runs(f"{PUBLIC_WANDB_ENTITY}/{PUBLIC_WANDB_NAME}",
                            filters={"$and": [{"config.role": "miner"},
                                               {"config.config.netuid": self.config.netuid},
                                               {"state": "running"}]
                                    })
        try:
            # Iterate over all runs in the opencompute project
            for index, run in enumerate(runs, start=1):
                # Access the run's configuration
                run_config = run.config
                hotkey = run_config.get('hotkey')
                specs = run_config.get('specs')
                
                # check the signature
                if self.verify_run(run) and specs:
                    # Add the index and (hotkey, specs) tuple to the db_specs_dict if hotkey is valid
                    valid_hotkeys = [axon.hotkey for axon in queryable_uids.values() if axon.hotkey]
                    if hotkey in valid_hotkeys:
                        db_specs_dict[index] = (hotkey, specs)
                        
        except Exception as e:
            # Handle the exception by logging an error message
            bt.logging.error(f"An error occurred while getting specs from wandb: {e}")
        
        # Return the db_specs_dict for further use or inspection
        return db_specs_dict
    
    def sign_run(self):
        # Include the run ID in the data to be signed
        data_to_sign = self.run_id

        # Compute a SHA-256 hash of the data to be signed
        data_hash = hashlib.sha256(data_to_sign.encode()).digest()

        # Sign the hash with the hotkey
        signature = self.wallet.hotkey.sign(data_hash).hex()
        update_dict = {
                "signature": signature
            }
        self.run.config.update(update_dict, allow_val_change=True)
        self.run.log({"dummy_metric": 0})
        self.api.flush()

    def verify_run(self, run):
        # Access the run's configuration
        run_config = run.config

        # Extract hotkey and signature from the run's summary
        hotkey = run_config.get('hotkey')
        signature = run.config.get('signature')  # Assuming signature is stored in summary
        run_id_str = run.id

        # Recreate the data that was signed
        data_to_sign = run_id_str

        # Compute a SHA-256 hash of the data to be signed
        data_hash = hashlib.sha256(data_to_sign.encode()).digest()

        if hotkey and signature:
            try:
                if bt.Keypair(ss58_address=hotkey).verify(data_hash, bytes.fromhex(signature)):
                    return True
                else:
                    bt.logging.info(f"Run ID: {run_id_str}, Name: {run.name}, Failed Signature: The signature is not valid.")
            except Exception as e:
                bt.logging.info(f"Error verifying signature for Run ID: {run_id_str}, Name: {run.name}: {e}")

        return False

    def sync_allocated(self, hotkey):
        """
        This function syncs the allocated status of the miner with the wandb run.
        """
        # Fetch allocated hotkeys
        allocated_hotkeys = self.get_allocated_hotkeys([], False)

        if hotkey in allocated_hotkeys:
            return True
        else:
            return False

    def get_penalized_hotkeys_checklist(self, valid_validator_hotkeys, flag): 
        """ This function gets penalized hotkeys checklist from a specific hardcoded validator. """
        # Hardcoded run ID
        run_id = "neuralinternet/opencompute/0djlnjjs"
        # Fetch the specific run by its ID
        self.api.flush()
        run = self.api.run(run_id) 
        if not run: 
            bt.logging.info(f"No run info found for ID {run_id}.") 
            return []
        # Access the run's configuration
        try: 
            run_config = run.config  
            penalized_hotkeys_checklist = run_config.get('penalized_hotkeys_checklist')
            return penalized_hotkeys_checklist 
        except Exception as e: 
            bt.logging.info(f"Run ID: {run.id}, Name: {run.name}, Error: {e}") 
            return []
