# The MIT License (MIT)
# Copyright © 2023

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

import os
import time
import torch
import argparse
import traceback
import bittensor as bt
import time
import tensorflow as tf
import compute
import Validator.complexity as cx
import Validator.database as db

# Step 2: Set up the configuration parser
# This function is responsible for setting up and parsing command-line arguments.
def get_config():

    parser = argparse.ArgumentParser()
    # TODO(developer): Adds your custom validator arguments to the parser.
    parser.add_argument('--custom', default='my_custom_value', help='Adds a custom value to the parser.')
    # Adds override arguments for network and netuid.
    parser.add_argument( '--netuid', type = int, default = 1, help = "The chain subnet uid." )
    # Adds subtensor specific arguments i.e. --subtensor.chain_endpoint ... --subtensor.network ...
    bt.subtensor.add_args(parser)
    # Adds logging specific arguments i.e. --logging.debug ..., --logging.trace .. or --logging.logging_dir ...
    bt.logging.add_args(parser)
    # Adds wallet specific arguments i.e. --wallet.name ..., --wallet.hotkey ./. or --wallet.path ...
    bt.wallet.add_args(parser)
    # Parse the config (will take command-line arguments if provided)
    # To print help message, run python3 template/miner.py --help
    config =  bt.config(parser)

    # Step 3: Set up logging directory
    # Logging is crucial for monitoring and debugging purposes.
    config.full_path = os.path.expanduser(
        "{}/{}/{}/netuid{}/{}".format(
            config.logging.logging_dir,
            config.wallet.name,
            config.wallet.hotkey,
            config.netuid,
            'validator',
        )
    )
    # Ensure the logging directory exists.
    if not os.path.exists(config.full_path): os.makedirs(config.full_path, exist_ok=True)

    # Return the parsed config.
    return config

