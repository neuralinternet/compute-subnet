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
import time
import traceback
import typing
import multiprocessing
import base64
import bittensor as bt

from compute import (
    SUSPECTED_EXPLOITERS_HOTKEYS,
    __version_as_int__,
    validator_permit_stake,
    miner_priority_specs,
    miner_priority_allocate,
    miner_priority_challenge, TRUSTED_VALIDATORS_HOTKEYS,
)
from compute.axon import ComputeSubnetAxon, ComputeSubnetSubtensor
from compute.protocol import Specs, Allocate, Challenge
from compute.utils.math import percent
from compute.utils.parser import ComputeArgPaser
from compute.utils.subtensor import (
    is_registered,
    get_current_block,
    calculate_next_block_time,
)
from compute.utils.version import (
    check_hashcat_version,
    try_update,
    version2number,
    get_remote_version,
)
from neurons.Miner.allocate import check_allocation, register_allocation, deregister_allocation, check_if_allocated
from neurons.Miner.container import build_check_container, build_sample_container, check_container, kill_container
from compute.wandb.wandb import ComputeWandb
from neurons.Miner.allocate import check_allocation, register_allocation
from neurons.Miner.pow import check_cuda_availability, run_miner_pow
from neurons.Miner.specs import RequestSpecsProcessor
from neurons.Validator.script import check_docker_availability


