# The MIT License (MIT)
# Copyright © 2023 GitPhantomman
# Copyright © 2023 Rapiiidooo

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import json
import os
import traceback
import typing

import bittensor as bt
import time
import torch

import Miner.allocate as al
import Miner.performance as pf
import Miner.pow as p
import compute
from compute.protocol import PerfInfo, Allocate, Challenge
from compute.utils.parser import ComputeArgPaser
from compute.utils.subtensor import is_registered
from compute.utils.version import get_remote_version, check_hashcat_version, try_update, version2number

whitelist_args_hotkeys_set: set = set()
whitelist_version_hotkeys_set: set = set()
blacklist_args_hotkeys_set: set = set()
exploiters_hotkeys_set: set = set()


def get_config():
    global whitelist_args_hotkeys_set
    global whitelist_version_hotkeys_set

    # Step 1: Set up the configuration parser
    # This function initializes the necessary command-line arguments.
    parser = ComputeArgPaser(description="This script aims to help miners with the compute subnet.")
    # Adds override arguments for network and netuid.

    # Activating the parser to read any command-line inputs.
    config = bt.config(parser)

    if config.whitelist_hotkeys:
        for hotkey in config.whitelist_hotkeys:
            whitelist_args_hotkeys_set.add(hotkey)

    if config.blacklist_hotkeys:
        for hotkey in config.blacklist_hotkeys:
            blacklist_args_hotkeys_set.add(hotkey)

    if config.blacklist_exploiters:
        for key in compute.SUSPECTED_EXPLOITERS_HOTKEYS:
            exploiters_hotkeys_set.add(key)

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


def get_valid_queryable_uids(metagraph):
    uids = metagraph.uids.tolist()
    valid_uids = []
    for index, uid in enumerate(uids):
        if metagraph.total_stake[index]:
            valid_uids.append(uid)
    return valid_uids


def get_queryable_axons(metagraph):
    queryable_uids = get_valid_queryable_uids(metagraph)
    queryable_axons = {metagraph.uids.tolist().index(uid): metagraph.axons[metagraph.uids.tolist().index(uid)] for uid in queryable_uids}
    return queryable_axons


def get_valid_validator_uids(metagraph: bt.metagraph):
    uids = metagraph.uids.tolist()
    valid_uids = []
    for index, uid in enumerate(uids):
        if metagraph.total_stake[index] > compute.validator_permit_stake:
            valid_uids.append(uid)
    return valid_uids


def get_valid_validator(config, subtensor: bt.subtensor, metagraph: bt.metagraph):
    valid_validator_uids = get_valid_validator_uids(metagraph=metagraph)
    valid_validator = []
    for uid in valid_validator_uids:
        neuron = subtensor.neuron_for_uid(uid, config.netuid)
        hotkey = neuron.hotkey
        version = neuron.prometheus_info.version
        valid_validator.append((uid, hotkey, version))

    return valid_validator


def get_valid_hotkeys(config, subtensor: bt.subtensor, metagraph: bt.metagraph):
    whitelist_version_hotkeys_set.clear()
    try:
        latest_version = version2number(get_remote_version(pattern="__minimal_validator_version__"))

        if latest_version is None:
            bt.logging.error(f"Github API call failed or version string is incorrect!")
            return

        valid_validators = get_valid_validator(config=config, subtensor=subtensor, metagraph=metagraph)
        for uid, hotkey, version in valid_validators:
            try:
                if version >= latest_version:
                    bt.logging.debug(f"Version signature match for hotkey : {hotkey}")
                    whitelist_version_hotkeys_set.add(hotkey)
                    continue

                bt.logging.debug(f"Version signature mismatch for hotkey : {hotkey}")
            except Exception:
                bt.logging.error(f"exception in get_valid_hotkeys: {traceback.format_exc()}")

        bt.logging.info(f"Total valid validator hotkeys = {whitelist_version_hotkeys_set}")

    except json.JSONDecodeError:
        bt.logging.error(f"exception in get_valid_hotkeys: {traceback.format_exc()}")


def set_weights(config, subtensor, wallet, metagraph, miner_subnet_uid):
    chain_weights = torch.zeros(subtensor.subnetwork_n(netuid=config.netuid))
    chain_weights[miner_subnet_uid] = 1
    # This is a crucial step that updates the incentive mechanism on the Bittensor blockchain.
    # Miners with higher scores (or weights) receive a larger share of TAO rewards on this subnet.
    result = subtensor.set_weights(
        netuid=config.netuid,  # Subnet to set weights on.
        wallet=wallet,  # Wallet to sign set weights using hotkey.
        uids=metagraph.uids,  # Uids of the miners to set weights for.
        weights=chain_weights,  # Weights to set for the miners.
        version_key=compute.__version_as_int__,
        wait_for_inclusion=False,
    )
    if result:
        bt.logging.success("Successfully set weights.")
    else:
        bt.logging.error("Failed to set weights.")


