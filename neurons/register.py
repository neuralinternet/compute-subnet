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
import pyfiglet
import json

import bittensor as bt
import torch
import time

import RSAEncryption as rsa
from compute.protocol import Allocate
from compute.utils.db import ComputeDb
from compute.wandb.wandb import ComputeWandb
from neurons.Validator.database.allocate import select_allocate_miners_hotkey, update_allocation_db, get_miner_details
from compute.utils.version import get_local_version

from compute.utils.db import ComputeDb


# Step 2a: Set up the configuration parser
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

# Step 2b: Option to set up the configuration via cli
# This function is responsible for setting up and parsing command-line arguments from interface
def get_config_cli():

    parser = argparse.ArgumentParser()
    # Adds bittensor specific arguments
    parser.add_argument("--netuid", type=int, default=27, help="The chain subnet uid.")
    parser.add_argument("--gpu_type", type=str, help="The GPU type.")
    parser.add_argument("--gpu_size", type=int, help="The GPU memory in GB.")
    bt.subtensor.add_args(parser)
    bt.logging.add_args(parser)
    bt.wallet.add_args(parser)
    
    # Parse the initial config to check for provided arguments
    config = bt.config(parser)

    # Prompt for GPU type and memory only if they are not provided
    if getattr(config, 'gpu_type', None) is None:
        config.gpu_type = input("Enter GPU type: ")
    if getattr(config, 'gpu_size', None) is None:
        gpu_size = int(input("Enter GPU memory in GB: "))
        config.gpu_size = gpu_size*1024

    # Set up logging directory
    config.full_path = os.path.expanduser(
        "{}/{}/{}/netuid{}/{}".format(
            config.logging.logging_dir,
            config.wallet.name,
            config.wallet.hotkey,
            config.netuid,
            "validator",
        )
    )
    if not os.path.exists(config.full_path):
        os.makedirs(config.full_path, exist_ok=True)

    return config


# Generate ssh connection for given device requirements and timeline
def allocate_container(config, device_requirement, timeline, public_key):
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
        return {"status": False, "msg": "Requested resource is not available."}

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
            timeout=60,
        )
        if register_response and register_response["status"] is True:
            register_response["ip"] = axon.ip
            register_response["hotkey"] = axon.hotkey
            return register_response

    # Close the db connection
    db.close()

    return {"status": False, "msg": "Requested resource is not available."}


# Generate ssh connection for given device requirements and timeline
def allocate_container_hotkey(config, hotkey, timeline, public_key):
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

    device_requirement = {"cpu": {"count": 1}, "gpu": {}, "hard_disk": {"capacity": 1073741824}, "ram": {"capacity": 1073741824}}
    device_requirement["gpu"] = {"count": 1, "capacity": config.gpu_size, "type": config.gpu_type}

    # Instantiate the connection to the db
    axon_candidate = []
    for axon in metagraph.axons:
        if axon.hotkey == hotkey:
            check_allocation = dendrite.query(
                axon,
                Allocate(timeline=timeline, device_requirement=device_requirement, checking=True),
                timeout=60,
                )
            if check_allocation  and check_allocation ["status"] is True:
                register_response = dendrite.query(
                    axon,
                    Allocate(timeline=timeline, device_requirement=device_requirement, checking=False, public_key=public_key),
                    timeout=60,
                    )
                if register_response and register_response["status"] is True:
                    register_response["ip"] = axon.ip
                    register_response["hotkey"] = axon.hotkey
                    return register_response

    return {"status": False, "msg": "Requested resource is not available."}


