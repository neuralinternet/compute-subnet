# The MIT License (MIT)
# Copyright © 2023 GitPhantomman
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
import asyncio
import json
import os
import threading
import traceback
import typing

import bittensor as bt
import time
import torch
import websocket

import compute
from compute.axon import ComputeSubnetAxon, ComputeSubnetSubtensor
from compute.protocol import Specs, Allocate, Challenge
from compute.utils.parser import ComputeArgPaser
from compute.utils.subtensor import is_registered, get_current_block
from compute.utils.version import check_hashcat_version, try_update, version2number, get_remote_version
from neurons.Miner.allocate import check_allocation, register_allocation
from neurons.Miner.pow import check_cuda_availability, run_miner_pow
from neurons.Miner.specs import get_respond


class Miner:
    blocks_done: set = set()

    blacklist_hotkeys: set
    blacklist_coldkeys: set
    whitelist_hotkeys: set
    whitelist_coldkeys: set
    whitelist_hotkeys_version: set = set()
    exploiters_hotkeys_set: set

    semaphore: asyncio.Semaphore
    lock: asyncio.Lock

    th_synchronize: threading.Thread
    th_update_repo: threading.Thread
    th_valid_hotkeys: threading.Thread

    _axon: bt.axon

    @property
    def wallet(self):
        return self._wallet

    @property
    def subtensor(self):
        return self._subtensor

    @property
    def metagraph(self):
        return self._metagraph

    @property
    def axon(self):
        return self._axon

    @property
    def current_block(self):
        return get_current_block(subtensor=self.subtensor)

    def __init__(self):
        # Step 1: Parse the bittensor and compute subnet config
        self.config = self.init_config()

        # Step 2: Initialize different black and white list
        self.init_black_and_white_list()

        # Activating Bittensor's logging with the set configurations.
        bt.logging(config=self.config, logging_dir=self.config.full_path)
        bt.logging.info(f"Running miner for subnet: {self.config.netuid} on network: {self.config.subtensor.chain_endpoint} with config:")

        # Step 3: Initialize Bittensor miner objects
        # These classes are vital to interact and function within the Bittensor network.
        bt.logging.info("Setting up bittensor objects.")

        # Wallet holds cryptographic information, ensuring secure transactions and communication.
        self._wallet = bt.wallet(config=self.config)
        bt.logging.info(f"Wallet: {self.wallet}")

        # Subtensor manages the blockchain connection, facilitating interaction with the Bittensor blockchain.
        self._subtensor = ComputeSubnetSubtensor(config=self.config)
        bt.logging.info(f"Subtensor: {self.subtensor}")

        # Metagraph provides the network's current state, holding state about other participants in a subnet.
        self._metagraph = self.subtensor.metagraph(self.config.netuid)
        bt.logging.info(f"Metagraph: {self.metagraph}")

        self.uids = self.metagraph.uids

        # Allow validators that are not permitted by stake
        self.miner_whitelist_not_enough_stake = self.config.miner_whitelist_not_enough_stake

        self.miner_subnet_uid = is_registered(wallet=self.wallet, metagraph=self.metagraph, subtensor=self.subtensor, entity="miner")

        check_cuda_availability()

        self.hashcat_path = self.config.miner_hashcat_path
        self.hashcat_workload_profile = self.config.miner_hashcat_workload_profile
        self.hashcat_extended_options = self.config.miner_hashcat_extended_options

        check_hashcat_version(hashcat_path=self.hashcat_path)

        self.init_axon()

        self.lck_synchronize = threading.Lock()
        self.lck_update_repo = threading.Lock()
        self.lck_valid_hotkeys = threading.Lock()

        self.init_threads()

    def init_threads(self):
        self.th_synchronize = threading.Thread(target=self.th_synchronize_func, name="th_synchronize", daemon=True)
        self.th_synchronize.start()

        if self.config.auto_update:
            self.th_update_repo = threading.Thread(target=self.th_update_repo_func, name="th_update_repo", daemon=True)
            self.th_update_repo.start()

        if self.config.miner_whitelist_version:
            self.th_valid_hotkeys = threading.Thread(target=self.th_valid_hotkeys, name="th_valid_hotkeys", daemon=True)
            self.th_valid_hotkeys.start()

    def th_valid_hotkeys(self):
        while True:
            with self.lck_valid_hotkeys:
                try:
                    self.whitelist_hotkeys_version.clear()
                    try:
                        latest_version = version2number(get_remote_version(pattern="__minimal_validator_version__"))

                        if latest_version is None:
                            bt.logging.error(f"Github API call failed or version string is incorrect!")
                            continue

                        valid_validators = self.get_valid_validator()
                        for uid, hotkey, version in valid_validators:
                            try:
                                if version >= latest_version:
                                    bt.logging.debug(f"Version signature match for hotkey : {hotkey}")
                                    self.whitelist_hotkeys_version.add(hotkey)
                                    continue

                                bt.logging.debug(f"Version signature mismatch for hotkey : {hotkey}")
                            except Exception:
                                bt.logging.error(f"exception in get_valid_hotkeys: {traceback.format_exc()}")

                        bt.logging.info(f"Total valid validator hotkeys = {self.whitelist_hotkeys_version}")

                    except json.JSONDecodeError:
                        bt.logging.error(f"exception in get_valid_hotkeys: {traceback.format_exc()}")
                except Exception as _:
                    bt.logging.error(traceback.format_exc())
                finally:
                    time.sleep(200)

    def th_update_repo_func(self):
        while True:
            with self.lck_update_repo:
                try:
                    try_update()
                except Exception as _:
                    bt.logging.error(traceback.format_exc())
                    continue
                finally:
                    time.sleep(300)

    def th_synchronize_func(self):
        last_updated_block = self.current_block - (self.current_block % 100)
        bt.logging.info(f"Starting sync loop at block: {self.current_block}")
        while True:
            try:
                try:
                    with self.lck_synchronize:
                        self.metagraph.sync(subtensor=self.subtensor)
                except (websocket.WebSocketTimeoutException, websocket.WebSocketProtocolException, OSError) as e:
                    bt.logging.warning(f"{e} <<< (can be ignored if you don't have it often)")

                if self.current_block not in self.blocks_done:
                    self.blocks_done.add(self.current_block)

                    log = (
                        f"Miner running at block: {self.current_block} | "
                        f"Stake:{self.metagraph.S[self.miner_subnet_uid]} | "
                        f"Rank:{self.metagraph.R[self.miner_subnet_uid]} | "
                        f"Trust:{self.metagraph.T[self.miner_subnet_uid]} | "
                        f"Consensus:{self.metagraph.C[self.miner_subnet_uid] } | "
                        f"Incentive:{self.metagraph.I[self.miner_subnet_uid]} | "
                        f"Emission:{self.metagraph.E[self.miner_subnet_uid]}"
                    )
                    bt.logging.info(log)

                    # Ensure miner is still active, ~ every 20 minutes
                    if self.current_block - last_updated_block > compute.weights_rate_limit:
                        self.set_weights()
                        last_updated_block = self.current_block
            except Exception as _:
                bt.logging.error(traceback.format_exc())
                continue
            finally:
                time.sleep(5)

    @staticmethod
    def init_config():
        """
        This function is responsible for setting up and parsing command-line arguments.
        :return: config
        """
        parser = ComputeArgPaser(description="This script aims to help miners with the compute subnet.")
        config = bt.config(parser)

        # Step 3: Set up logging directory
        # Logging captures events for diagnosis or understanding miner's behavior.
        config.full_path = os.path.expanduser(
            "{}/{}/{}/netuid{}/{}".format(
                config.logging.logging_dir,
                config.wallet.name,
                config.wallet.hotkey,
                config.netuid,
                "miner",
            )
        )
        # Ensure the directory for logging exists, else create one.
        if not os.path.exists(config.full_path):
            os.makedirs(config.full_path, exist_ok=True)
        return config

    def init_black_and_white_list(self):
        # Set blacklist and whitelist arrays
        self.blacklist_hotkeys = {hotkey for hotkey in self.config.blacklist_hotkeys}
        self.blacklist_coldkeys = {coldkey for coldkey in self.config.blacklist_coldkeys}
        self.whitelist_hotkeys = {hotkey for hotkey in self.config.whitelist_hotkeys}
        self.whitelist_coldkeys = {coldkey for coldkey in self.config.whitelist_coldkeys}

        if self.config.blacklist_exploiters:
            self.exploiters_hotkeys_set = {key for key in compute.SUSPECTED_EXPLOITERS_HOTKEYS}
        else:
            self.exploiters_hotkeys_set = set()

    def init_axon(self):
        # Step 6: Build and link miner functions to the axon.
        # The axon handles request processing, allowing validators to send this process requests.
        self._axon = ComputeSubnetAxon(wallet=self.wallet, config=self.config)
        bt.logging.info(f"Axon {self.axon}")

        # Attach determiners which functions are called when servicing a request.
        bt.logging.info(f"Attaching forward function to axon.")
        self.axon.attach(
            forward_fn=self.allocate,
            blacklist_fn=self.blacklist_allocate,
            priority_fn=self.priority_allocate,
        ).attach(
            forward_fn=self.challenge,
            blacklist_fn=self.blacklist_challenge,
            priority_fn=self.priority_challenge,
        ).attach(
            forward_fn=self.specs,
            blacklist_fn=self.blacklist_specs,
            priority_fn=self.priority_specs,
        )

        # Serve passes the axon information to the network + netuid we are hosting on.
        # This will auto-update if the axon port of external ip have changed.
        bt.logging.info(f"Serving axon {self.axon} on network: {self.config.subtensor.chain_endpoint} with netuid: {self.config.netuid}")

        self.axon.serve(netuid=self.config.netuid, subtensor=self.subtensor)

        # Start  starts the miner's axon, making it active on the network.
        bt.logging.info(f"Starting axon server on port: {self.config.axon.port}")
        self.axon.start()

    def base_blacklist(self, synapse: typing.Union[Specs, Allocate, Challenge]) -> typing.Tuple[bool, str]:
        hotkey = synapse.dendrite.hotkey
        synapse_type = type(synapse).__name__

        with self.lck_synchronize:
            _metagraph = self.metagraph
        if hotkey not in _metagraph.hotkeys:
            # Ignore requests from unrecognized entities.
            bt.logging.trace(f"Blacklisting unrecognized hotkey {hotkey}")
            return True, "Unrecognized hotkey"

        index = _metagraph.hotkeys.index(hotkey)
        stake = _metagraph.S[index].item()

        if stake < compute.validator_permit_stake and not self.miner_whitelist_not_enough_stake:
            bt.logging.trace(f"Not enough stake {stake}")
            return True, "Not enough stake!"

        if len(self.whitelist_hotkeys) > 0 and hotkey not in self.whitelist_hotkeys:
            return True, "Not whitelisted"

        if len(self.blacklist_hotkeys) > 0 and hotkey in self.blacklist_hotkeys:
            return True, "Blacklisted hotkey"

        # Blacklist entities that are not up-to-date
        if hotkey not in self.whitelist_hotkeys_version and len(self.whitelist_hotkeys_version) > 0:
            return (
                True,
                f"Blacklisted a {synapse_type} request from a non-updated hotkey: {hotkey}",
            )

        if hotkey in self.exploiters_hotkeys_set:
            return (
                True,
                f"Blacklisted a {synapse_type} request from an exploiter hotkey: {hotkey}",
            )

        bt.logging.trace(f"Not Blacklisting recognized hotkey {synapse.dendrite.hotkey}")
        return False, "Hotkey recognized!"

    def base_priority(self, synapse: typing.Union[Specs, Allocate, Challenge]) -> float:
        with self.lck_synchronize:
            _metagraph = self.metagraph
        caller_uid = _metagraph.hotkeys.index(synapse.dendrite.hotkey)  # Get the caller index.
        priority = float(_metagraph.S[caller_uid])  # Return the stake as the priority.
        bt.logging.trace(f"Prioritizing {synapse.dendrite.hotkey} with value: ", priority)
        return priority

    # The blacklist function decides if a request should be ignored.
    def blacklist_specs(self, synapse: Specs) -> typing.Tuple[bool, str]:
        return self.base_blacklist(synapse)

    # The priority function determines the order in which requests are handled.
    # More valuable or higher-priority requests are processed before others.
    def priority_specs(self, synapse: Specs) -> float:
        return self.base_priority(synapse) + compute.miner_priority_specs

    # This is the PerfInfo function, which decides the miner's response to a valid, high-priority request.
    @staticmethod
    def specs(synapse: Specs) -> Specs:
        app_data = synapse.specs_input
        synapse.specs_output = get_respond(app_data)
        return synapse

    # The blacklist function decides if a request should be ignored.
    def blacklist_allocate(self, synapse: Allocate) -> typing.Tuple[bool, str]:
        return self.base_blacklist(synapse)

    # The priority function determines the order in which requests are handled.
    # More valuable or higher-priority requests are processed before others.
    def priority_allocate(self, synapse: Allocate) -> float:
        return self.base_priority(synapse) + compute.miner_priority_allocate

    # This is the Allocate function, which decides the miner's response to a valid, high-priority request.
    @staticmethod
    def allocate(synapse: Allocate) -> Allocate:
        timeline = synapse.timeline
        device_requirement = synapse.device_requirement
        checking = synapse.checking

        if checking is True:
            result = check_allocation(timeline, device_requirement)
            synapse.output = result
        else:
            public_key = synapse.public_key
            result = register_allocation(timeline, device_requirement, public_key)
            synapse.output = result
        return synapse

    # The blacklist function decides if a request should be ignored.
    def blacklist_challenge(self, synapse: Challenge) -> typing.Tuple[bool, str]:
        return self.base_blacklist(synapse)

    # The priority function determines the order in which requests are handled.
    # More valuable or higher-priority requests are processed before others.
    def priority_challenge(self, synapse: Challenge) -> float:
        return self.base_priority(synapse) + compute.miner_priority_challenge

    # This is the Challenge function, which decides the miner's response to a valid, high-priority request.
    def challenge(self, synapse: Challenge) -> Challenge:
        bt.logging.info(f"Received challenge (hash, salt): ({synapse.challenge_hash}, {synapse.challenge_salt})")
        result = run_miner_pow(
            _hash=synapse.challenge_hash,
            salt=synapse.challenge_salt,
            mode=synapse.challenge_mode,
            chars=synapse.challenge_chars,
            mask=synapse.challenge_mask,
            hashcat_path=self.hashcat_path,
            hashcat_workload_profile=self.hashcat_workload_profile,
            hashcat_extended_options=self.hashcat_extended_options,
        )
        synapse.output = result
        return synapse

    def get_valid_validator_uids(self):
        valid_uids = []
        with self.lck_synchronize:
            _metagraph = self.metagraph
        uids = _metagraph.uids.tolist()
        for index, uid in enumerate(uids):
            if _metagraph.total_stake[index] > compute.validator_permit_stake:
                valid_uids.append(uid)
        return valid_uids

    def get_valid_validator(self):
        valid_validator_uids = self.get_valid_validator_uids()
        valid_validator = []
        for uid in valid_validator_uids:
            neuron = self.subtensor.neuron_for_uid(uid, self.config.netuid)
            hotkey = neuron.hotkey
            version = neuron.prometheus_info.version
            valid_validator.append((uid, hotkey, version))

        return valid_validator

    def set_weights(self):
        chain_weights = torch.zeros(self.subtensor.subnetwork_n(netuid=self.config.netuid))
        chain_weights[self.miner_subnet_uid] = 1
        # This is a crucial step that updates the incentive mechanism on the Bittensor blockchain.
        # Miners with higher scores (or weights) receive a larger share of TAO rewards on this subnet.
        result = self.subtensor.set_weights(
            netuid=self.config.netuid,  # Subnet to set weights on.
            wallet=self.wallet,  # Wallet to sign set weights using hotkey.
            uids=self.uids,  # Uids of the miners to set weights for.
            weights=chain_weights.float(),  # Weights to set for the miners.
            version_key=compute.__version_as_int__,
            wait_for_inclusion=False,
        )
        if result:
            bt.logging.success("Successfully set weights.")
        else:
            bt.logging.error("Failed to set weights.")

    def start(self):
        # This loop maintains the miner's operations until intentionally stopped.
        while True:
            try:
                time.sleep(2)
            # If someone intentionally stops the miner, it'll safely terminate operations.
            except KeyboardInterrupt:
                if self.th_synchronize:
                    self.th_synchronize.join()
                if self.th_update_repo:
                    self.th_update_repo.join()
                if self.th_valid_hotkeys:
                    self.th_valid_hotkeys.join()
                self.axon.stop()
                bt.logging.success("Miner killed by keyboard interrupt.")
                break
            # In case of unforeseen errors, the miner will log the error and continue operations.
            except Exception as _:
                bt.logging.error(traceback.format_exc())
                continue


def main():
    """
    Main function to run the miner.

    This function initializes and runs the miner. It handles the main loop, state management, and interaction
    with the Bittensor network.
    """
    Miner().start()


if __name__ == "__main__":
    main()