def main( config ):
    # Set up logging with the provided configuration and directory.
    bt.logging(config=config, logging_dir=config.full_path)
    bt.logging.info(f"Running validator for subnet: {config.netuid} on network: {config.subtensor.chain_endpoint} with config:")
    # Log the configuration for reference.
    #bt.logging.info(config)

    # Step 4: Build Bittensor validator objects
    # These are core Bittensor classes to interact with the network.
    bt.logging.info("Setting up bittensor objects.")

    # The wallet holds the cryptographic key pairs for the validator.
    wallet = bt.wallet( config = config )
    bt.logging.info(f"Wallet: {wallet}")

    # The subtensor is our connection to the Bittensor blockchain.
    subtensor = bt.subtensor( config = config )
    bt.logging.info(f"Subtensor: {subtensor}")

    # Dendrite is the RPC client; it lets us send messages to other nodes (axons) in the network.
    dendrite = bt.dendrite( wallet = wallet )
    bt.logging.info(f"Dendrite: {dendrite}")

    # The metagraph holds the state of the network, letting us know about other miners.
    metagraph = subtensor.metagraph( config.netuid )
    bt.logging.info(f"Metagraph: {metagraph}")

    # Step 5: Connect the validator to the network
    if wallet.hotkey.ss58_address not in metagraph.hotkeys:
        bt.logging.error(f"\nYour validator: {wallet} if not registered to chain connection: {subtensor} \nRun btcli register and try again.")
        exit()
    else:
        # Each miner gets a unique identity (UID) in the network for differentiation.
        my_subnet_uid = metagraph.hotkeys.index(wallet.hotkey.ss58_address)
        bt.logging.info(f"Running validator on uid: {my_subnet_uid}")

    # Step 6: Set up initial scoring weights for validation
    bt.logging.info("Building validation weights.")
    alpha = 0.9
    scores = torch.ones_like(metagraph.S, dtype=torch.float32)

    # Step 7: The Main Validation Loop
    bt.logging.info("Starting validator loop.")
    step = 0
    while True:
        try:
            # TODO(developer): Define how the validator selects a miner to query, how often, etc.
            # Broadcast a query to all miners on the network.
            axons_list = metagraph.axons
            uid_list = [param.data.item() for param in metagraph.uids]
            if(step % 10 == 1):
                            
                #The responses of PerfInfo request
                perfInfo_responses = dendrite.query(
                    axons_list,
                    compute.protocol.PerfInfo(),
                    deserialize = True,
                    timeout = 5,
                )
                #Filter perfInfo_responses - remove empty responses
                perfInfo_responses = [obj for obj in perfInfo_responses if any(obj.values())]

                for i, perfInfo_i in enumerate(perfInfo_responses):
                    bt.logging.info(f"PerfInfo Response of Miner {perfInfo_i['id']} : {perfInfo_i}")
                
                #The count of string that will be sent to miner
                str_count = 5

                clarify_origin_dict = {}
                clarify_hashed_dict = {}
                
                for perfInfo in perfInfo_responses:
                    #Miner's id
                    miner_id = perfInfo['id']

                    #Calculate complexity based on the perfInfo
                    complexity = cx.calculate_complexity(perfInfo)

                    #Select str_count of strings with given complexity
                    str_list = db.select_str_list(str_count, complexity)

                    #Save the pair of given string and hashed string
                    clarify_origin_dict[miner_id] = {'complexity': complexity, 'str_list': str_list['origin']}
                    clarify_hashed_dict[miner_id] = {'complexity': complexity, 'str_list': str_list['hashed']}

                #The responses of clarify request
                clarify_responses = dendrite.query(
                    axons_list,
                    compute.protocol.Clarify(clarify_input=clarify_origin_dict),
                    deserialize = True,
                    timeout = 30, #Deadline
                )
                #Filter clarify_responses - remove empty respnoses
                clarify_responses = [obj for obj in clarify_responses if any(obj['output'].values())]
                for i, clarify_i in enumerate(clarify_responses):
                    bt.logging.info(f"Clarify Response of Miner {clarify_i['output']['id']} : {clarify_i}")
                
                #Calculate score based on the responses of perfInfo and clarify
                score_list = {}
                for clarify_i in clarify_responses:
                    #Calculation result of clarifying
                    output_i = clarify_i['output']

                    #Timmeout of clarify response
                    timeout = clarify_i['timeout']

                    #Miner's ID
                    id = output_i['id']

                    complexity = clarify_hashed_dict[id]['complexity']

                    bt.logging.info(f"Miner{id} : Clarify elapsed {timeout}s Complexity : {complexity}")

                    # Initialize the score for the current miner's response.
                    score = db.evaluate(clarify_hashed_dict[id], output_i['result'])

                    score_list[id] = score

                #Find the maximum score
                max_score = max(score_list)

                #Fill the score_list with 0 for no response miners
                for id in uid_list:
                    if id in score_list:
                        continue
                    score_list[id] = 0

                bt.logging.info(f"ScoreList:{score_list}")

                # Calculate score
                for id, score in enumerate(score_list):
                    index = uid_list.index(id)
                    # Update the global score of the miner.
                    # This score contributes to the miner's weight in the network.
                    # A higher weight means that the miner has been consistently responding correctly.
                    scores[index] = alpha * scores[index] + (1 - alpha) * score / max_score

            # Periodically update the weights on the Bittensor blockchain.
            if step > 1 and step % 50 == 1:
                # TODO(developer): Define how the validator normalizes scores before setting weights.
                weights = torch.nn.functional.normalize(scores, p=1.0, dim=0)
                for i, weight_i in enumerate(weights):
                    bt.logging.info(f"Weight of Miner{i + 1} : {weights[i]}")
                # This is a crucial step that updates the incentive mechanism on the Bittensor blockchain.
                # Miners with higher scores (or weights) receive a larger share of TAO rewards on this subnet.
                result = subtensor.set_weights(
                    netuid = config.netuid, # Subnet to set weights on.
                    wallet = wallet, # Wallet to sign set weights using hotkey.
                    uids = metagraph.uids, # Uids of the miners to set weights for.
                    weights = weights, # Weights to set for the miners.
                    wait_for_inclusion = True
                )
                if result: bt.logging.success('Successfully set weights.')
                else: bt.logging.error('Failed to set weights.') 

            # End the current step and prepare for the next iteration.
            step += 1
            # Resync our local state with the latest state from the blockchain.
            metagraph = subtensor.metagraph(config.netuid)
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
    main( config )