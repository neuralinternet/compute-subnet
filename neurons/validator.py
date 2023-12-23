# The MIT License (MIT)
# Copyright © 2023 Crazydevlegend

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

# Step 1: Import necessary libraries and modules

import argparse
import ast
import concurrent.futures
import json
import os
import sys
import time
import traceback

import bittensor as bt
import torch

import compute
from Validator import basic_pow as bp, calculate_score as cs, database as db

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

blacklisted_hotkeys_set: set = set()
blacklisted_coldkeys_set: set = set()

SUSPECTED_MALICIOUS_COLDKEYS = []
SUSPECTED_MALICIOUS_HOTKEYS = [
    "5HZ1ATsziEMDm1iUqNWQatfEDb1JSNf37AiG8s3X4pZzoP3A",
    "5H679r89XawDrMhwKGH1jgWMZQ5eeJ8RM9SvUmwCBkNPvSCL",
    "5FnMHpqYo1MfgFLax6ZTkzCZNrBJRjoWE5hP35QJEGdZU6ft",
    "5H3tiwVEdqy9AkQSLxYaMewwZWDi4PNNGxzKsovRPUuuvALW",
    "5E6oa5hS7a6udd9LUUsbBkvzeiWDCgyA2kGdj6cXMFdjB7mm",
    "5DFaj2o2R4LMZ2zURhqEeFKXvwbBbAPSPP7EdoErYc94ATP1",
    "5H3padRmkFMJqZQA8HRBZUkYY5aKCTQzoR8NwqDfWFdTEtky",
    "5HBqT3dhKWyHEAFDENsSCBJ1ntyRdyEDQWhZo1JKgMSrAhUv",
    "5FAH7UesJRwwLMkVVknW1rsh9MQMUo78d5Qyx3KpFpL5A7LW",
    "5GUJBJmSJtKPbPtUgALn4h34Ydc1tjrNfD1CT4akvcZTz1gE",
    "5E2RkNBMCrdfgpnXHuiC22osAxiw6fSgZ1iEVLqWMXSpSKac",
    "5DaLy2qQRNsmbutQ7Havj49CoZSKksQSRkCLJsiknH8GcsN2",
    "5GNNB5kZfo6F9hqwXvaRfYdTuJPSzrXbtABzwoL499jPNBjt",
    "5GVjcJLQboN5NcQoP4x8oqovjAiEizdscoocWo9HBYYmPdR3",
    "5FswTe5bbs9n1SzaGpzUd6sDfnzdPfWVS2MwDWNbAneeT15k",
    "5F4bqDZkx79hCxmbbsVMuq312EW9hQLvsBzKsAJgcEqpb8L9",
]


def parse_list(input_string):
    """Very temporary TODO move to utils."""
    return ast.literal_eval(input_string)


# Step 2: Set up the configuration parser
# This function is responsible for setting up and parsing command-line arguments.
def get_config():
    parser = argparse.ArgumentParser()
    # Adds override arguments for network and netuid.
    parser.add_argument("--netuid", type=int, default=1, help="The chain subnet uid.")
    parser.add_argument("--auto_update", default="yes", help="Auto update")
    parser.add_argument(
        "--blacklist.suspected.hotkeys",
        dest="blacklist_suspected_hotkeys",
        default=True,
        action="store_true",
        help="Automatically use the list of internal suspected hotkeys.",
    )
    parser.add_argument(
        "--blacklisted.hotkeys",
        type=parse_list,
        dest="blacklisted_hotkeys",
        help="The list of the blacklisted hotkeys int the following format: \"['hotkey_x', '...']\"",
        default=[],
    )
    parser.add_argument(
        "--blacklist.suspected.coldkeys",
        dest="blacklist_suspected_coldkeys",
        default=True,
        action="store_true",
        help="Automatically use the list of internal suspected hotkeys.",
    )
    parser.add_argument(
        "--blacklisted.coldkeys",
        type=parse_list,
        dest="blacklisted_coldkeys",
        help="The list of the blacklisted coldkeys int the following format: \"['coldkeys_x', '...']\"",
        default=[],
    )

    # Adds subtensor specific arguments i.e. --subtensor.chain_endpoint ... --subtensor.network ...
    bt.subtensor.add_args(parser)
    # Adds logging specific arguments i.e. --logging.debug ..., --logging.trace .. or --logging.logging_dir ...
    bt.logging.add_args(parser)
    # Adds wallet specific arguments i.e. --wallet.name ..., --wallet.hotkey ./. or --wallet.path ...
    bt.wallet.add_args(parser)
    # Parse the config (will take command-line arguments if provided)
    config = bt.config(parser)

    if config.blacklist_suspected_hotkeys:
        for blacklisted_hotkey in SUSPECTED_MALICIOUS_HOTKEYS:
            config.blacklisted_hotkeys.append(blacklisted_hotkey)

    if config.blacklisted_coldkeys:
        for blacklisted_hotkey in SUSPECTED_MALICIOUS_COLDKEYS:
            config.blacklisted_hotkeys.append(blacklisted_hotkey)

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


