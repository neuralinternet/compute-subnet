# The MIT License (MIT)
# Copyright © 2023 Crazydevlegend
# Copyright © 2023 Rapiiidooo
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import ast
import asyncio
import base64
import json
import os
import random
import threading
import traceback
import hashlib
from asyncio import AbstractEventLoop
from typing import Dict, Tuple, List

import bittensor as bt
import math
import time

from compute.utils.socket import check_port
import cryptography
import torch
from cryptography.fernet import Fernet
from torch._C._te import Tensor
import RSAEncryption as rsa
from neurons.Validator.script import check_ssh_login

import Validator.app_generator as ag
from Validator.pow import gen_hash, run_validator_pow
from compute import (
    pow_min_difficulty,
    pow_max_difficulty,
    pow_timeout,
    SUSPECTED_EXPLOITERS_HOTKEYS,
    SUSPECTED_EXPLOITERS_COLDKEYS,
    __version_as_int__,
    validator_permit_stake,
    weights_rate_limit,
    specs_timeout,
)
from compute.axon import ComputeSubnetSubtensor
from compute.protocol import Allocate, Challenge, Specs
from compute.utils.db import ComputeDb
from compute.utils.math import percent, force_to_float_or_default
from compute.utils.parser import ComputeArgPaser
from compute.utils.subtensor import is_registered, get_current_block, calculate_next_block_time
from compute.utils.version import try_update, get_local_version, version2number, get_remote_version
from compute.wandb.wandb import ComputeWandb
from neurons.Validator.calculate_pow_score import calc_score
from neurons.Validator.database.allocate import update_miner_details, select_has_docker_miners_hotkey, get_miner_details
from neurons.Validator.database.challenge import select_challenge_stats, update_challenge_details
from neurons.Validator.database.miner import select_miners, purge_miner_entries, update_miners


