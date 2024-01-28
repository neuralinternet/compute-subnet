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
# Step 1: Import necessary libraries and modules


import argparse
import base64
import os

import bittensor as bt
import torch
import wandb

import RSAEncryption as rsa
from compute.protocol import Allocate
from compute.utils.db import ComputeDb
from neurons.Validator.database.allocate import select_allocate_miners_hotkey


# Step 2: Set up the configuration parser
# This function is responsible for setting up and parsing command-line arguments.
def get_config():
    parser = argparse.ArgumentParser()
    # Adds override arguments for network and netuid.
    parser.add_argument("--netuid", type=int, default=1, help="The chain subnet uid.")
    parser.add_argument("--gpu_type", type=str, default="", help="The type of GPU required.")
    parser.add_argument("--gpu_size", type=int, default=0, help="The capacity of GPU required in MB.")
    # Adds subtensor specific arguments i.e. --subtensor.chain_endpoint ... --subtensor.network ...
    bt.subtensor.add_args(parser)
    # Adds logging specific arguments i.e. --logging.debug ..., --logging.trace .. or --logging.logging_dir ...
    bt.logging.add_args(parser)
    # Adds wallet specific arguments i.e. --wallet.name ..., --wallet.hotkey ./. or --wallet.path ...
    bt.wallet.add_args(parser)
    # Parse the config (will take command-line arguments if provided)
    # To print help message, run python3 template/miner.py --help
    config = bt.config(parser)

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


# Generate ssh connection for given device requirements and timeline
def allocate(config, device_requirement, timeline, public_key):
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

    # Instantiate the connection to the db
    db = ComputeDb()

    # Find out the candidates
    candidates_hotkey = select_allocate_miners_hotkey(db, device_requirement)

    axon_candidates = []
    for axon in metagraph.axons:
        if axon.hotkey in candidates_hotkey:
            axon_candidates.append(axon)

    responses = dendrite.query(axon_candidates, Allocate(timeline=timeline, device_requirement=device_requirement, checking=True))

    final_candidates_hotkey = []

    for index, response in enumerate(responses):
        hotkey = axon_candidates[index].hotkey
        if response and response["status"] is True:
            final_candidates_hotkey.append(hotkey)

    # Check if there are candidates
    if len(final_candidates_hotkey) <= 0:
        return {"status": False, "msg": "No proper miner"}

    # Sort the candidates with their score
    scores = torch.ones_like(metagraph.S, dtype=torch.float32)

    score_dict = {hotkey: score for hotkey, score in zip([axon.hotkey for axon in metagraph.axons], scores)}
    sorted_hotkeys = sorted(final_candidates_hotkey, key=lambda hotkey: score_dict.get(hotkey, 0), reverse=True)

    # Loop the sorted candidates and check if one can allocate the device
    for hotkey in sorted_hotkeys:
        index = metagraph.hotkeys.index(hotkey)
        axon = metagraph.axons[index]
        register_response = dendrite.query(
            axon,
            Allocate(timeline=timeline, device_requirement=device_requirement, checking=False, public_key=public_key),
            timeout=120,
        )
        if register_response and register_response["status"] is True:
            register_response["ip"] = axon.ip
            register_response["hotkey"] = axon.hotkey
            return register_response

    # Close the db connection
    db.close()

    return {"status": False, "msg": "No proper miner"}


def main(config):
    device_requirement = {"cpu": {"count": 1}, "gpu": {}, "hard_disk": {"capacity": 1073741824}, "ram": {"capacity": 1073741824}}
    if config.gpu_type != "" and config.gpu_size != 0:
        device_requirement["gpu"] = {"count": 1, "capacity": config.gpu_size, "type": config.gpu_type}
    timeline = 60
    private_key, public_key = rsa.generate_key_pair()
    result = allocate(config, device_requirement, timeline, public_key)

    if result["status"] is True:
        result_hotkey = result["hotkey"]
        result_info = result["info"]
        private_key = private_key.encode("utf-8")
        decrypted_info = rsa.decrypt_data(private_key, base64.b64decode(result_info))
        upload_wandb(result_hotkey)
        bt.logging.info(f"Registered successfully : {decrypted_info}, 'ip':{result['ip']}")
    else:
        bt.logging.info(f"Failed : {result['msg']}")


def upload_wandb(hotkey):
    try:
        wandb.init(project="registered-miners", name="hotkeys")
        wandb.log({"key": hotkey})
    except Exception as e:
        bt.logging.info(f"Error uploading to wandb : {e}")
        return


# The main function parses the configuration and runs the validator.
if __name__ == "__main__":
    # Parse the configuration.
    config = get_config()
    # Run the main function.
    main(config)