# Filter the axons with uids_list, remove those with the same IP address.
def filter_axons(queryable_axons, queryable_uids):
    # Set to keep track of unique identifiers
    valid_ip_addresses = set()

    # List to store filtered axons
    filtered_uid_axons_dict = dict()
    for index, axon in enumerate(queryable_axons):
        ip_address = axon.ip

        if ip_address not in valid_ip_addresses:
            valid_ip_addresses.add(ip_address)
            filtered_uid_axons_dict[queryable_uids[index]] = axon

    return filtered_uid_axons_dict


def is_blacklisted(neuron):
    coldkey = neuron.axon_info.coldkey
    hotkey = neuron.axon_info.hotkey

    # Blacklist coldkeys that are blacklisted by user
    if coldkey in blacklisted_coldkeys_set:
        bt.logging.debug(f"Blacklisted recognized coldkey {coldkey} - with hotkey: {hotkey}")
        return True

    # Blacklist coldkeys that are blacklisted by user or by set of hotkeys
    if hotkey in blacklisted_hotkeys_set:
        bt.logging.debug(f"Blacklisted recognized hotkey {hotkey}")
        # Add the coldkey attached to this hotkey in the blacklisted coldkeys
        blacklisted_coldkeys_set.add(coldkey)
        return True


def get_valid_queryable_uids(metagraph, uids):
    valid_uids = []
    for index, uid in enumerate(uids):
        neuron = metagraph.neurons[uid]

        if neuron.axon_info.ip != "0.0.0.0" and metagraph.total_stake[index] < 1.024e3 and not is_blacklisted(neuron=neuron):
            valid_uids.append(uid)

    return valid_uids


def get_valid_tensors(metagraph):
    tensors = []
    for uid in metagraph.uids:
        neuron = metagraph.neurons[uid]

        if neuron.axon_info.ip != "0.0.0.0" and not is_blacklisted(neuron=neuron):
            tensors.append(True)
        else:
            tensors.append(False)

    return tensors