class Validator:
    blocks_done: set = set()

    pow_requests: dict = {}
    pow_responses: dict = {}
    pow_benchmark: dict = {}
    new_pow_benchmark: dict = {}
    pow_benchmark_success: dict = {}

    queryable_for_specs: dict = {}
    finalized_specs_once: bool = False

    total_current_miners: int = 0

    scores: Tensor
    stats: dict

    validator_subnet_uid: int

    _queryable_uids: Dict[int, bt.AxonInfo]

    loop: AbstractEventLoop

    @property
    def wallet(self) -> bt.wallet:
        return self._wallet

    @property
    def subtensor(self) -> ComputeSubnetSubtensor:
        return self._subtensor

    @property
    def dendrite(self) -> bt.dendrite:
        return self._dendrite

    @property
    def metagraph(self) -> bt.metagraph:
        return self._metagraph

    @property
    def queryable(self):
        return self._queryable_uids

    @property
    def queryable_uids(self):
        return [uid for uid in self._queryable_uids.keys()]

    @property
    def queryable_axons(self):
        return [axon for axon in self._queryable_uids.values()]

    @property
    def queryable_hotkeys(self):
        return [axon.hotkey for axon in self._queryable_uids.values()]

    @property
    def current_block(self):
        return get_current_block(subtensor=self.subtensor)

    @property
    def miners_items_to_set(self):
        return set((uid, hotkey) for uid, hotkey in self.miners.items()) if self.miners else None

    def __init__(self):
        # Step 1: Parse the bittensor and compute subnet config
        self.config = self.init_config()

        # Setup extra args
        self.blacklist_hotkeys = {hotkey for hotkey in self.config.blacklist_hotkeys}
        self.blacklist_coldkeys = {coldkey for coldkey in self.config.blacklist_coldkeys}
        self.whitelist_hotkeys = {hotkey for hotkey in self.config.whitelist_hotkeys}
        self.whitelist_coldkeys = {coldkey for coldkey in self.config.whitelist_coldkeys}
        self.exploiters_hotkeys = {hotkey for hotkey in SUSPECTED_EXPLOITERS_HOTKEYS} if self.config.blacklist_exploiters else {}
        self.exploiters_coldkeys = {coldkey for coldkey in SUSPECTED_EXPLOITERS_COLDKEYS} if self.config.blacklist_exploiters else {}

        # Set custom validator arguments
        self.validator_specs_batch_size = self.config.validator_specs_batch_size
        self.validator_challenge_batch_size = self.config.validator_challenge_batch_size
        self.validator_perform_hardware_query = self.config.validator_perform_hardware_query
        self.validator_whitelist_updated_threshold = self.config.validator_whitelist_updated_threshold

        # Set up logging with the provided configuration and directory.
        bt.logging(config=self.config, logging_dir=self.config.full_path)
        bt.logging.info(f"Running validator for subnet: {self.config.netuid} on network: {self.config.subtensor.chain_endpoint} with config:")
        # Log the configuration for reference.
        bt.logging.info(self.config)

        # Step 2: Build Bittensor validator objects
        # These are core Bittensor classes to interact with the network.
        bt.logging.info("Setting up bittensor objects.")

        # The wallet holds the cryptographic key pairs for the validator.
        self._wallet = bt.wallet(config=self.config)
        bt.logging.info(f"Wallet: {self.wallet}")

        # The subtensor is our connection to the Bittensor blockchain.
        self._subtensor = ComputeSubnetSubtensor(config=self.config)
        bt.logging.info(f"Subtensor: {self.subtensor}")

        # Dendrite is the RPC client; it lets us send messages to other nodes (axons) in the network.
        self._dendrite = bt.dendrite(wallet=self.wallet)
        bt.logging.info(f"Dendrite: {self.dendrite}")

        # The metagraph holds the state of the network, letting us know about other miners.
        self._metagraph = self.subtensor.metagraph(self.config.netuid)
        bt.logging.info(f"Metagraph: {self.metagraph}")

        # Initialize the local db
        self.db = ComputeDb()
        self.miners: dict = select_miners(self.db)

        # Initialize wandb
        self.wandb = ComputeWandb(self.config, self.wallet, os.path.basename(__file__))

        # Step 3: Set up initial scoring weights for validation
        bt.logging.info("Building validation weights.")
        self.uids: list = self.metagraph.uids.tolist()
        self.last_uids: list = self.uids.copy()
        self.init_scores()
        self.sync_status()

        self.last_updated_block = self.current_block - (self.current_block % 100)

        # Initialize allocated_hotkeys as an empty list
        self.allocated_hotkeys = []

        # Initialize penalized_hotkeys as an empty list
        self.penalized_hotkeys = []

        # Init the thread.
        self.lock = threading.Lock()
        self.threads: List[threading.Thread] = []

    @staticmethod
    def init_config():
        """
        This function is responsible for setting up and parsing command-line arguments.
        :return: config
        """
        parser = ComputeArgPaser(description="This script aims to help validators with the compute subnet.")
        config = parser.config

        # Step 3: Set up logging directory
        # Logging is crucial for monitoring and debugging purposes.
        config.full_path = os.path.expanduser(
            "{}/{}/{}/netuid{}/{}".format(
                config.logging.logging_dir,
                config.wallet.name,
                config.wallet.hotkey,
                config.netuid,
                "validator",
            )
        )
        # Ensure the logging directory exists.
        if not os.path.exists(config.full_path):
            os.makedirs(config.full_path, exist_ok=True)

        # Return the parsed config.
        return config

    def init_prometheus(self, force_update: bool = False):
        """
        Register the prometheus information on metagraph.
        :return: bool
        """
        bt.logging.info("Extrinsic prometheus information on metagraph.")
        success = self.subtensor.serve_prometheus(
            wallet=self.wallet,
            port=bt.defaults.axon.port,
            netuid=self.config.netuid,
            force_update=force_update,
        )
        if success:
            bt.logging.success(prefix="Prometheus served", sufix=f"<blue>Current version: {get_local_version()}</blue>")
        else:
            bt.logging.error("Prometheus initialization failed")
        return success

    def init_local(self):
        bt.logging.info(f"🔄 Syncing metagraph with subtensor.")
        self._metagraph = self.subtensor.metagraph(self.config.netuid)
        self.uids = self.metagraph.uids.tolist()

    def init_scores(self):
        self.scores = torch.zeros(len(self.uids), dtype=torch.float32)
        # Set the weights of validators to zero.
        self.scores = self.scores * (self.metagraph.total_stake < 1.024e3)
        # Set the weight to zero for all nodes without assigned IP addresses.
        self.scores = self.scores * torch.Tensor(self.get_valid_tensors(metagraph=self.metagraph))
        bt.logging.info(f"🔢 Initialized scores : {self.scores.tolist()}")
        self.sync_scores()

    @staticmethod
    def pretty_print_dict_values(items: dict):
        for key, values in items.items():
            log = f"uid: {key}"

            for values_key, values_values in values.items():
                if values_key == "ss58_address":
                    values_values = values_values[:8] + (values_values[8:] and "...")
                try:
                    values_values = f"{float(values_values):.2f}"
                except Exception:
                    pass
                log += f" | {values_key}: {values_values}"

            bt.logging.trace(log)

    def sync_scores(self):
        # Fetch scoring stats
        self.stats = select_challenge_stats(self.db)

        valid_validator_hotkeys = self.get_valid_validator_hotkeys()

        # Fetch allocated hotkeys
        self.allocated_hotkeys = self.wandb.get_allocated_hotkeys(valid_validator_hotkeys, True)

        # Fetch penalized hotkeys
        self.penalized_hotkeys = self.wandb.get_penalized_hotkeys(valid_validator_hotkeys, True)

        # Fetch docker requirement
        has_docker_hotkeys = select_has_docker_miners_hotkey(self.db)

        self.pretty_print_dict_values(self.stats)

        self._queryable_uids = self.get_queryable()

        # Calculate score
        for uid in self.uids:
            try:
                axon = self._queryable_uids[uid]
                hotkey = axon.hotkey

                if uid not in self.stats:
                    self.stats[uid] = {}  # Initialize empty dictionary for this UID

                if hotkey in has_docker_hotkeys:
                    self.stats[uid]["has_docker"] = True
                elif not self.finalized_specs_once:
                    self.stats[uid]["has_docker"] = True
                else:
                    self.stats[uid]["has_docker"] = False

                score = calc_score(self.stats[uid], hotkey, self.allocated_hotkeys, self.penalized_hotkeys, valid_validator_hotkeys)
                self.stats[uid]["score"] = score

            except KeyError as e:
                # bt.logging.info(f"KeyError occurred for UID {uid}: {str(e)}")
                score = 0
            except Exception as e:
                # bt.logging.info(f"An unexpected exception occurred for UID {uid}: {str(e)}")
                score = 0

            self.scores[uid] = score

        # Update stats in wandb
        self.wandb.update_stats(self.stats)

        bt.logging.info(f"🔢 Synced scores : {self.scores.tolist()}")

    def sync_local(self):
        """
        Resync our local state with the latest state from the blockchain.
        Sync scores with metagraph.
        Get the current uids of all miners in the network.
        """
        self.metagraph.sync(subtensor=self.subtensor)
        self.uids = self.metagraph.uids.tolist()

    def sync_status(self):
        # Check if the validator is still registered
        self.validator_subnet_uid = is_registered(
            wallet=self.wallet,
            metagraph=self.metagraph,
            subtensor=self.subtensor,
            entity="validator",
        )

        # Check for auto update
        if self.config.auto_update:
            try_update()

        # Check if the validator has the prometheus info updated
        subnet_prometheus_version = self.metagraph.neurons[self.validator_subnet_uid].prometheus_info.version
        current_version = __version_as_int__
        if subnet_prometheus_version != current_version:
            self.init_prometheus(force_update=True)
    def remove_duplicate_penalized_hotkeys(self):
        """
        Removes any duplicate entries in the penalized_hotkeys_checklist
        based on the 'hotkey' field.
        """
        seen = set()
        unique_penalized_list = []

        for item in self.penalized_hotkeys_checklist:
            if item['hotkey'] not in seen:
                unique_penalized_list.append(item)
                seen.add(item['hotkey'])

        self.penalized_hotkeys_checklist = unique_penalized_list
        bt.logging.info("Removed duplicate hotkeys from penalized_hotkeys_checklist.")

    def sync_checklist(self):
        self.threads = []
        self.penalized_hotkeys_checklist = self.wandb.get_penalized_hotkeys_checklist(self.get_valid_validator_hotkeys(), True)
        for i in range(0, len(self.uids), self.validator_challenge_batch_size):
            for _uid in self.uids[i : i + self.validator_challenge_batch_size]:
                try:
                    axon = self._queryable_uids[_uid]
                    self.threads.append(
                        threading.Thread(
                            target=self.execute_miner_checking_request,
                            args=(_uid, axon),
                            name=f"th_execute_miner_checking_request-{_uid}",
                            daemon=True,
                        )
                    )
                except KeyError:
                    continue
        self.remove_duplicate_penalized_hotkeys()

        for thread in self.threads:
            thread.start()

        for thread in self.threads:
            thread.join()

        self.wandb.update_penalized_hotkeys_checklist(self.penalized_hotkeys_checklist)

    def sync_miners_info(self, queryable_tuple_uids_axons: List[Tuple[int, bt.AxonInfo]]):
        if queryable_tuple_uids_axons:
            for uid, axon in queryable_tuple_uids_axons:
                if self.miners_items_to_set and (uid, axon.hotkey) not in self.miners_items_to_set:
                    try:
                        bt.logging.info(f"❌ Miner {uid}-{self.miners[uid]} has been deregistered. Clean up old entries.")
                        purge_miner_entries(self.db, uid, self.miners[uid])
                    except KeyError:
                        pass
                    bt.logging.info(f"✅ Setting up new miner {uid}-{axon.hotkey}.")
                    update_miners(self.db, [(uid, axon.hotkey)]),
                    self.miners[uid] = axon.hotkey
        else:
            bt.logging.warning(f"❌ No queryable miners.")

    def calc_difficulty(self, uid):
        difficulty = pow_min_difficulty
        try:
            stat = self.stats[uid]
            current_difficulty = math.ceil(force_to_float_or_default(stat.get("last_20_difficulty_avg"), default=pow_min_difficulty))
            last_20_challenge_failed = force_to_float_or_default(stat.get("last_20_challenge_failed"))
            challenge_successes = force_to_float_or_default(stat.get("challenge_successes"))

            # Adjust difficulty based on failure rates with more nuanced increments
            if challenge_successes > 4:  # Adjusts the threshold from 20 to 4 for faster response
                failure_rate = last_20_challenge_failed / 20
                if failure_rate < 0.1:
                    difficulty = min(current_difficulty + 2, pow_max_difficulty)
                elif failure_rate < 0.2:
                    difficulty = min(current_difficulty + 1, pow_max_difficulty)
                elif failure_rate > 0.25:
                    difficulty = max(current_difficulty - 1, pow_min_difficulty)
                else:
                    difficulty = current_difficulty
        except KeyError:
            pass
        except Exception as e:
            bt.logging.error(f"{e} => difficulty minimal: {pow_min_difficulty} attributed for {uid}")

        return max(difficulty, pow_min_difficulty)

    @staticmethod
    def filter_axons(queryable_tuple_uids_axons: List[Tuple[int, bt.AxonInfo]]):
        """Filter the axons with uids_list, remove those with the same IP address."""
        # Set to keep track of unique identifiers
        valid_ip_addresses = set()

        # List to store filtered axons
        dict_filtered_axons = {}
        for uid, axon in queryable_tuple_uids_axons:
            ip_address = axon.ip

            if ip_address not in valid_ip_addresses:
                valid_ip_addresses.add(ip_address)
                dict_filtered_axons[uid] = axon

        return dict_filtered_axons

    def filter_axon_version(self, dict_filtered_axons: dict):
        # Get the minimal miner version
        latest_version = version2number(get_remote_version(pattern="__minimal_miner_version__"))
        if percent(len(dict_filtered_axons), self.total_current_miners) <= self.validator_whitelist_updated_threshold:
            bt.logging.info(f"Less than {self.validator_whitelist_updated_threshold}% miners are currently using the last version. Allowing all.")
            return dict_filtered_axons

        dict_filtered_axons_version = {}
        for uid, axon in dict_filtered_axons.items():
            if latest_version and latest_version <= axon.version < 600:
                dict_filtered_axons_version[uid] = axon
        return dict_filtered_axons_version

    def is_blacklisted(self, neuron: bt.NeuronInfoLite):
        coldkey = neuron.coldkey
        hotkey = neuron.hotkey

        # Blacklist coldkeys that are blacklisted by user
        if coldkey in self.blacklist_coldkeys:
            bt.logging.trace(f"Blacklisted recognized coldkey {coldkey} - with hotkey: {hotkey}")
            return True

        # Blacklist coldkeys that are blacklisted by user or by set of hotkeys
        if hotkey in self.blacklist_hotkeys:
            bt.logging.trace(f"Blacklisted recognized hotkey {hotkey}")
            # Add the coldkey attached to this hotkey in the blacklisted coldkeys
            self.blacklist_hotkeys.add(coldkey)
            return True

        # Blacklist coldkeys that are exploiters
        if coldkey in self.exploiters_coldkeys:
            bt.logging.trace(f"Blacklisted exploiter coldkey {coldkey} - with hotkey: {hotkey}")
            return True

        # Blacklist hotkeys that are exploiters
        if hotkey in self.exploiters_hotkeys:
            bt.logging.trace(f"Blacklisted exploiter hotkey {hotkey}")
            # Add the coldkey attached to this hotkey in the blacklisted coldkeys
            self.exploiters_hotkeys.add(coldkey)
            return True

        return False

    def get_valid_tensors(self, metagraph):
        tensors = []
        self.total_current_miners = 0
        for uid in metagraph.uids:
            neuron = metagraph.neurons[uid]

            if neuron.axon_info.ip != "0.0.0.0" and not self.is_blacklisted(neuron=neuron):
                self.total_current_miners += 1
                tensors.append(True)
            else:
                tensors.append(False)

        return tensors

    def get_valid_queryable(self):
        valid_queryable = []
        for uid in self.uids:
            neuron: bt.NeuronInfoLite = self.metagraph.neurons[uid]
            axon = self.metagraph.axons[uid]

            if neuron.axon_info.ip != "0.0.0.0" and self.metagraph.total_stake[uid] < 1.024e3 and not self.is_blacklisted(neuron=neuron):
                valid_queryable.append((uid, axon))

        return valid_queryable

    def get_queryable(self):
        queryable = self.get_valid_queryable()

        # Execute a cleanup of the stats and miner information if the miner has been dereg
        self.sync_miners_info(queryable)

        dict_filtered_axons = self.filter_axons(queryable_tuple_uids_axons=queryable)
        dict_filtered_axons = self.filter_axon_version(dict_filtered_axons=dict_filtered_axons)
        return dict_filtered_axons

    def get_valid_validator_hotkeys(self):
        valid_uids = []
        uids = self.metagraph.uids.tolist()
        for index, uid in enumerate(uids):
            if self.metagraph.total_stake[index] > validator_permit_stake:
                valid_uids.append(uid)
        valid_hotkeys = []
        for uid in valid_uids:
            neuron = self.subtensor.neuron_for_uid(uid, self.config.netuid)
            hotkey = neuron.hotkey
            valid_hotkeys.append(hotkey)
        return valid_hotkeys

    def execute_pow_request(self, uid, axon: bt.AxonInfo, _hash, _salt, mode, chars, mask, difficulty):
        dendrite = bt.dendrite(wallet=self.wallet)
        start_time = time.time()
        bt.logging.info(f"Querying for {Challenge.__name__} - {uid}/{axon.hotkey}/{_hash}/{difficulty}")
        response = dendrite.query(
            axon,
            Challenge(
                challenge_hash=_hash,
                challenge_salt=_salt,
                challenge_mode=mode,
                challenge_chars=chars,
                challenge_mask=mask,
                challenge_difficulty=difficulty,
            ),
            timeout=pow_timeout,
        )
        elapsed_time = time.time() - start_time
        response_password = response.get("password", "")
        hashed_response = gen_hash(response_password, _salt)[0] if response_password else ""
        success = True if _hash == hashed_response else False
        result_data = {
            "ss58_address": axon.hotkey,
            "success": success,
            "elapsed_time": elapsed_time,
            "difficulty": difficulty,
        }
        with self.lock:
            self.pow_responses[uid] = response
            self.new_pow_benchmark[uid] = result_data

    def execute_miner_checking_request(self, uid, axon: bt.AxonInfo):
        dendrite = bt.dendrite(wallet=self.wallet)
        bt.logging.info(f"Querying for {Allocate.__name__} - {uid}/{axon.hotkey}")

        response = dendrite.query(axon, Allocate(timeline=1, checking=True), timeout=30)
        port = response.get("port", "")
        status = response.get("status", False)
        checklist_hotkeys = [item['hotkey'] for item in self.penalized_hotkeys_checklist]
        if port:
            if not status:
                is_port_open = check_port(axon.ip, port)
                if (axon.hotkey not in checklist_hotkeys )and (not is_port_open):
                    self.penalized_hotkeys_checklist.append({"hotkey": axon.hotkey, "status_code": "PORT_CLOSED", "description": "The port of ssh server is closed"})
                    bt.logging.info(
                        f"Debug {Allocate.__name__} - status of Checking allocation - {status} {uid} - Port is closed and not usable, even though it has been allocated."
                    )
                else:
                    bt.logging.info(f"Debug {Allocate.__name__} - status of Checking allocation - {status} {uid} - Port is open and the miner is allocated")
            else:
                is_ssh_access = True
                allocation_status = False
                private_key, public_key = rsa.generate_key_pair()
                device_requirement = {"cpu": {"count": 1}, "gpu": {}, "hard_disk": {"capacity": 1073741824}, "ram": {"capacity": 1073741824}}
                try:
                    response = dendrite.query(axon, Allocate(timeline=1, device_requirement=device_requirement, checking=False, public_key=public_key), timeout=60)
                    if response and response["status"] is True:
                        allocation_status = True
                        bt.logging.info(f"Debug {Allocate.__name__} - Successfully Allocated - {uid}")
                        private_key = private_key.encode("utf-8")
                        decrypted_info_str = rsa.decrypt_data(private_key, base64.b64decode(response["info"]))
                        info = json.loads(decrypted_info_str)
                        is_ssh_access = check_ssh_login(axon.ip, port, info['username'], info['password'])
                except Exception as e:
                    bt.logging.error(f"{e}")
                while True and allocation_status:
                    deregister_response = dendrite.query(axon, Allocate(timeline=0, checking=False, public_key=public_key), timeout=60)
                    if deregister_response and deregister_response["status"] is True:
                        bt.logging.info(f"Debug {Allocate.__name__} - Deallocated - {uid}")
                        break
                    else:
                        bt.logging.error(f"Debug {Allocate.__name__} - Failed to deallocate - {uid} will retry in 5 seconds")
                        time.sleep(5)
                if axon.hotkey in checklist_hotkeys:
                    self.penalized_hotkeys_checklist = [item for item in self.penalized_hotkeys_checklist if item['hotkey'] != axon.hotkey]
                if not is_ssh_access:
                    bt.logging.info(f"Debug {Allocate.__name__} - status of Checking allocation - {status} {uid} - SSH access is disabled")
                    self.penalized_hotkeys_checklist.append({"hotkey": axon.hotkey, "status_code": "SSH_ACCESS_DISABLED", "description": "It can not access to the server via ssh"})               

    def execute_specs_request(self):
        if len(self.queryable_for_specs) > 0:
            return
        else:
            # Miners to query this block
            self.queryable_for_specs = self.queryable.copy()

        bt.logging.info(f"💻 Initialisation of the {Specs.__name__} queries...")
        # # Prepare app_data for benchmarking
        # # Generate secret key for app
        secret_key = Fernet.generate_key()
        cipher_suite = Fernet(secret_key)
        # # Compile the script and generate an exe.
        ag.run(secret_key)
        try:
            main_dir = os.path.dirname(os.path.abspath(__file__))
            file_name = os.path.join(main_dir, "Validator/dist/script")
            # Read the exe file and save it to app_data.
            with open(file_name, "rb") as file:
                # Read the entire content of the EXE file
                app_data = file.read()
        except Exception as e:
            bt.logging.error(f"{e}")
            return

        results = {}
        while len(self.queryable_for_specs) > 0:
            uids = list(self.queryable_for_specs.keys())
            queryable_for_specs_uids = random.sample(uids, self.validator_specs_batch_size) if len(uids) > self.validator_specs_batch_size else uids
            queryable_for_specs_uid = []
            queryable_for_specs_axon = []
            queryable_for_specs_hotkey = []

            for uid, axon in self.queryable_for_specs.items():
                if uid in queryable_for_specs_uids:
                    queryable_for_specs_uid.append(uid)
                    queryable_for_specs_axon.append(axon)
                    queryable_for_specs_hotkey.append(axon.hotkey)

            for uid in queryable_for_specs_uids:
                del self.queryable_for_specs[uid]

            try:
                # Query the miners for benchmarking
                bt.logging.info(f"💻 Hardware list of uids queried: {queryable_for_specs_uid}")
                responses = self.dendrite.query(queryable_for_specs_axon, Specs(specs_input=repr(app_data)), timeout=specs_timeout)

                # Format responses and save them to benchmark_responses
                for index, response in enumerate(responses):
                    try:
                        if response:
                            binary_data = ast.literal_eval(response)  # Convert str to binary data
                            decrypted = cipher_suite.decrypt(binary_data)  # Decrypt str to binary data
                            decoded_data = json.loads(decrypted.decode())  # Convert data to object
                            results[queryable_for_specs_uid[index]] = (queryable_for_specs_hotkey[index], decoded_data)
                        else:
                            results[queryable_for_specs_uid[index]] = (queryable_for_specs_hotkey[index], {})
                    except cryptography.fernet.InvalidToken:
                        bt.logging.warning(f"{queryable_for_specs_hotkey[index]} - InvalidToken")
                        results[queryable_for_specs_uid[index]] = (queryable_for_specs_hotkey[index], {})
                    except Exception as _:
                        traceback.print_exc()
                        results[queryable_for_specs_uid[index]] = (queryable_for_specs_hotkey[index], {})

            except Exception as e:
                traceback.print_exc()

        update_miner_details(self.db, list(results.keys()), list(results.values()))
        bt.logging.info(f"✅ Hardware list responses:")

        # Hardware list response hotfix 1.3.11
        db = ComputeDb()
        hardware_details = get_miner_details(db)
        for hotkey, specs in hardware_details.items():
            bt.logging.info(f"{hotkey} - {specs}")
        """
        for hotkey, specs in results.values():
            bt.logging.info(f"{hotkey} - {specs}")
        """
        self.finalized_specs_once = True

    def get_specs_wandb(self):

        bt.logging.info(f"💻 Hardware list of uids queried (Wandb): {list(self._queryable_uids.keys())}")

        specs_dict = self.wandb.get_miner_specs(self._queryable_uids) 
        # Update the local db with the data from wandb
        update_miner_details(self.db, list(specs_dict.keys()), list(specs_dict.values()))

        # Log the hotkey and specs
        bt.logging.info(f"✅ Hardware list responses:")
        for hotkey, specs in specs_dict.values():
            bt.logging.info(f"{hotkey} - {specs}")

        self.finalized_specs_once = True

    def set_weights(self):
        # Remove all negative scores and attribute them 0.
        self.scores[self.scores < 0] = 0
        # Normalize the scores into weights
        weights: torch.FloatTensor = torch.nn.functional.normalize(self.scores, p=1.0, dim=0).float()
        bt.logging.info(f"🏋️ Weight of miners : {weights.tolist()}")
        # This is a crucial step that updates the incentive mechanism on the Bittensor blockchain.
        # Miners with higher scores (or weights) receive a larger share of TAO rewards on this subnet.
        result = self.subtensor.set_weights(
            netuid=self.config.netuid,  # Subnet to set weights on.
            wallet=self.wallet,  # Wallet to sign set weights using hotkey.
            uids=self.uids,  # Uids of the miners to set weights for.
            weights=weights,  # Weights to set for the miners.
            version_key=__version_as_int__,
            wait_for_inclusion=False,
        )
        if isinstance(result, bool) and result or isinstance(result, tuple) and result[0]:
            bt.logging.info(result)
            bt.logging.success("✅ Successfully set weights.")
        else:
            bt.logging.error(result)
            bt.logging.error("❌ Failed to set weights.")

    def next_info(self, cond, next_block):
        if cond:
            return calculate_next_block_time(self.current_block, next_block)
        else:
            return None

    async def start(self):
        """The Main Validation Loop"""
        self.loop = asyncio.get_running_loop()

        # Step 5: Perform queries to miners, scoring, and weight
        block_next_challenge = 1
        block_next_sync_status = 1
        block_next_set_weights = self.current_block + weights_rate_limit
        block_next_hardware_info = 1        
        block_next_miner_checking = 1

        time_next_challenge = None
        time_next_sync_status = None
        time_next_set_weights = None
        time_next_hardware_info = None        
        time_next_miner_checking = None

        bt.logging.info("Starting validator loop.")
        while True:
            try:
                self.sync_local()

                if self.current_block not in self.blocks_done:
                    self.blocks_done.add(self.current_block)

                    time_next_challenge = self.next_info(not block_next_challenge == 1, block_next_challenge)
                    time_next_sync_status = self.next_info(not block_next_sync_status == 1, block_next_sync_status)
                    time_next_set_weights = self.next_info(not block_next_set_weights == 1, block_next_set_weights)
                    time_next_hardware_info = self.next_info(
                        not block_next_hardware_info == 1 and self.validator_perform_hardware_query, block_next_hardware_info
                    )
                    time_next_miner_checking = self.next_info(not block_next_miner_checking == 1, block_next_miner_checking)

                    # Perform pow queries
                    if self.current_block % block_next_challenge == 0 or block_next_challenge < self.current_block:
                        # Next block the validators will challenge again.
                        block_next_challenge = self.current_block + random.randint(50, 80)  # 50,80 -> between ~ 10 and 16 minutes

                        # Filter axons with stake and ip address.
                        self._queryable_uids = self.get_queryable()

                        self.pow_requests = {}
                        self.new_pow_benchmark = {}

                        self.threads = []
                        for i in range(0, len(self.uids), self.validator_challenge_batch_size):
                            for _uid in self.uids[i : i + self.validator_challenge_batch_size]:
                                try:
                                    axon = self._queryable_uids[_uid]
                                    if axon.hotkey in self.allocated_hotkeys:
                                        continue
                                    difficulty = self.calc_difficulty(_uid)
                                    password, _hash, _salt, mode, chars, mask = run_validator_pow(length=difficulty)
                                    self.pow_requests[_uid] = (password, _hash, _salt, mode, chars, mask, difficulty)
                                    self.threads.append(
                                        threading.Thread(
                                            target=self.execute_pow_request,
                                            args=(_uid, axon, _hash, _salt, mode, chars, mask, difficulty),
                                            name=f"th_execute_pow_request-{_uid}",
                                            daemon=True,
                                        )
                                    )
                                except KeyError:
                                    continue

                        for thread in self.threads:
                            thread.start()

                        for thread in self.threads:
                            thread.join()

                        self.pow_benchmark = self.new_pow_benchmark
                        self.pow_benchmark_success = {k: v for k, v in self.pow_benchmark.items() if v["success"] is True and v["elapsed_time"] < pow_timeout}

                        # Logs benchmarks for the validators
                        if len(self.pow_benchmark_success) > 0:
                            bt.logging.info("✅ Results success benchmarking:")
                            for uid, benchmark in self.pow_benchmark_success.items():
                                bt.logging.info(f"{uid}: {benchmark}")
                        else:
                            bt.logging.warning("❌ Benchmarking: All miners failed. An issue occurred.")

                        pow_benchmarks_list = [{**values, "uid": uid} for uid, values in self.pow_benchmark.items()]
                        update_challenge_details(self.db, pow_benchmarks_list)

                        self.sync_scores()

                    # Perform specs queries
                    if (self.current_block % block_next_hardware_info == 0 and self.validator_perform_hardware_query) or (
                        block_next_hardware_info < self.current_block and self.validator_perform_hardware_query
                    ):
                        block_next_hardware_info = self.current_block + 150  # 150 -> ~ every 30 minutes

                        if not hasattr(self, "_queryable_uids"):
                            self._queryable_uids = self.get_queryable()

                        # self.loop.run_in_executor(None, self.execute_specs_request) replaced by wandb query.
                        self.get_specs_wandb()

                    # Perform miner checking
                    if self.current_block % block_next_miner_checking == 0 or block_next_miner_checking < self.current_block:
                        # Next block the validators will do port checking again.
                        block_next_miner_checking = self.current_block + 50  # 50 -> every 10 minutes

                        # Filter axons with stake and ip address.
                        self._queryable_uids = self.get_queryable()

                        #self.sync_checklist()

                    if self.current_block % block_next_sync_status == 0 or block_next_sync_status < self.current_block:
                        block_next_sync_status = self.current_block + 25  # ~ every 5 minutes
                        self.sync_status()

                        # Log chain data to wandb
                        chain_data = {
                            "Block": self.current_block,
                            "Stake": float(self.metagraph.S[self.validator_subnet_uid]),
                            "Rank": float(self.metagraph.R[self.validator_subnet_uid]),
                            "vTrust": float(self.metagraph.validator_trust[self.validator_subnet_uid]),
                            "Emission": float(self.metagraph.E[self.validator_subnet_uid]),
                        }
                        self.wandb.log_chain_data(chain_data)

                    # Periodically update the weights on the Bittensor blockchain, ~ every 20 minutes
                    if self.current_block - self.last_updated_block > weights_rate_limit:
                        block_next_set_weights = self.current_block + weights_rate_limit
                        self.sync_scores()
                        self.set_weights()
                        self.last_updated_block = self.current_block
                        self.blocks_done.clear()
                        self.blocks_done.add(self.current_block)

                bt.logging.info(
                    (
                        f"Block:{self.current_block} | "
                        f"Stake:{self.metagraph.S[self.validator_subnet_uid]} | "
                        f"Rank:{self.metagraph.R[self.validator_subnet_uid]} | "
                        f"vTrust:{self.metagraph.validator_trust[self.validator_subnet_uid]} | "
                        f"Emission:{self.metagraph.E[self.validator_subnet_uid]} | "
                        f"next_challenge: #{block_next_challenge} ~ {time_next_challenge} | "
                        f"sync_status: #{block_next_sync_status} ~ {time_next_sync_status} | "
                        f"set_weights: #{block_next_set_weights} ~ {time_next_set_weights} | "
                        f"hardware_info: #{block_next_hardware_info} ~ {time_next_hardware_info} |"
                        f"miner_checking: #{block_next_miner_checking} ~ {time_next_miner_checking}"
                    )
                )
                time.sleep(1)

            # If we encounter an unexpected error, log it for debugging.
            except RuntimeError as e:
                bt.logging.error(e)
                traceback.print_exc()

            # If the user interrupts the program, gracefully exit.
            except KeyboardInterrupt:
                self.db.close()
                bt.logging.success("Keyboard interrupt detected. Exiting validator.")
                exit()


def main():
    """
    Main function to run the neuron.

    This function initializes and runs the neuron. It handles the main loop, state management, and interaction
    with the Bittensor network.
    """
    validator = Validator()
    asyncio.run(validator.start())


if __name__ == "__main__":
    main()