# Main takes the config and starts the miner.
def main(config):
    # Activating Bittensor's logging with the set configurations.
    bt.logging(config=config, logging_dir=config.full_path)
    bt.logging.info(f"Running miner for subnet: {config.netuid} on network: {config.subtensor.chain_endpoint} with config:")

    # This logs the active configuration to the specified logging directory for review.
    # bt.logging.info(config)

    # Step 4: Initialize Bittensor miner objects
    # These classes are vital to interact and function within the Bittensor network.
    bt.logging.info("Setting up bittensor objects.")

    # Wallet holds cryptographic information, ensuring secure transactions and communication.
    wallet = bt.wallet(config=config)
    bt.logging.info(f"Wallet: {wallet}")

    # subtensor manages the blockchain connection, facilitating interaction with the Bittensor blockchain.
    subtensor = bt.subtensor(config=config)
    bt.logging.info(f"Subtensor: {subtensor}")

    # metagraph provides the network's current state, holding state about other participants in a subnet.
    metagraph = subtensor.metagraph(config.netuid)
    bt.logging.info(f"Metagraph: {metagraph}")

    # Allow validators that are not permitted by stake
    miner_whitelist_not_enough_stake = config.miner_whitelist_not_enough_stake

    miner_subnet_uid = is_registered(wallet=wallet, metagraph=metagraph, subtensor=subtensor, entity="miner")
    bt.logging.info(f"Running miner on uid: {miner_subnet_uid}")

    p.check_cuda_availability()

    hashcat_path = config.miner_hashcat_path
    hashcat_workload_profile = config.miner_hashcat_workload_profile
    hashcat_extended_options = config.miner_hashcat_extended_options

    check_hashcat_version(hashcat_path=hashcat_path)

    current_block = subtensor.block
    last_updated_block = current_block - (current_block % 100)

    # Step 5: Set up miner functionalities
    # The following functions control the miner's response to incoming requests.
    def base_blacklist(synapse: typing.Union[PerfInfo, Allocate, Challenge]) -> typing.Tuple[bool, str]:
        hotkey = synapse.dendrite.hotkey
        synapse_type = type(synapse).__name__

        if hotkey not in metagraph.hotkeys:
            # Ignore requests from unrecognized entities.
            bt.logging.trace(f"Blacklisting unrecognized hotkey {hotkey}")
            return True, "Unrecognized hotkey"

        index = metagraph.hotkeys.index(hotkey)
        stake = metagraph.S[index].item()

        if stake < compute.validator_permit_stake and not miner_whitelist_not_enough_stake:
            bt.logging.trace(f"Not enough stake {stake}")
            return True, "Not enough stake!"

        if len(whitelist_args_hotkeys_set) > 0 and hotkey not in whitelist_args_hotkeys_set:
            return True, "Not whitelisted"

        if len(blacklist_args_hotkeys_set) > 0 and hotkey in blacklist_args_hotkeys_set:
            return True, "Blacklisted hotkey"

        # Blacklist entities that are not up-to-date
        if hotkey not in whitelist_version_hotkeys_set and len(whitelist_version_hotkeys_set) > 0:
            return (
                True,
                f"Blacklisted a {synapse_type} request from a non-updated hotkey: {hotkey}",
            )

        if hotkey in exploiters_hotkeys_set:
            return (
                True,
                f"Blacklisted a {synapse_type} request from an exploiter hotkey: {hotkey}",
            )

        bt.logging.trace(f"Not Blacklisting recognized hotkey {synapse.dendrite.hotkey}")
        return False, "Hotkey recognized!"

    def base_priority(synapse: typing.Union[PerfInfo, Allocate, Challenge]) -> float:
        caller_uid = metagraph.hotkeys.index(synapse.dendrite.hotkey)  # Get the caller index.
        priority = float(metagraph.S[caller_uid])  # Return the stake as the priority.
        bt.logging.trace(f"Prioritizing {synapse.dendrite.hotkey} with value: ", priority)
        return priority

    # The blacklist function decides if a request should be ignored.
    def blacklist_perfInfo(synapse: PerfInfo) -> typing.Tuple[bool, str]:
        return base_blacklist(synapse)

    # The priority function determines the order in which requests are handled.
    # More valuable or higher-priority requests are processed before others.
    def priority_perfInfo(synapse: PerfInfo) -> float:
        return base_priority(synapse) + compute.miner_priority_perfinfo

    # This is the PerfInfo function, which decides the miner's response to a valid, high-priority request.
    def perfInfo(synapse: PerfInfo) -> PerfInfo:
        app_data = synapse.perf_input
        synapse.perf_output = pf.get_respond(app_data)
        return synapse

    # The blacklist function decides if a request should be ignored.
    def blacklist_allocate(synapse: Allocate) -> typing.Tuple[bool, str]:
        return base_blacklist(synapse)

    # The priority function determines the order in which requests are handled.
    # More valuable or higher-priority requests are processed before others.
    def priority_allocate(synapse: Allocate) -> float:
        return base_priority(synapse) + compute.miner_priority_allocate

    # This is the Allocate function, which decides the miner's response to a valid, high-priority request.
    def allocate(synapse: Allocate) -> Allocate:
        timeline = synapse.timeline
        device_requirement = synapse.device_requirement
        checking = synapse.checking

        result = True
        if checking == True:
            result = al.check(timeline, device_requirement)
            synapse.output = result
        else:
            public_key = synapse.public_key
            result = al.register(timeline, device_requirement, public_key)
            synapse.output = result
        return synapse

    # The blacklist function decides if a request should be ignored.
    def blacklist_challenge(synapse: Challenge) -> typing.Tuple[bool, str]:
        return base_blacklist(synapse)

    # The priority function determines the order in which requests are handled.
    # More valuable or higher-priority requests are processed before others.
    def priority_challenge(synapse: Challenge) -> float:
        return base_priority(synapse) + compute.miner_priority_challenge

    # This is the Challenge function, which decides the miner's response to a valid, high-priority request.
    def challenge(synapse: Challenge) -> Challenge:
        bt.logging.info(f"Received challenge (hash, salt): ({synapse.challenge_hash}, {synapse.challenge_salt})")
        result = p.run_miner_pow(
            _hash=synapse.challenge_hash,
            salt=synapse.challenge_salt,
            mode=synapse.challenge_mode,
            chars=synapse.challenge_chars,
            mask=synapse.challenge_mask,
            hashcat_path=hashcat_path,
            hashcat_workload_profile=hashcat_workload_profile,
            hashcat_extended_options=hashcat_extended_options,
        )
        synapse.output = result
        return synapse

    # Step 6: Build and link miner functions to the axon.
    # The axon handles request processing, allowing validators to send this process requests.
    axon = bt.axon(wallet=wallet, config=config)
    bt.logging.info(f"Axon {axon}")

    # Attach determiners which functions are called when servicing a request.
    bt.logging.info(f"Attaching forward function to axon.")
    axon.attach(
        forward_fn=allocate,
        blacklist_fn=blacklist_allocate,
        priority_fn=priority_allocate,
    ).attach(
        forward_fn=challenge,
        blacklist_fn=blacklist_challenge,
        priority_fn=priority_challenge,
    ).attach(
        forward_fn=perfInfo,
        blacklist_fn=blacklist_perfInfo,
        priority_fn=priority_perfInfo,
    )

    # Serve passes the axon information to the network + netuid we are hosting on.
    # This will auto-update if the axon port of external ip have changed.
    bt.logging.info(f"Serving axon {perfInfo, allocate, challenge} on network: {config.subtensor.chain_endpoint} with netuid: {config.netuid}")
    axon.serve(netuid=config.netuid, subtensor=subtensor)

    # Start  starts the miner's axon, making it active on the network.
    bt.logging.info(f"Starting axon server on port: {config.axon.port}")
    axon.start()

    # This loop maintains the miner's operations until intentionally stopped.
    bt.logging.info(f"Starting main loop")
    step = 0
    while True:
        try:
            current_block = subtensor.block

            # Periodically update our knowledge of the network graph.
            if step % 5 == 0:
                metagraph.sync(subtensor=subtensor)

                log = (
                    f"Step:{step} | "
                    f"Block:{metagraph.block.item()} | "
                    f"Stake:{metagraph.S[miner_subnet_uid]} | "
                    f"Rank:{metagraph.R[miner_subnet_uid]} | "
                    f"Trust:{metagraph.T[miner_subnet_uid]} | "
                    f"Consensus:{metagraph.C[miner_subnet_uid] } | "
                    f"Incentive:{metagraph.I[miner_subnet_uid]} | "
                    f"Emission:{metagraph.E[miner_subnet_uid]}"
                )
                bt.logging.info(log)

            if step % compute.miner_whitelist_validator_steps_for == 0:
                get_valid_hotkeys(config=config, subtensor=subtensor, metagraph=metagraph)

            # Check for auto update
            if step % 100 == 0 and config.auto_update == "yes":
                try_update()

            # Ensure miner is still active, ~ every 20 minutes
            if current_block - last_updated_block > compute.weights_rate_limit:
                set_weights(config=config, subtensor=subtensor, wallet=wallet, metagraph=metagraph, miner_subnet_uid=miner_subnet_uid)
                last_updated_block = current_block

            step += 1
            time.sleep(1)

        # If someone intentionally stops the miner, it'll safely terminate operations.
        except KeyboardInterrupt:
            axon.stop()
            bt.logging.success("Miner killed by keyboard interrupt.")
            break
        # In case of unforeseen errors, the miner will log the error and continue operations.
        except Exception as e:
            bt.logging.error(traceback.format_exc())
            continue


# This is the main function, which runs the miner.
if __name__ == "__main__":
    main(get_config())