def main(config):
    global blacklisted_hotkeys_set
    global blacklisted_coldkeys_set

    # Set up logging with the provided configuration and directory.
    bt.logging(config=config, logging_dir=config.full_path)
    bt.logging.info(f"Running validator for subnet: {config.netuid} on network: {config.subtensor.chain_endpoint} with config:")
    # Log the configuration for reference.
    bt.logging.info(config)

    # Step 4: Build Bittensor validator objects
    # These are core Bittensor classes to interact with the network.
    bt.logging.info("Setting up bittensor objects.")

    # The wallet holds the cryptographic key pairs for the validator.
    wallet = bt.wallet(config=config)
    bt.logging.info(f"Wallet: {wallet}")

    # The subtensor is our connection to the Bittensor blockchain.
    subtensor = bt.subtensor(config=config)
    bt.logging.info(f"Subtensor: {subtensor}")

    # Dendrite is the RPC client; it lets us send messages to other nodes (axons) in the network.
    dendrite = bt.dendrite(wallet=wallet)
    bt.logging.info(f"Dendrite: {dendrite}")

    # The metagraph holds the state of the network, letting us know about other miners.
    metagraph = subtensor.metagraph(config.netuid)
    bt.logging.info(f"Metagraph: {metagraph}")

    # Optimize the blacklist list
    blacklisted_hotkeys_set = {blacklisted_hotkey for blacklisted_hotkey in config.blacklisted_hotkeys}
    blacklisted_coldkeys_set = {blacklisted_coldkey for blacklisted_coldkey in config.blacklisted_coldkeys}

    # Step 5: Connect the validator to the network
    # TODO UNCOMMENT THIS WHEN PROD - THIS IS COMMENTED FOR TESTING PURPOSE ONLY
    # if wallet.hotkey.ss58_address not in metagraph.hotkeys:
    #     bt.logging.error(f"\nYour validator: {wallet} is not registered to chain connection: {subtensor} \nRun btcli register and try again.")
    #     exit()
    # else:
    #     # Each miner gets a unique identity (UID) in the network for differentiation.
    #     my_subnet_uid = metagraph.hotkeys.index(wallet.hotkey.ss58_address)
    #     bt.logging.info(f"Running validator on uid: {my_subnet_uid}")

    # Step 6: Set up initial scoring weights for validation
    bt.logging.info("Building validation weights.")

    # Initialize alpha
    alpha = 0.9

    # Initialize weights, difficulties for each miner, and store current uids.
    last_uids_list = metagraph.uids.tolist()
    scores = torch.zeros(len(last_uids_list), dtype=torch.float32)
    difficulties = torch.zeros(len(last_uids_list), dtype=torch.int8)
    difficulties[difficulties == 0] = 1
    default_dict = {
        "axon": None,
        "header": None,
        "difficulty": None,
        "score": None,
        "synapse": None,
        "response": None,
        "challenge_output": None,
        "time_elapsed": None,
        "verified": None,
    }
    last_uids_dict = {uid: default_dict for uid in last_uids_list}

    curr_block = subtensor.block
    last_updated_block = curr_block - (curr_block % 100)

    new_uids = []
    new_uids_dict = {}
    # Step 7: The Main Validation Loop
    bt.logging.info("Starting validator loop.")
    step = 0
    while True:
        try:
            if step % 5 == 0:
                # Sync the subtensor state with the blockchain.
                bt.logging.info(f"🔄 Syncing metagraph with subtensor.")

                # Resync our local state with the latest state from the blockchain.
                metagraph = subtensor.metagraph(config.netuid)

                # Sync scores with metagraph
                # Get the current uids of all miners in the network.
                new_uids = metagraph.uids.tolist()
                new_uids_dict = {uid: default_dict for uid in new_uids}

                # Create new_scores with current metagraph
                new_scores = torch.zeros(len(new_uids), dtype=torch.float32)
                new_difficulties = torch.zeros(len(last_uids_list), dtype=torch.int8)
                new_difficulties[new_difficulties == 0] = 1

                for uid in last_uids_dict:
                    try:
                        new_scores[uid] = scores[uid]

                        # Increase or decrease the difficulty on some conditions
                        verified = last_uids_dict[uid].get("verified")
                        time_elapsed = last_uids_dict[uid].get("time_elapsed")
                        difficulty = last_uids_dict[uid].get("difficulty")
                        if verified is True and time_elapsed < compute.pow_timeout / 2:
                            new_difficulties[uid] = difficulty + 1
                        elif last_uids_dict[uid].get("verified") is True:
                            new_difficulties[uid] = difficulty
                        elif last_uids_dict[uid].get("verified") is False and difficulty > 1:
                            new_difficulties[uid] = difficulty - 1
                        else:
                            new_difficulties[uid] = difficulties[uid]
                    except KeyError:
                        # New node
                        new_scores[uid] = 0

                last_uids_dict = new_uids_dict

                # Set the weights of validators to zero.
                scores = new_scores * (metagraph.total_stake < 1.024e3)
                # Set the weight to zero for all nodes without assigned IP addresses.
                scores = scores * torch.Tensor(get_valid_tensors(metagraph=metagraph))

                bt.logging.info(f"🔢 Initialized scores : {scores.tolist()}")

            if step % 10 == 0:
                # Filter axons with stake and ip address.
                queryable_uids = get_valid_queryable_uids(metagraph, new_uids)
                queryable_axons = [metagraph.axons[metagraph.uids.tolist().index(uid)] for uid in queryable_uids]
                filtered_uid_axons_dict = filter_axons(queryable_axons=queryable_axons, queryable_uids=queryable_uids)

                bt.logging.info(f"🔢 PoW challenge generation.")
                for uid in new_uids_dict:
                    header = bp.gen_proof_of_work(uid)
                    challenge_input = {"header": header, "difficulty": new_uids_dict[uid]["difficulty"]}
                    new_uids_dict[uid]["headers"] = header
                    new_uids_dict[uid]["synapse"] = compute.protocol.Challenge(challenge_input=json.dumps(challenge_input))

                def perform_query(_axon, _synapse):
                    start_time = time.time()  # Record the start time of the query
                    response = dendrite.query(_axon, _synapse, timeout=compute.pow_timeout)
                    end_time = time.time()  # Record the time upon receiving the response
                    response_time = end_time - start_time  # Calculate the response time
                    return _axon.uid, response, response_time  # Return the uid, response, and response time

                # Query the miners for benchmarking using a ThreadPoolExecutor to execute the calls in parallel
                bt.logging.info(f"🆔 Benchmarking uids : {filtered_uid_axons_dict.keys()}")
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    # Launch asynchronous calls to dendrite.query for each axon in the list
                    futures = {executor.submit(perform_query, axon, new_uids_dict[uid].get("synapse")): axon for uid, axon in filtered_uid_axons_dict.items()}

                    # Retrieve the results once the calls are completed
                    for future in concurrent.futures.as_completed(futures):
                        axon = futures[future]
                        try:
                            axon_uid, result, time_elapsed = future.result()
                            challenge_output = result.challenge_output
                            new_uids_dict[axon_uid]["response"] = result
                            new_uids_dict[axon_uid]["challenge_output"] = challenge_output
                            new_uids_dict[axon_uid]["time_elapsed"] = time_elapsed
                            bp.verify_hash(
                                header=new_uids_dict[axon_uid].get("header"),
                                nonce=challenge_output,
                                target_difficulty=new_uids_dict[axon_uid].get("difficulty"),
                            )
                        except Exception as e:
                            bt.logging.error(f"An error occurred for axon {axon}: {e}")

                benchmark_result = [(data["difficulty"], data["time_elapsed"], data["verified"]) for data in new_uids_dict.values()]
                bt.logging.info(f"✅ Benchmark results : {benchmark_result}")

                db.update(uids_details=new_uids_dict)

                # Calculate score
                for uid in metagraph.uids:
                    try:
                        score = cs.score(new_uids_dict[uid])
                        # Benchmark the new possible score obtainable to put a true score limit.
                        # score = min(score, 100)
                    except (ValueError, KeyError):
                        score = 0

                    # Update the global score of the miner.
                    # This score contributes to the miner's weight in the network.
                    # A higher weight means that the miner has been consistently responding correctly.
                    scores[uid] = alpha * scores[uid] + (1 - alpha) * score
                    new_uids_dict[uid]["score"] = scores[uid].item()

                score_result = [(uid, data["score"]) for uid, data in new_uids_dict.items()]
                bt.logging.info(f"🔢 Updated scores : {score_result}")

            if step % 15 == 0:
                # Check for auto update
                if config.auto_update == "yes":
                    compute.util.try_update()

            # Periodically update the weights on the Bittensor blockchain.
            current_block = subtensor.block
            if current_block - last_updated_block > 100:
                weights = torch.nn.functional.normalize(scores, p=1.0, dim=0)
                bt.logging.info(f"🏋️ Weight of miners : {weights.tolist()}")
                # This is a crucial step that updates the incentive mechanism on the Bittensor blockchain.
                # Miners with higher scores (or weights) receive a larger share of TAO rewards on this subnet.
                result = subtensor.set_weights(
                    netuid=config.netuid,  # Subnet to set weights on.
                    wallet=wallet,  # Wallet to sign set weights using hotkey.
                    uids=metagraph.uids,  # Uids of the miners to set weights for.
                    weights=weights,  # Weights to set for the miners.
                    wait_for_inclusion=False,
                )
                last_updated_block = current_block
                if result:
                    bt.logging.success("Successfully set weights.")
                else:
                    bt.logging.error("Failed to set weights.")

            # End the current step and prepare for the next iteration.
            step += 1
            # Sleep for a duration equivalent to the block time (i.e., time between successive blocks).
            time.sleep(bt.__blocktime__)

        # If we encounter an unexpected error, log it for debugging.
        except RuntimeError as e:
            bt.logging.error(e)
            traceback.print_exc()

        # If the user interrupts the program, gracefully exit.
        except KeyboardInterrupt:
            bt.logging.success("Keyboard interrupt detected. Exiting validator.")
            exit()


# The main function parses the configuration and runs the validator.
if __name__ == "__main__":
    # Parse the configuration.
    config = get_config()
    # Run the main function.
    main(config)
