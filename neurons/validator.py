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
import os
import random
import traceback
from typing import List, Dict, Union

import bittensor as bt
import time
import torch
from cryptography.fernet import Fernet
from torch._C._te import Tensor

import Validator.app_generator as ag
import Validator.calculate_pow_score as cps
import Validator.database as db
from Validator.pow import run_validator_pow
from compute import pow_min_difficulty, pow_timeout, SUSPECTED_EXPLOITERS_HOTKEYS, SUSPECTED_EXPLOITERS_COLDKEYS
from compute.axon import ComputeSubnetSubtensor
from compute.protocol import Challenge, PerfInfo, Allocate
from compute.utils.parser import ComputeArgPaser
from compute.utils.subtensor import is_registered
from compute.utils.version import try_update, get_local_version


class Validator:
    pow_requests: dict = {}
    pow_responses: dict = {}
    pow_benchmark: dict = {}
    new_pow_benchmark: dict = {}

    scores: Tensor

    score_decay_factor = 0.334
    score_limit = 0.5

    _queryable_uids: Dict[int, bt.AxonInfo]

    @property
    def wallet(self):
        return self._wallet

    @property
    def subtensor(self):
        return self._subtensor

    @property
    def dendrite(self):
        return self._dendrite

    @property
    def metagraph(self):
        return self._metagraph

    @property
    def queryable_uids(self):
        return [uid for uid in self._queryable_uids.keys()]

    @property
    def queryable_axons(self):
        return [axon for axon in self._queryable_uids.values()]

    @property
    def queryable_hotkeys(self):
        return [axon.hotkey for axon in self._queryable_uids.values()]

    def __init__(self):
        # Step 1: Parse the bittensor and compute subnet config
        self.config = self.init_config()

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

        # Set blacklist and whitelist arrays
        self.blacklist_hotkeys = {hotkey for hotkey in self.config.blacklist_hotkeys}
        self.blacklist_coldkeys = {coldkey for coldkey in self.config.blacklist_coldkeys}
        self.whitelist_hotkeys = {hotkey for hotkey in self.config.whitelist_hotkeys}
        self.whitelist_coldkeys = {coldkey for coldkey in self.config.whitelist_coldkeys}

        self.exploiters_hotkeys = {hotkey for hotkey in SUSPECTED_EXPLOITERS_HOTKEYS} if self.config.blacklist_exploiters else {}
        self.exploiters_coldkeys = {coldkey for coldkey in SUSPECTED_EXPLOITERS_COLDKEYS} if self.config.blacklist_exploiters else {}

        # Set custom validator arguments
        self.validator_challenge_batch_size = self.config.validator_challenge_batch_size
        self.validator_perform_hardware_query = self.config.validator_perform_hardware_query

        # Step 3: Connect the validator to the network
        # Check if hotkey is registered
        is_registered(wallet=self.wallet, metagraph=self.metagraph, subtensor=self.subtensor, entity="validator")

        # Initialize the prometheus transaction
        self.init_prometheus()

        # Step 4: Set up initial scoring weights for validation
        bt.logging.info("Building validation weights.")
        self.uids: list = self.metagraph.uids.tolist()
        self.last_uids: list = self.uids.copy()
        self.init_scores()

        self.curr_block = self.subtensor.block
        self.last_updated_block = self.curr_block - (self.curr_block % 100)

        # Init the event loop.
        self.loop = asyncio.get_event_loop()

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

    def init_prometheus(self):
        """
        Register the prometheus information on metagraph.
        :return: bool
        """
        bt.logging.info("Extrinsic prometheus information on metagraph.")
        success = self.subtensor.serve_prometheus(
            wallet=self.wallet,
            port=bt.defaults.axon.port,
            netuid=self.config.netuid,
        )
        if success:
            bt.logging.success(prefix="Prometheus served", sufix=f"<blue>Current version: {get_local_version()}</blue>")
        else:
            bt.logging.error("Prometheus initialization failed")
        return success

    def init_scores(self):
        self.scores = torch.zeros(len(self.uids), dtype=torch.float32)
        bt.logging.info(f"🔢 Initialized scores : {self.scores.tolist()}")

    def sync_scores(self):
        # Set the weights of validators to zero.
        self.scores = self.scores * (self.metagraph.total_stake < 1.024e3)
        # Set the weight to zero for all nodes without assigned IP addresses.
        self.scores = self.scores * torch.Tensor(self.get_valid_tensors(metagraph=self.metagraph))
        bt.logging.info(f"🔢 Synced scores : {self.scores.tolist()}")

    def sync_local(self):
        """
        Resync our local state with the latest state from the blockchain.
        Sync scores with metagraph.
        Get the current uids of all miners in the network.
        """
        bt.logging.info(f"🔄 Syncing metagraph with subtensor.")
        self.sync_scores()
        self._metagraph = self.subtensor.metagraph(self.config.netuid)
        self.uids = self.metagraph.uids.tolist()

    def start(self):
        """The Main Validation Loop"""
        # Step 5: Perform queries to miners, scoring, and weight
        bt.logging.info("Starting validator loop.")

        step = 0
        step_pseudo_rdm = 20
        while True:
            current_block = self.subtensor.block
            try:
                # Sync the subtensor state with the blockchain, every ~ 1 minute
                if step % 10 == 0:
                    self.sync_local()

                # Perform pow queries, between ~ 10 and 14 minutes
                if step % step_pseudo_rdm == 0:
                    # Prepare the next random step the validators will challenge again
                    step_pseudo_rdm = random.randint(100, 140)

                    # Filter axons with stake and ip address.
                    self._queryable_uids = self.get_queryable()

                    self.pow_requests = {}
                    self.new_pow_benchmark = {}

                    async def run_pow():
                        for i in range(0, len(self.uids), self.validator_challenge_batch_size):
                            tasks = []
                            for _uid in self.uids[i : i + self.validator_challenge_batch_size]:
                                try:
                                    axon = self._queryable_uids[_uid]
                                    password, _hash, _salt, mode, chars, mask = run_validator_pow()
                                    self.pow_requests[_uid] = (password, _hash, _salt, mode, chars, mask, pow_min_difficulty)
                                    tasks.append(self.execute_pow_request(_uid, axon, password, _hash, _salt, mode, chars, mask))
                                except KeyError:
                                    continue
                            await asyncio.gather(*tasks)

                    self.loop.run_until_complete(run_pow())

                    self.pow_benchmark = self.new_pow_benchmark
                    # Logs benchmarks for the validators
                    bt.logging.info("🔢 Results benchmarking:")
                    for uid, benchmark in self.pow_benchmark.items():
                        bt.logging.info(f"{uid}: {benchmark}")

                    # TODO update db accordingly with pow results
                    # db.update(...)

                    # Calculate score
                    score_uid_dict = {}
                    for uid in self.uids:
                        previous_score = self.scores[uid]
                        try:
                            score = cps.score(
                                self.pow_benchmark[uid],
                                self.pow_requests[uid][-1],
                                self._queryable_uids[uid].hotkey,
                            )
                        except (ValueError, KeyError):
                            score = 0

                        if previous_score > score < self.score_limit:
                            decayed_score = previous_score * self.score_decay_factor
                        else:
                            decayed_score = score

                        self.scores[uid] = decayed_score if decayed_score > self.score_limit else score
                        score_uid_dict[uid] = self.scores[uid].item()

                    bt.logging.info(f"🔢 Updated scores : {score_uid_dict}")

                # ~ every 5 minutes
                if step % 50 == 0:
                    # Check for auto update
                    if self.config.auto_update:
                        try_update()
                    # Frequently check if the validator is still registered
                    is_registered(wallet=self.wallet, metagraph=self.metagraph, subtensor=self.subtensor, entity="validator")

                # ~ every 20 minutes
                if step % 200 == 0 and self.validator_perform_hardware_query:
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
                        continue
                    # Query the miners for benchmarking
                    bt.logging.info(f"🆔 Hardware list of uids : {self.queryable_uids}")
                    responses: List[Union[PerfInfo, Allocate, Challenge]] = self.dendrite.query(
                        self.queryable_axons,
                        PerfInfo(perf_input=repr(app_data)),
                        timeout=120,
                    )

                    # Format responses and save them to benchmark_responses
                    hardware_list_responses = []
                    for index, response in enumerate(responses):
                        try:
                            if response:
                                binary_data = ast.literal_eval(response)  # Convert str to binary data
                                decoded_data = ast.literal_eval(cipher_suite.decrypt(binary_data).decode())  # Decrypt data and convert it to object
                                hardware_list_responses.append(decoded_data)
                            else:
                                hardware_list_responses.append({})
                        except Exception as _:
                            hardware_list_responses.append({})

                    db.update(self.queryable_hotkeys, hardware_list_responses)
                    bt.logging.info(f"🔢 Hardware list responses : {hardware_list_responses}")

                # Periodically update the weights on the Bittensor blockchain, ~ every 20 minutes
                if current_block - self.last_updated_block > 100:
                    self.set_weights()
                    self.last_updated_block = current_block

                bt.logging.info(f"Validator running at block {current_block}...")
                step += 1

                # Sleep for a duration equivalent to half a block time (i.e., time between successive blocks).
                time.sleep(bt.__blocktime__ / 2)

            # If we encounter an unexpected error, log it for debugging.
            except RuntimeError as e:
                bt.logging.error(e)
                traceback.print_exc()

            # If the user interrupts the program, gracefully exit.
            except KeyboardInterrupt:
                bt.logging.success("Keyboard interrupt detected. Exiting validator.")
                exit()

    def set_weights(self):
        weights: torch.FloatTensor = torch.nn.functional.normalize(self.scores, p=1.0, dim=0).float()
        bt.logging.info(f"🏋️ Weight of miners : {weights.tolist()}")
        # This is a crucial step that updates the incentive mechanism on the Bittensor blockchain.
        # Miners with higher scores (or weights) receive a larger share of TAO rewards on this subnet.
        result = self.subtensor.set_weights(
            netuid=self.config.netuid,  # Subnet to set weights on.
            wallet=self.wallet,  # Wallet to sign set weights using hotkey.
            uids=self.metagraph.uids,  # Uids of the miners to set weights for.
            weights=weights,  # Weights to set for the miners.
            wait_for_inclusion=False,
        )
        if result:
            bt.logging.success("Successfully set weights.")
        else:
            bt.logging.error("Failed to set weights.")

    # Filter the axons with uids_list, remove those with the same IP address.
    @staticmethod
    def filter_axons(queryable_tuple_uids_axons):
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

    def get_valid_queryable(self):
        valid_queryable = []
        for uid in self.uids:
            neuron: bt.NeuronInfoLite = self.metagraph.neurons[uid]
            axon = self.metagraph.axons[uid]

            if neuron.axon_info.ip != "0.0.0.0" and self.metagraph.total_stake[uid] < 1.024e3 and not self.is_blacklisted(neuron=neuron):
                valid_queryable.append((uid, axon))

        return valid_queryable

    def get_valid_tensors(self, metagraph):
        tensors = []
        for uid in metagraph.uids:
            neuron = metagraph.neurons[uid]

            if neuron.axon_info.ip != "0.0.0.0" and not self.is_blacklisted(neuron=neuron):
                tensors.append(True)
            else:
                tensors.append(False)

        return tensors

    def get_queryable(self):
        queryable = self.get_valid_queryable()
        dict_filtered_axons = self.filter_axons(queryable_tuple_uids_axons=queryable)
        return dict_filtered_axons

    async def execute_pow_request(self, uid, axon, password, _hash, _salt, mode, chars, mask):
        start_time = time.time()
        response = self.dendrite.query(
            axon,
            Challenge(
                challenge_hash=_hash,
                challenge_salt=_salt,
                challenge_mode=mode,
                challenge_chars=chars,
                challenge_mask=mask,
            ),
            timeout=pow_timeout,
        )
        elapsed_time = time.time() - start_time
        self.pow_responses[uid] = response

        if password != response.get("password"):
            self.new_pow_benchmark[uid] = {"success": False, "elapsed_time": elapsed_time}
        else:
            self.new_pow_benchmark[uid] = {"success": True, "elapsed_time": elapsed_time}


def main():
    """
    Main function to run the neuron.

    This function initializes and runs the neuron. It handles the main loop, state management, and interaction
    with the Bittensor network.
    """
    Validator().start()


if __name__ == "__main__":
    main()