def allocate(wandb):
    config = get_config_cli()
    
    device_requirement = {"cpu": {"count": 1}, "gpu": {}, "hard_disk": {"capacity": 1073741824}, "ram": {"capacity": 1073741824}}
    if config.gpu_type != "" and config.gpu_size != 0:
        device_requirement["gpu"] = {"count": 1, "capacity": config.gpu_size, "type": config.gpu_type}
    timeline = 90
    private_key, public_key = rsa.generate_key_pair()
    result = allocate_container(config, device_requirement, timeline, public_key)

    if result["status"] is True:
        result_hotkey = result["hotkey"]
        result_info = result["info"]
        private_key = private_key.encode("utf-8")
        decrypted_info_str = rsa.decrypt_data(private_key, base64.b64decode(result_info))
        bt.logging.info(f"Registered successfully : {decrypted_info_str}, 'ip':{result['ip']}")

        # Iterate through the miner specs details to get gpu_name
        db = ComputeDb()
        specs_details = get_miner_details(db)
        for key, details in specs_details.items():
            if str(key) == str(result_hotkey) and details:
                try:
                    gpu_miner = details['gpu']
                    gpu_name = str(gpu_miner['details'][0]['name']).lower()
                    break
                except (KeyError, IndexError, TypeError):
                    gpu_name = "Invalid details"
            else:
                gpu_name = "No details available"

        info = json.loads(decrypted_info_str)
        info['ip'] = result['ip']
        info['resource'] = gpu_name
        info['regkey'] = public_key

        time.sleep(1)
        print("\nAllocation successfull! Details and access data:")
        print("-" * 100)  # Print a separator line
        print(f"Hotkey: {result_hotkey}")
        #print(f"Regkey: {info['regkey']}")
        print(f"Resource: {info['resource']}")
        print(f"Username: {info['username']}")
        print(f"Password: {info['password']}")
        print(f"Port: {info['port']}")
        print(f"IP: {info['ip']}")

        # Construct the SSH command
        ssh_command = f"ssh {info['username']}@{result['ip']} -p {info['port']}"
        #print("\nTo access this resource via SSH, use the following command:")
        print(ssh_command)
        print("-" * 100)  # Print a separator line

        update_allocation_db(result_hotkey,info,True)
        update_allocation_wandb(wandb)

    else:
        bt.logging.info(f"Failed : {result['msg']}")


def allocate_hotkey(wandb):
    # Get hotkey:
    hotkey = input("Enter the hotkey of the resource to allocate: ")

    config = get_config()
    
    timeline = 30
    private_key, public_key = rsa.generate_key_pair()
    result = allocate_container_hotkey(config, hotkey, timeline, public_key)

    # Iterate through the miner specs details to get gpu_name
    db = ComputeDb()
    specs_details = get_miner_details(db)
    for key, details in specs_details.items():
        if str(key) == str(hotkey) and details:
            try:
                gpu_miner = details['gpu']
                gpu_name = str(gpu_miner['details'][0]['name']).lower()
                break
            except (KeyError, IndexError, TypeError):
                gpu_name = "Invalid details"
        else:
            gpu_name = "No details available"

    if result["status"] is True:
        result_hotkey = result["hotkey"]
        result_info = result["info"]
        private_key = private_key.encode("utf-8")
        decrypted_info_str = rsa.decrypt_data(private_key, base64.b64decode(result_info))
        bt.logging.info(f"Registered successfully : {decrypted_info_str}, 'ip':{result['ip']}")

        info = json.loads(decrypted_info_str)
        info['ip'] = result['ip']
        info['resource'] = gpu_name
        info['regkey'] = public_key

        time.sleep(1)
        print("\nAllocation successfull! Details and access data:")
        print("-" * 100)  # Print a separator line
        print(f"Hotkey: {result_hotkey}")
        #print(f"Regkey: {info['regkey']}")
        print(f"Resource: {info['resource']}")
        print(f"Username: {info['username']}")
        print(f"Password: {info['password']}")
        print(f"Port: {info['port']}")
        print(f"IP: {info['ip']}")

        # Construct the SSH command
        ssh_command = f"ssh {info['username']}@{result['ip']} -p {info['port']}"
        #print("\nTo access this resource via SSH, use the following command:")
        print(ssh_command)
        print("-" * 100)  # Print a separator line

        update_allocation_db(result_hotkey,info,True)
        update_allocation_wandb(wandb)

    else:
        bt.logging.info(f"Failed : {result['msg']}")


def deallocate(wandb):
    # Get hotkey:
    hotkey = input("Enter the hotkey of the resource to de-allocate: ")

    config = get_config()

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

    wallet = bt.wallet(config=config)
    subtensor = bt.subtensor(config=config)
    bt.logging.info(f"Subtensor: {subtensor}")

    # Dendrite is the RPC client; it lets us send messages to other nodes (axons) in the network.
    dendrite = bt.dendrite(wallet=wallet)
    metagraph = subtensor.metagraph(config.netuid)

    # Instantiate the connection to the db
    db = ComputeDb()
    cursor = db.get_cursor()

    try:
        # Retrieve the allocation details for the given hotkey
        cursor.execute("SELECT details, hotkey FROM allocation WHERE hotkey = ?", (hotkey,))
        row = cursor.fetchone()

        if row:
            # Parse the JSON string in the 'details' column
            info = json.loads(row[0])
            result_hotkey = row[1]

            username = info['username']
            password = info['password']
            port = info['port']
            ip = info['ip']
            regkey = info['regkey']

            index = metagraph.hotkeys.index(hotkey)
            axon = metagraph.axons[index]
            deregister_response = dendrite.query(
                axon,
                Allocate(timeline=0, device_requirement="", checking=False, public_key=regkey),
                timeout=60,
            )
            if deregister_response and deregister_response["status"] is True:
                print("Resource de-allocated successfully.")
            else:
                print("No Response from axon server, Resource de-allocated successfully .")

            update_allocation_db(result_hotkey, info, False)
            update_allocation_wandb(wandb)

        else:
            print("No allocation details found for the provided hotkey.")

    except Exception as e:
        print(f"An error occurred during de-allocation: {e}")
    finally:
        cursor.close()
        db.close()

