import argparse
import os
import json
import asyncio
import threading
import time
import base64
import RSAEncryption as rsa
import bittensor as bt
import paramiko  # For SSH functionality
from compute.protocol import Allocate  # Allocate is still needed for the actual allocation process
from compute.wandb.wandb import ComputeWandb  # Importing ComputeWandb

VALID_VALIDATOR_HOTKEYS = ["5GmvyePN9aYErXBBhBnxZKGoGk4LKZApE4NkaSzW62CYCYNA"]

class MinerChecker:
    def __init__(self, config):
        self.config = config
        self.metagraph = self.get_metagraph() # Retrieve metagraph state
        self.axons = self.get_miners() # Retrieve the list of axons (miners)
        self.validator_challenge_batch_size = 50
        self.threads = []
        self.wandb = ComputeWandb(config, bt.wallet(config=config), "validator.py") # Added ComputeWandb integration
        self.penalized_hotkeys_checklist = [] # List of dictionaries for penalized miners
        self.allocated_hotkeys = []  # Allocated miners that shouldn't be checked

    def get_metagraph(self):
        """Retrieves the metagraph from subtensor."""
        subtensor = bt.subtensor(config=self.config)
        return subtensor.metagraph(self.config.netuid)

    def get_miners(self):
        """Retrieves a list of miners (axons) from the metagraph."""
        return self.metagraph.axons

    def sync_checklist(self):
        """Batch process miners using threads, and generate a new penalized hotkey list."""
        self.threads = []
        self.penalized_hotkeys_checklist.clear() # Reset the penalized list for each run
        self.metagraph = self.get_metagraph() # Retrieve metagraph state
        self.axons = self.get_miners() # Retrieve the list of axons (miners)

        #Step 1: Fetch allocated hotkeys from wandb with an empty validator list and flag set to False
        self.allocated_hotkeys = self.wandb.get_allocated_hotkeys(VALID_VALIDATOR_HOTKEYS, True) # Get allocated miners
        # Step 2: Create threads for miners that are NOT allocated
        for i in range(0, len(self.axons), self.validator_challenge_batch_size):
            for axon in self.axons[i: i + self.validator_challenge_batch_size]:
                if axon.hotkey in self.allocated_hotkeys:
                    bt.logging.info(f"Skipping allocated miner: {axon.hotkey}")
                    continue  # skip this miner since it's allocated

                thread = threading.Thread(target=self.miner_checking_thread, args=(axon,), name=f"th_miner_checking_request-{axon.hotkey}", daemon=True)
                self.threads.append(thread)

        # Start and join all threads
        for thread in self.threads:
            thread.start()
        for thread in self.threads:
            thread.join()

        # Update penalized hotkeys via wandb
        # self.wandb.update_penalized_hotkeys_checklist(self.penalized_hotkeys_checklist)
        self.write_penalized_hotkeys_to_file()

        bt.logging.info(f"Length of penalized hotkeys checklist: {len(self.penalized_hotkeys_checklist)}")

    def write_penalized_hotkeys_to_file(self, file_path="penalized_hotkeys.json"):
        """Writes the penalized hotkeys checklist to a file on the disk."""
        try:
            with open(file_path, 'w') as file:
                json.dump(self.penalized_hotkeys_checklist, file, indent=4)
                bt.logging.info(f"Penalized hotkeys written to {file_path}")
        except Exception as e:
            bt.logging.error(f"Error writing penalized hotkeys to file: {e}")

    def penalize_miner(self, hotkey, status_code, description):
        """Adds a miner to the penalized list if it's not already penalized."""
        if not any(p['hotkey'] == hotkey for p in self.penalized_hotkeys_checklist):
            self.penalized_hotkeys_checklist.append({ "hotkey": hotkey, "status_code": status_code, "description": description})
            bt.logging.info(f"Penalized miner {hotkey}: {status_code} - {description}")
        else:
            bt.logging.info(f"Miner {hotkey} already penalized, skipping.")


    async def miner_checking_thread(self, axon):
        """Handles allocation, SSH access, and deallocation of a miner."""
        wallet = bt.wallet(config=self.config)
        dendrite = bt.dendrite(wallet=wallet)
        bt.logging.info(f"Quering for miner: {axon.hotkey}")

        is_ssh_access = True
        allocation_status = False
        private_key, public_key = rsa.generate_key_pair()

        device_requirement = {"cpu": {"count": 1}, "gpu": {}, "hard_disk": {"capacity": 1073741824}, "ram": {"capacity": 1073741824}, "testing": True}

        try:
            check_allocation = await dendrite(axon, Allocate(timeline=30, device_requirement=device_requirement, checking=True,), timeout=30)

            if check_allocation and check_allocation["status"] is True:
                bt.logging.info(f"Successfully passed allocaton check: miner {axon.hotkey}")
                # Simulate an allocation query with Allocate
                response = await dendrite(axon, Allocate(timeline=1, device_requirement=device_requirement, checking=False, public_key=public_key), timeout=60)
                if response and response["status"] is True:
                    allocation_status = True
                    bt.logging.info(f"Successfully allocated miner {axon.hotkey}")
                    private_key = private_key.encode("utf-8")
                    decrypted_info_str = rsa.decrypt_data(private_key, base64.b64decode(response["info"]))
                    info = json.loads(decrypted_info_str)
                    # Use the SSH check function
                    is_ssh_access = self.check_ssh_login(axon.ip, info['port'], info['username'], info['password'])
                else:
                    # Penalize if the allocation failed
                    self.penalize_miner(axon.hotkey, "ALLOCATION_FAILED", "Allocation failed during resource allocation")
            else:
                # Penalize if the allocation failed
                self.penalize_miner(axon.hotkey, "ALLOCATION_FAILED", "Allocation check failed: not reachable/running container")
        except Exception as e:
            bt.logging.error(f"Error during allocation for {axon.hotkey}: {e}")
            self.penalize_miner(axon.hotkey, "ALLOCATION_ERROR", f"Error during allocation: {str(e)}")

        # Deallocate resources if allocated, with a max retry count of 3
        retry_count = 0
        max_retries = 3
        while allocation_status and retry_count < max_retries:
            try:
                # Deallocation query
                deregister_response = await dendrite.query(axon, Allocate(timeline=0, checking=False, public_key=public_key), timeout=60)
                if deregister_response and deregister_response["status"] is True:
                    allocation_status = False
                    bt.logging.info(f"Deallocated miner {axon.hotkey}")
                    break
                else:
                    retry_count += 1
                    bt.logging.error(f"Failed to deallocate miner {axon.hotkey} (attempt {retry_count}/{max_retries})")
                    if retry_count >= max_retries:
                        bt.logging.error(f"Max retries reached for deallocating miner {axon.hotkey}.")
                        self.penalize_miner(axon.hotkey, "DEALLOCATION_FAILED", "Failed to deallocate after max retries")
                    time.sleep(5)
            except Exception as e:
                retry_count += 1
                bt.logging.error(f"Error while trying to deallocate miner {axon.hotkey} (attempt {retry_count}/{max_retries}): {e}")
                if retry_count >= max_retries:
                    bt.logging.error(f"Max retries reached for deallocating miner {axon.hotkey}.")
                    self.penalize_miner(axon.hotkey, "DEALLOCATION_FAILED", "Failed to deallocate after max retries")
                time.sleep(5)

        if not is_ssh_access:
            # Penalize if SSH access fails
            self.penalize_miner(axon.hotkey, "SSH_ACCESS_DISABLED", "Failed SSH access")

    def check_ssh_login(self, host, port, username, password):
        """Check SSH login using Paramiko."""
        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(hostname=host, port=port, username=username, password=password, timeout=10)
            bt.logging.info(f"SSH login successful for {host}")
            return True
        except paramiko.AuthenticationException:
            bt.logging.error(f"Authentication failed for {host}")
            return False
        except paramiko.SSHException as ssh_exception:
            bt.logging.error(f"Unable to establish SSH connection: {ssh_exception}")
            return False
        except Exception as e:
            bt.logging.error(f"Exception in connecting to the server: {e}")
            return False
        finally:
            ssh_client.close()

def get_config():
    """Set up configuration using argparse."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--netuid", type=int, default=1, help="The chain subnet uid.")
    bt.subtensor.add_args(parser)
    bt.logging.add_args(parser)
    bt.wallet.add_args(parser)
    config = bt.config(parser)
    # Ensure the logging directory exists
    config.full_path = os.path.expanduser( "{}/{}/{}/netuid{}/{}".format( config.logging.logging_dir, config.wallet.name, config.wallet.hotkey, config.netuid, "validator",))
    return config

def main():
    """Main function to run the miner checker loop."""
    config = get_config()
    miner_checker = MinerChecker(config)

    while True:
        miner_checker.sync_checklist()
        bt.logging.info("Sleeping before next loop...")
        time.sleep(900) # Sleep for 10 minutes before re-checking miners

if __name__ == "__main__":
    main()