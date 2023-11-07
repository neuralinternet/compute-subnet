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

import os
import time
import torch
import argparse
import traceback
import json
import bittensor as bt
import compute
import Validator.app_generator as ag
import Validator.calculate_score as cs
import Validator.database as db
from cryptography.fernet import Fernet
import ast

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

#Generate ssh connection for given device requirements and timeline
def allocate (metagraph, dendrite, device_requirement, timeline):
    #Find out the candidates
    candidates_hotkey = db.select_miners_hotkey(device_requirement)

    axon_candidates = []
    for axon in metagraph.axons:
        if axon.hotkey in candidates_hotkey:
            axon_candidates.append(axon)

    allocate_responses = dendrite.query(
        axon_candidates,
        compute.protocol.Allocate(timeline = timeline, device_requirement = device_requirement, checking = True)
    )

    final_candidates_hotkey = []

    for index, allocate_response in enumerate(allocate_responses):
        if allocate_response and allocate_response['status'] == True:
            final_candidates_hotkey.append(axon_candidates[index].hotkey)
    
    #Check if there are candidates
    if final_candidates_hotkey == []:
        return {"status" : False, "msg" : "No proper miner"}
    
    #Sort the candidates with their score
    scores = torch.ones_like(metagraph.S, dtype=torch.float32)

    score_dict = {hotkey: score for hotkey, score in zip([axon.hotkey for axon in metagraph.axons], scores)}
    sorted_hotkeys = sorted(final_candidates_hotkey, key=lambda hotkey: score_dict.get(hotkey, 0), reverse=True)

    #Loop the sorted candidates and check if one can allocate the device
    for hotkey in sorted_hotkeys:
        index = metagraph.hotkeys.index(hotkey)
        axon = metagraph.axons[index]
        register_response = dendrite.query(
            axon,
            compute.protocol.Allocate(timeline = timeline, device_requirement = device_requirement, checking = False),
            timeout = 120,
        )
        if register_response and register_response['status'] == True:
            register_response.update({'ip' : axon.ip_str()})
            bt.logging.info(f"Registered : {register_response}")

            return register_response
        
    return {"status" : False, "msg" : "No proper miner"}

#Filter axons with ip address, remove axons with same ip address
def filter_axons_with_ip(axons_list):
    # Set to keep track of unique identifiers
    unique_ip_addresses = set()

    # List to store filtered axons
    filtered_axons = []

    for axon in axons_list:
        ip_address = axon.ip_str()

        if ip_address not in unique_ip_addresses:
            unique_ip_addresses.add(ip_address)
            filtered_axons.append(axon)

    return filtered_axons

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
            if step % 10 == 1:
                
                #Filter axons, remove duplicated ip address
                axons_list = metagraph.axons
                axons_list = filter_axons_with_ip(axons_list)

                #Generate secret key for app
                secret_key = Fernet.generate_key()
                cipher_suite = Fernet(secret_key)
                #Compile the script and generate an exe
                ag.run(secret_key)
                
                #Read the exe file and save it to app_data
                with open('neurons//Validator//dist//script', 'rb') as file:
                    # Read the entire content of the EXE file
                    app_data = file.read()
                
                #The responses of PerfInfo request
                ret_perfInfo_responses = dendrite.query(
                    axons_list,
                    compute.protocol.PerfInfo(perf_input = repr(app_data)),
                    timeout = 30
                )

                #Filter invalid responses
                perfInfo_responses = []
                hotkey_list = []
                for index, perfInfo in enumerate(ret_perfInfo_responses):
                    if perfInfo:
                        binary_data = ast.literal_eval(perfInfo) #Convert str to binary data
                        decoded_data = ast.literal_eval(cipher_suite.decrypt(binary_data).decode()) #Decrypt data and convert it to object
                        perfInfo_responses.append(decoded_data)
                        hotkey_list.append(axons_list[index].hotkey)

                bt.logging.info(f"PerfInfo : {perfInfo_responses}")

                db.update(hotkey_list, perfInfo_responses)
                
                #Make score_list based on the perf_info
                score_list = {}

                for index, perfInfo in enumerate(perfInfo_responses):
                    hotkey = hotkey_list[index] #hotkey of miner
                    score_list[hotkey] = cs.score(perfInfo)
                
                #Fill the score_list with 0 for no response miners
                for hotkey in metagraph.hotkeys:
                    if hotkey in score_list:
                        continue
                    score_list[hotkey] = 0

                #Find the maximum score
                max_score = score_list[max(score_list, key = score_list.get)]
                if max_score == 0:
                    max_score = 1

                bt.logging.info(f"ScoreList:{score_list}")

                # Calculate score
                for index, axon in enumerate(metagraph.axons):
                    score = score_list[axon.hotkey]
                    # Update the global score of the miner.
                    # This score contributes to the miner's weight in the network.
                    # A higher weight means that the miner has been consistently responding correctly.
                    scores[index] = alpha * scores[index] + (1 - alpha) * score / max_score

            if step % 10 == 2:
                device_requirement = {'cpu':{'count':3}, 'gpu':{'capacity':10737418240, 'capabilities':'all'}, 'hard_disk':{'capacity':32212254720}, 'ram':{'capacity':5368709120}}
                timeline = 5
                result = allocate(metagraph, dendrite, device_requirement, timeline)

            # Periodically update the weights on the Bittensor blockchain.
            if step > 1 and step % 50 == 1:
                # TODO(developer): Define how the validator normalizes scores before setting weights.
                weights = torch.nn.functional.normalize(scores, p=1.0, dim=0)
                for i, weight_i in enumerate(weights):
                    bt.logging.info(f"Weight of Miner{i + 1} : {weight_i}")
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