def list_allocations(wandb):
    # Instantiate the connection to the db
    db = ComputeDb()
    cursor = db.get_cursor()

    try:
        # Retrieve all records from the allocation table
        cursor.execute("SELECT id, hotkey, details FROM allocation")
        rows = cursor.fetchall()

        # ANSI escape code for blue text
        BLUE = '\033[94m'
        # ANSI escape code to reset to default text color
        RESET = '\033[0m'
        print("=" * 80)  # Print a separator line for the title
        print(f"{BLUE}LIST OF ALLOCATED RESOURCES{RESET}")
        print("=" * 80)  # Print a separator line for the title

        if not rows:
            print("No resources allocated. Allocate a resource with 'a'.")

        for row in rows:
            id, hotkey, details = row
            info = json.loads(details)

            print(f"ID: {id}")
            print(f"Hotkey: {hotkey}")
            #print(f"Regkey: {info['regkey']}")
            print(f"Resource: {info['resource']}")
            print(f"Username: {info['username']}")
            print(f"Password: {info['password']}")
            print(f"Port: {info['port']}")
            print(f"IP: {info['ip']}")
            ssh_command = f"ssh {info['username']}@{info['ip']} -p {info['port']}"
            print(ssh_command)
            print("-" * 80)  # Print a separator line

    except Exception as e:
        print(f"An error occurred while retrieving allocation details: {e}")
    finally:
        cursor.close()
        db.close()


def list_resources(wandb): 
    db = ComputeDb()

    specs_details = get_miner_details(db)

    # ANSI escape code for blue text
    BLUE = '\033[94m'
    # ANSI escape code to reset to default text color
    RESET = '\033[0m'
    print("=" * 80)  # Print a separator line for the title
    print(f"{BLUE}LIST OF RESOURCES ON COMPUTE SUBNET{RESET}")
    print("=" * 80)  # Print a separator line for the title

    # Define the column widths for alignment
    column_widths = [50, 25, 15, 11, 7, 10, 16, 8]

   # Print the header for the table
    headers = ['Hotkey', 'GPU Name', 'GPU Size (GB)', 'GPU Count', 'vCPUs', 'RAM (GB)', 'Hard Disk (GB)', 'Status']
    header_line = '|'.join(h.ljust(w) for h, w in zip(headers, column_widths))
    print('-' * len(header_line))
    print(header_line)

    # Print a line after the header
    print('-' * len(header_line))

    # Initialize a dictionary to keep track of GPU instances
    gpu_instances = {}
    total_gpu_counts = {}

    # Iterate through the miner specs details and print the table
    for hotkey, details in specs_details.items():
        if details:  # Check if details are not empty
            try:
                # Extract GPU details
                gpu_miner = details['gpu']
                gpu_capacity = "{:.2f}".format((gpu_miner['capacity']/1024))
                gpu_name = str(gpu_miner['details'][0]['name']).lower()
                gpu_count = gpu_miner['count']
                
                # Extract CPU details
                cpu_miner = details['cpu']
                cpu_count = cpu_miner['count']
                
                # Extract RAM details
                ram_miner = details['ram']
                ram = "{:.2f}".format(ram_miner['available']/1024.0**3)
                
                # Extract Hard Disk details
                hard_disk_miner = details['hard_disk']
                hard_disk = "{:.2f}".format(hard_disk_miner['free']/1024.0**3)
                
                # Update the GPU instances count
                gpu_key = (gpu_name, gpu_count)
                gpu_instances[gpu_key] = gpu_instances.get(gpu_key, 0) + 1
                total_gpu_counts[gpu_name] = total_gpu_counts.get(gpu_name, 0) + gpu_count

            except (KeyError, IndexError, TypeError):
                gpu_name = "Invalid details"
                gpu_capacity = "N/A"
                gpu_count = "N/A"
                cpu_count = "N/A"
                ram = "N/A"
                hard_disk = "N/A"
        else:
            gpu_name = "No details available"
            gpu_capacity = "N/A"
            gpu_count = "N/A"
            cpu_count = "N/A"
            ram = "N/A"
            hard_disk = "N/A"
        
        # Allocation status
        status = "N/A"
        allocated_hotkeys =  wandb.get_allocated_hotkeys([], False)
        
        if hotkey in allocated_hotkeys:
            status = "Res."
        else:
            status = "Avail."

        # Print the row with column separators
        row_data = [hotkey, gpu_name, gpu_capacity, gpu_count, cpu_count, ram, hard_disk, status]
        row_line = '|'.join(str(d).ljust(w) for d, w in zip(row_data, column_widths))
        print(row_line)

    # Print the summary table
    print("\nSUMMARY (Instances Count):")
    summary_headers = ['GPU Name', 'GPU Count', 'Instances Count']
    summary_header_line = '|'.join(h.ljust(w) for h, w in zip(summary_headers, [30, 10, 15]))
    print('-' * len(summary_header_line))
    print(summary_header_line)
    print('-' * len(summary_header_line))

    # Iterate through the GPU instances and print the summary
    for (gpu_name, gpu_count), instances_count in gpu_instances.items():
        summary_data = [gpu_name, gpu_count, instances_count]
        summary_line = '|'.join(str(d).ljust(w) for d, w in zip(summary_data, [30, 10, 15]))
        print(summary_line)
        
    # Print the summary table for total GPU counts
    print("\nSUMMARY (Total GPU Counts):")
    summary_headers = ['GPU Name', 'Total GPU Count']
    summary_header_line = '|'.join(h.ljust(w) for h, w in zip(summary_headers, [30, 15]))
    print('-' * len(summary_header_line))
    print(summary_header_line)
    print('-' * len(summary_header_line))

    # Iterate through the total GPU counts and print the summary
    for gpu_name, total_count in total_gpu_counts.items():
        summary_data = [gpu_name, total_count]
        summary_line = '|'.join(str(d).ljust(w) for d, w in zip(summary_data, [30, 15]))
        print(summary_line)