class Miner:
    blocks_done: set = set()

    blacklist_hotkeys: set
    blacklist_coldkeys: set
    whitelist_hotkeys: set
    whitelist_coldkeys: set
    whitelist_hotkeys_version: set = set()
    exploiters_hotkeys_set: set

    miner_whitelist_updated_threshold: int

    miner_subnet_uid: int

    _axon: bt.axon

    @property
    def wallet(self) -> bt.wallet:
        return self._wallet

    @property
    def subtensor(self) -> ComputeSubnetSubtensor:
        return self._subtensor

    @property
    def metagraph(self) -> bt.metagraph:
        return self._metagraph

    @property
    def axon(self) -> bt.axon:
        return self._axon

    @property
    def current_block(self):
        return get_current_block(subtensor=self.subtensor)

    def __init__(self):
        # Step 1: Parse the bittensor and compute subnet config
        self.config = self.init_config()

        # Setup extra args
        self.miner_whitelist_updated_threshold = self.config.miner_whitelist_updated_threshold
        self.miner_whitelist_not_enough_stake = self.config.miner_whitelist_not_enough_stake
        self.init_black_and_white_list()

        # Set up logging with the provided configuration and directory.
        bt.logging(config=self.config, logging_dir=self.config.full_path)
        bt.logging.info(f"Running miner for subnet: {self.config.netuid} on network: {self.config.subtensor.chain_endpoint} with config:")
        # Log the configuration for reference.
        bt.logging.info(self.config)

        # Step 2: Build Bittensor miner objects
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

        build_check_container('my-compute-subnet','sn27-check-container')
        has_docker, msg = check_docker_availability()

        # Build sample container image to speed up the allocation process
        sample_docker = multiprocessing.Process(target=build_sample_container)
        sample_docker.start()

        if not has_docker:
            bt.logging.error(msg)
            exit(1)
        else:
            bt.logging.info(f"Docker is installed. Version: {msg}")

        check_cuda_availability()

        # Step 3: Set up hashcat for challenges
        self.hashcat_path = self.config.miner_hashcat_path
        self.hashcat_workload_profile = self.config.miner_hashcat_workload_profile
        self.hashcat_extended_options = self.config.miner_hashcat_extended_options

        check_hashcat_version(hashcat_path=self.hashcat_path)

        self.uids: list = self.metagraph.uids.tolist()

        self.sync_status()
        self.init_axon()

        # Step 4: Initialize wandb
        self.wandb = ComputeWandb(self.config, self.wallet, os.path.basename(__file__))
        self.wandb.update_specs()

        # check allocation status
        file_path = 'allocation_key'
        # Open the file in read mode ('r') and read the data
        with open(file_path, 'r') as file:
            allocation_key_encoded = file.read()

        if not self.wandb.sync_allocated(self.wallet.hotkey.ss58_address) and allocation_key_encoded:
            # Decode the base64-encoded public key from the file
            public_key = base64.b64decode(allocation_key_encoded).decode('utf-8')
            deregister_allocation(public_key)
            self.wandb.update_allocated(None)
            bt.logging.info("Allocation is not exist in wandb. Resetting the allocation status.")

        if check_container() and not allocation_key_encoded:
            kill_container()
            self.wandb.update_allocated(None)
            bt.logging.info("Container is already running without allocated. Killing the container.")

        self.request_specs_processor = RequestSpecsProcessor()

        self.last_updated_block = self.current_block - (self.current_block % 100)

    def init_axon(self):
        # Step 6: Build and link miner functions to the axon.
        # The axon handles request processing, allowing validators to send this process requests.
        self._axon = ComputeSubnetAxon(wallet=self.wallet, config=self.config)

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
        default_whitelist = self.config.whitelist_hotkeys + TRUSTED_VALIDATORS_HOTKEYS

        # Set blacklist and whitelist arrays
        self.blacklist_hotkeys = {hotkey for hotkey in self.config.blacklist_hotkeys}
        self.blacklist_coldkeys = {coldkey for coldkey in self.config.blacklist_coldkeys}
        self.whitelist_hotkeys = {hotkey for hotkey in default_whitelist}
        self.whitelist_coldkeys = {coldkey for coldkey in self.config.whitelist_coldkeys}

        if self.config.blacklist_exploiters:
            self.exploiters_hotkeys_set = {key for key in SUSPECTED_EXPLOITERS_HOTKEYS}
        else:
            self.exploiters_hotkeys_set = set()

    def sync_local(self):
        """Resync our local state with the latest state from the blockchain. Sync scores with metagraph."""
        self.metagraph.sync(subtensor=self.subtensor)

    def sync_status(self):
        self.miner_subnet_uid = is_registered(
            wallet=self.wallet,
            metagraph=self.metagraph,
            subtensor=self.subtensor,
            entity="miner",
        )

        # Check for auto update
        if self.config.auto_update:
            try_update()

        if hasattr(self, "axon"):
            if self.axon:
                # Check if the miner has the axon version info updated
                subnet_axon_version: bt.AxonInfo = self.metagraph.neurons[self.miner_subnet_uid].axon_info
                current_version = __version_as_int__
                if subnet_axon_version.version != current_version:
                    bt.logging.info("Axon info version has been changed. Needs to restart axon...")
                    self.axon.stop()
                    self.init_axon()

    def base_blacklist(self, synapse: typing.Union[Specs, Allocate, Challenge]) -> typing.Tuple[bool, str]:
        hotkey = synapse.dendrite.hotkey
        synapse_type = type(synapse).__name__

        if len(self.whitelist_hotkeys) > 0 and hotkey not in self.whitelist_hotkeys:
            bt.logging.trace(f"Not Blacklisting recognized hotkey {synapse.dendrite.hotkey}")
            return False, "Whitelisted hotkey"

        if hotkey not in self.metagraph.hotkeys:
            # Ignore requests from unrecognized entities.
            bt.logging.trace(f"Blacklisting unrecognized hotkey {hotkey}")
            return True, "Unrecognized hotkey"

        index = self.metagraph.hotkeys.index(hotkey)
        stake = self.metagraph.S[index].item()

        if stake < validator_permit_stake and not self.miner_whitelist_not_enough_stake:
            bt.logging.trace(f"Not enough stake {stake}")
            return True, "Not enough stake!"

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
        caller_uid = self._metagraph.hotkeys.index(synapse.dendrite.hotkey)  # Get the caller index.
        priority = float(self._metagraph.S[caller_uid])  # Return the stake as the priority.
        bt.logging.trace(f"Prioritizing {synapse.dendrite.hotkey} with value: ", priority)
        return priority

    # The blacklist function decides if a request should be ignored.
    def blacklist_specs(self, synapse: Specs) -> typing.Tuple[bool, str]:
        return self.base_blacklist(synapse)

    # The priority function determines the order in which requests are handled.
    # More valuable or higher-priority requests are processed before others.
    def priority_specs(self, synapse: Specs) -> float:
        return self.base_priority(synapse) + miner_priority_specs

    # This is the PerfInfo function, which decides the miner's response to a valid, high-priority request.
    def specs(self, synapse: Specs) -> Specs:
        app_data = synapse.specs_input
        synapse.specs_output = self.request_specs_processor.get_respond(app_data)
        return synapse

    # The blacklist function decides if a request should be ignored.
    def blacklist_allocate(self, synapse: Allocate) -> typing.Tuple[bool, str]:
        return self.base_blacklist(synapse)

    # The priority function determines the order in which requests are handled.
    # More valuable or higher-priority requests are processed before others.
    def priority_allocate(self, synapse: Allocate) -> float:
        return self.base_priority(synapse) + miner_priority_allocate

    def update_allocation(self, synapse: Allocate):
        if not synapse.checking and isinstance(synapse.output, dict) and synapse.output.get("status") is True:
            if synapse.timeline > 0:
                self.wandb.update_allocated(synapse.dendrite.hotkey)
                bt.logging.success(f"Allocation made by {synapse.dendrite.hotkey}.")
            else:
                self.wandb.update_allocated(None)
                bt.logging.success(f"De-allocation made by {synapse.dendrite.hotkey}.")

    # This is the Allocate function, which decides the miner's response to a valid, high-priority request.
    def allocate(self, synapse: Allocate) -> Allocate:
        timeline = synapse.timeline
        device_requirement = synapse.device_requirement
        checking = synapse.checking
        docker_requirement = synapse.docker_requirement
        docker_requirement['ssh_port'] = int(self.config.ssh.port)

        if checking is True:
            if timeline > 0:
                result = check_allocation(timeline, device_requirement)
                synapse.output = result
            else:
                public_key = synapse.public_key
                result = check_if_allocated(public_key=public_key)
                synapse.output = result
        else:
            public_key = synapse.public_key
            if timeline > 0:
                result = register_allocation(timeline, device_requirement, public_key, docker_requirement)
                synapse.output = result
            else:
                result = deregister_allocation(public_key)
                synapse.output = result
        self.update_allocation(synapse)
        return synapse

    # The blacklist function decides if a request should be ignored.
    def blacklist_challenge(self, synapse: Challenge) -> typing.Tuple[bool, str]:
        return self.base_blacklist(synapse)

    # The priority function determines the order in which requests are handled.
    # More valuable or higher-priority requests are processed before others.
    def priority_challenge(self, synapse: Challenge) -> float:
        return self.base_priority(synapse) + miner_priority_challenge

    # This is the Challenge function, which decides the miner's response to a valid, high-priority request.
    def challenge(self, synapse: Challenge) -> Challenge:
        if synapse.challenge_difficulty <= 0:
            bt.logging.warning(f"{synapse.dendrite.hotkey}: Challenge received with a difficulty <= 0 - it can not be solved.")
            return synapse

        v_id = synapse.dendrite.hotkey[:8]
        run_id = f"{v_id}/{synapse.challenge_difficulty}/{synapse.challenge_hash[10:20]}"

        result = run_miner_pow(
            run_id=run_id,
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

    def get_updated_validator(self):
        try:
            self.whitelist_hotkeys_version.clear()
            try:
                latest_version = version2number(get_remote_version(pattern="__minimal_validator_version__"))

                if latest_version is None:
                    bt.logging.error(f"Github API call failed or version string is incorrect!")
                    return

                valid_validators = self.get_valid_validator()

                valid_validators_version = [uid for uid, hotkey, version in valid_validators if version >= latest_version]
                if percent(len(valid_validators_version), len(valid_validators)) <= self.miner_whitelist_updated_threshold:
                    bt.logging.info(f"Less than {self.miner_whitelist_updated_threshold}% validators are currently using the last version. Allowing all.")
                else:
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

    def get_valid_validator_uids(self):
        valid_uids = []
        uids = self.metagraph.uids.tolist()
        for index, uid in enumerate(uids):
            if self.metagraph.total_stake[index] > validator_permit_stake:
                valid_uids.append(uid)
        return valid_uids

    def get_valid_validator(self) -> typing.List[typing.Tuple[int, str, int]]:
        valid_validator_uids = self.get_valid_validator_uids()
        valid_validator = []
        for uid in valid_validator_uids:
            neuron = self.subtensor.neuron_for_uid(uid, self.config.netuid)
            hotkey = neuron.hotkey
            version = neuron.prometheus_info.version
            valid_validator.append((uid, hotkey, version))
        return valid_validator

    def next_info(self, cond, next_block):
        if cond:
            return calculate_next_block_time(self.current_block, next_block)
        else:
            return None

    async def start(self):
        """The Main Validation Loop"""

        block_next_updated_validator = self.current_block + 30
        block_next_updated_specs = self.current_block + 150
        block_next_sync_status = self.current_block + 25

        time_next_updated_validator = None
        time_next_sync_status = None

        bt.logging.info("Starting miner loop.")
        while True:
            try:
                self.sync_local()

                if self.current_block not in self.blocks_done:
                    self.blocks_done.add(self.current_block)

                    time_next_updated_validator = self.next_info(
                        not block_next_updated_validator == 1,
                        block_next_updated_validator,
                    )
                    time_next_sync_status = self.next_info(not block_next_sync_status == 1, block_next_sync_status)

                if self.current_block % block_next_updated_validator == 0 or block_next_updated_validator < self.current_block:
                    block_next_updated_validator = self.current_block + 30  # 30 ~ every 6 minutes
                    self.get_updated_validator()
                
                if self.current_block % block_next_updated_specs == 0 or block_next_updated_specs < self.current_block:
                    block_next_updated_specs = self.current_block + 150  # 150 ~ every 30 minutes
                    self.wandb.update_specs()               

                if self.current_block % block_next_sync_status == 0 or block_next_sync_status < self.current_block:
                    block_next_sync_status = self.current_block + 25  # 25 ~ every 5 minutes
                    self.sync_status()

                    # Log chain data to wandb
                    chain_data = {
                        "Block": self.current_block,
                        "Stake": float(self.metagraph.S[self.miner_subnet_uid]),
                        "Trust": float(self.metagraph.T[self.miner_subnet_uid]),
                        "Consensus": float(self.metagraph.C[self.miner_subnet_uid]),
                        "Incentive": float(self.metagraph.I[self.miner_subnet_uid]),
                        "Emission": float(self.metagraph.E[self.miner_subnet_uid]),
                    }
                    self.wandb.log_chain_data(chain_data)

                # Periodically clear some vars
                if len(self.blocks_done) > 1000:
                    self.blocks_done.clear()
                    self.blocks_done.add(self.current_block)

                bt.logging.info(
                    f"Block: {self.current_block} | "
                    f"Stake: {self.metagraph.S[self.miner_subnet_uid]:.4f} | "
                    f"Trust: {self.metagraph.T[self.miner_subnet_uid]:.4f} | "
                    f"Consensus: {self.metagraph.C[self.miner_subnet_uid]:.6f} | "
                    f"Incentive: {self.metagraph.I[self.miner_subnet_uid]:.6f} | "
                    f"Emission: {self.metagraph.E[self.miner_subnet_uid]:.6f} | "
                    f"update_validator: #{block_next_updated_validator} ~ {time_next_updated_validator} | "
                    f"sync_status: #{block_next_sync_status} ~ {time_next_sync_status}"
                )
                time.sleep(5)

            except (RuntimeError, Exception) as e:
                bt.logging.error(e)
                traceback.print_exc()

            # If the user interrupts the program, gracefully exit.
            except KeyboardInterrupt:
                self.axon.stop()
                bt.logging.success("Keyboard interrupt detected. Exiting miner.")
                exit()


def main():
    """
    Main function to run the miner.

    This function initializes and runs the miner. It handles the main loop, state management, and interaction
    with the Bittensor network.
    """
    miner = Miner()
    asyncio.run(miner.start())


if __name__ == "__main__":
    main()