def update_allocation_wandb(wandb):
    hotkey_list = []
    
    # Instantiate the connection to the db
    db = ComputeDb()
    cursor = db.get_cursor()

    try:
        # Retrieve all records from the allocation table
        cursor.execute("SELECT id, hotkey, details FROM allocation")
        rows = cursor.fetchall()
        
        for row in rows:
            id, hotkey, details = row
            hotkey_list.append(hotkey)

    except Exception as e:
        print(f"An error occurred while retrieving allocation details: {e}")
    finally:
        cursor.close()
        db.close()
    try:
        wandb.update_allocated_hotkeys(hotkey_list)
    except Exception as e:
        bt.logging.info(f"Error updating wandb : {e}")
        return
    

def print_welcome_message():
    welcome_text = pyfiglet.figlet_format("Compute Subnet 27", width=120)
    print(welcome_text)
    print("Powered by Neural Internet")
    print(f"Version: {get_local_version()}\n")

def main():
    
    # Check wandb API-Key
    config = get_config()
    wallet = bt.wallet(config=config)
    wandb = ComputeWandb(config, wallet, "validator.py")

    print_welcome_message()

    parser = argparse.ArgumentParser(description='Compute subnet CLI')
    subparsers = parser.add_subparsers(dest='command')

    # Subparser for the 'allocate' command
    parser_allocate = subparsers.add_parser('a', help='Allocate resource via device requirements (GPU)')
    parser_allocate.set_defaults(func=allocate)

    # Subparser for the 'allocate' command
    parser_allocate = subparsers.add_parser('a_hotkey', help='Allocate resource via hotkey')
    parser_allocate.set_defaults(func=allocate_hotkey)

    # Subparser for the 'deallocate' command
    parser_deallocate = subparsers.add_parser('d', help='De-allocate resource')
    parser_deallocate.set_defaults(func=deallocate)

    # Subparser for the 'list_allocations'
    parser_list = subparsers.add_parser('list_a', help='List allocated resources')
    parser_list.set_defaults(func=list_allocations)

    # Subparser for the 'list_resources'
    parser_list = subparsers.add_parser('list_r', help='List resources')
    parser_list.set_defaults(func=list_resources)

    # Print help before entering the command loop
    parser.print_help()

    # Set the WANDB_SILENT environment variable to 'true'
    os.environ['WANDB_SILENT'] = 'true'

    # Command loop
    while True:
        command_input = input("\nEnter command: ").strip()
        if command_input.lower() == 'exit':
            break

        try:
            args = parser.parse_args(command_input.split())
            if hasattr(args, 'func'):
                args.func(wandb)
        except SystemExit:
            # Catch the SystemExit exception to prevent the script from closing
            continue


# The main function parses the configuration and runs the CLI.
if __name__ == "__main__":
    # Parse the configuration.
    # Run the main function.
    main()
