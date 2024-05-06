# The MIT License (MIT)
# Copyright © 2023 Crazydevlegend
# Copyright © 2023 Rapiiidooo
# Cp[yright @ 2024 Thomas Chu
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

from starlette.responses import JSONResponse
from sympy.codegen.fnodes import allocated

import RSAEncryption as rsa
from compute.protocol import Allocate
from compute.utils.db import ComputeDb
from compute.wandb.wandb import ComputeWandb
from neurons.Validator.database.allocate import (
     select_allocate_miners_hotkey,
     update_allocation_db,
     get_miner_details,
)
from compute.utils.version import get_local_version
from compute.utils.db import ComputeDb
from register import (
     allocate_container,
     allocate_container_hotkey,
     update_allocation_wandb,
)

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse

# from passlib.context import CryptContext
from pydantic import typing, BaseModel, Field
from typing import List, Optional, Type, Union, Any

# Database connection details
DATABASE_URL = "sqlite:///data.db"

# Security configuration
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


class UserConfig(BaseModel):
    netuid: str = Field(default="15")
    subtensor_network: str = Field(default="test", alias="subtensor.network")
    subtensor_chain_endpoint: Union[str, None] = Field(
        default="", alias="subtensor.chain_endpoint"
    )
    wallet_name: str = Field(default="validator", alias="wallet.name")
    wallet_hotkey: str = Field(default="default", alias="wallet.hotkey")
    logging_debug: Union[str, None] = Field(default="", alias="logging.debug")


class Requirement(BaseModel):
    gpu_type: str = "a6000"
    gpu_size: int = 3000
    timeline: int = "90" # timeline=90 day by spec, 30 day by hotkey


class Allocation(BaseModel):
    resource: str = ""
    hotkey: str = ""
    regkey: str = ""
    ssh_ip: str = ""
    ssh_port: int = 4444
    ssh_username: str = ""
    ssh_password: str = ""
    ssh_command: str = ""


class UserInfo(BaseModel):
    user_id: str = ""
    user_pass: str = ""
    token: str = ""


class ResourceGPU(BaseModel):
    gpu_name: str = ""
    gpu_capacity: int = 0
    gpu_count: int = 1


class Resource(BaseModel):
    hotkey: str = ""
    cpu_count: int = 1
    gpu_name: str = ""
    gpu_capacity: str = ""
    gpu_count: int = 1
    ram: str = "0"
    hard_disk: str = "0"
    allocate_status: str = ""  # "Avail." or "Res."


app = FastAPI()


@app.on_event("startup")
async def startup_event():
    """
    This function is called when the application starts. <br>
    It initializes the database connection and other necessary components. <br>
    """
    # Initialize the config connection
    global config, wandb
    user_config = UserConfig()
    user_config.netuid = "15"
    user_config.subtensor_network = "test"
    user_config.subtensor_chain_endpoint = ""
    user_config.wallet_name = "validator"
    user_config.wallet_hotkey = "default"
    user_config.logging_debug = ""
    config = get_config_api(user_config=user_config)
    # Initialize the W&B logging
    wandb = get_wandb_api(config)



# For User authentication function
@app.post(
    "/user/login",
    response_model=UserInfo,
    responses={
        401: {"description": "Invalid authentication credentials"},
        200: {"description": "User login successful"},
    },
)
async def login(
    user_id: str,
    user_pass: str,
):
    """
    The user login API endpoint. <br>
    user_id: The user ID. <br>
    user_pass: The user password. <br>
    user will be authenticated and a token will be returned. <br>
    """
    if not user_pass or not user_id:
        # credentials_exception = HTTPException(
        #         status_code=status.HTTP_401_UNAUTHORIZED,
        #         detail="Invalid authentication credentials",
        #         headers={"WWW-Authenticate": "Bearer"},
        return {"status": "error", "message": "user_id and user_pass not found"}
    else:
        #     username = form_data.username
        #     password = form_data.password
        #     user = await self.verify_password(username, password)
        #     if not user:
        #         raise HTTPException(
        #             status_code=status.HTTP_400_BAD_REQUEST,
        #             detail="Incorrect username or password",
        #         )
        #     access_token = f"Bearer {username}"  # Simple token format (replace with JWT for better security)
        #     return {"access_token": access_token, "token_type": "bearer"}
        username = f"Bearer {token}"  # Extract username from token format
        is_valid = await self.verify_password(
            username, ""
        )  # Empty password for verification
        if not is_valid:
            raise credentials_exception
        #   return pwd_context.verify(plain_password, user.hashed_password)
        return {"apiKey": token}

        # User registration methods


@app.post(
    "/service/allocate_spec",
    response_model=Allocation,
    responses={
        400: {"description": "Invalid allocation request"},
        401: {"description": "Missing authorization"},
        404: {"description": "Fail to get allocation"},
        201: {"description": "Resource was successfully allocated"},
    },
)
async def allocate_spec(
    token: str,
    requirements: Requirement,
) -> JSONResponse:
    """
    The GPU resource allocate API endpoint. <br>
    token: The user token for the authorization. <br>
    user_config: The user configuration which contain the validator's hotkey and wallet information. <br>
    requirements: The GPU resource requirements which contain the GPU type, GPU size, and booking timeline. <br>
    """
    if token:
        if requirements:
            config.gpu_type = requirements.gpu_type
            config.gpu_size = int(requirements.gpu_size)
            config.timeline = int(requirements.timeline)

            device_requirement = {
                "cpu": {"count": 1},
                "gpu": {},
                "hard_disk": {"capacity": 1073741824},
                "ram": {"capacity": 1073741824},
            }
            if config.gpu_type != "" and config.gpu_size != 0:
                device_requirement["gpu"] = {
                    "count": 1,
                    "capacity": config.gpu_size,
                    "type": config.gpu_type,
                }
            timeline = int(requirements.timeline)
            private_key, public_key = rsa.generate_key_pair()
            result = allocate_container(config, device_requirement, timeline, public_key)

            if result["status"] is True:
                result_hotkey = result["hotkey"]
                result_info = result["info"]
                private_key = private_key.encode("utf-8")
                decrypted_info_str = rsa.decrypt_data(
                    private_key, base64.b64decode(result_info)
                )
                bt.logging.info(
                    f"Registered successfully : {decrypted_info_str}, 'ip':{result['ip']}"
                )

                # Iterate through the miner specs details to get gpu_name
                db = ComputeDb()
                specs_details = get_miner_details(db)
                for key, details in specs_details.items():
                    if str(key) == str(result_hotkey) and details:
                        try:
                            gpu_miner = details["gpu"]
                            gpu_name = str(gpu_miner["details"][0]["name"]).lower()
                            break
                        except (KeyError, IndexError, TypeError):
                            gpu_name = "Invalid details"
                    else:
                        gpu_name = "No details available"

                info = json.loads(decrypted_info_str)
                info["ip"] = result["ip"]
                info["resource"] = gpu_name
                info["regkey"] = public_key

                time.sleep(1)

                allocated = Allocation()
                allocated.resource = info["resource"]
                allocated.hotkey = result_hotkey
                # allocated.regkey = info["regkey"]
                allocated.ssh_ip = info["ip"]
                allocated.ssh_port = info["port"]
                allocated.ssh_username = info["username"]
                allocated.ssh_password = info["password"]
                allocated.ssh_command = f"ssh {info['username']}@{result['ip']} -p {str(info['port'])}"

                update_allocation_db(result_hotkey, info, True)
                update_allocation_wandb(wandb)
                return JSONResponse(status_code=status.HTTP_201_CREATED, content=jsonable_encoder(allocated))
            else:
                bt.logging.info(f"Failed : {result['msg']}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"msg": result['msg']})
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"msg": "Invalid allocation request"})
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"msg": "Missing authorization"},
        )


@app.post(
    "/service/allocate_hotkey",
    response_model=Allocation,
    responses={
        400: {"description": "Invalid allocation request"},
        401: {"description": "Missing authorization"},
        404: {"description": "Fail to get allocation"},
        201: {"description": "Resource was successfully allocated"},
    },
)
async def allocate_hotkey(
    token: str,
    hotkey: str,
) -> JSONResponse:
    """
    The GPU allocate by hotkey API endpoint. <br>
    User use this API to book a specific miner. <br>
    token: The user token for the authorization. <br>
    user_config: The user configuration which contain the validator's hotkey and wallet information. <br>
    hotkey: The miner hotkey to allocate the gpu resource. <br>
    """
    if token:
        if hotkey:
            timeline = 30
            private_key, public_key = rsa.generate_key_pair()
            result = allocate_container_hotkey(config, hotkey, timeline, public_key)

            # Iterate through the miner specs details to get gpu_name
            db = ComputeDb()
            specs_details = get_miner_details(db)
            for key, details in specs_details.items():
                if str(key) == str(hotkey) and details:
                    try:
                        gpu_miner = details["gpu"]
                        gpu_name = str(gpu_miner["details"][0]["name"]).lower()
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
                bt.logging.info(
                    f"Registered successfully : {decrypted_info_str}, 'ip':{result['ip']}"
                )

                info = json.loads(decrypted_info_str)
                info["ip"] = result["ip"]
                info["resource"] = gpu_name
                info["regkey"] = public_key

                time.sleep(1)
                allocated = Allocation()
                allocated.resource = info["resource"]
                allocated.hotkey = result_hotkey
                # allocated.regkey = info["regkey"]
                allocated.ssh_ip = info["ip"]
                allocated.ssh_port = info["port"]
                allocated.ssh_username = info["username"]
                allocated.ssh_password = info["password"]
                allocated.ssh_command = f"ssh {info['username']}@{result['ip']} -p {str(info['port'])}"

                update_allocation_db(result_hotkey, info, True)
                update_allocation_wandb(wandb)
                return JSONResponse(status_code=status.HTTP_201_CREATED, content=jsonable_encoder(allocated))
            else:
                bt.logging.info(f"Failed : {result['msg']}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"msg": result['msg']})
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"msg": "Invalid allocation request"})
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"msg": "Missing authorization"},
        )


@app.post(
    "/service/deallocate",
    response_model=dict,
    responses={
        400: {"description": "De-allocation not successfully, please try again."},
        401: {"description": "Missing authorization"},
        403: {"description": "An error occurred during de-allocation"},
        404: {"description": "No allocation details found for the provided hotkey."},
        200: {"description": "Resource de-allocated successfully."},
    },
)
async def deallocate(
    token: str,
    hotkey: str,
):
    """
    The GPU deallocate API endpoint. <br>
    token: The user token for the authorization. <br>
    user_config: The user configuration which contain the validator's hotkey and wallet information. <br>
    hotkey: The miner hotkey to deallocate the gpu resource. <br>
    """
    if token:
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
                    Allocate(timeline=0, device_requirement={}, checking=False, public_key=regkey),
                    timeout=60,
                )
                if deregister_response and deregister_response["status"] is True:
                    update_allocation_db(result_hotkey, info, False)
                    update_allocation_wandb(wandb)
                    return JSONResponse(
                        status_code=status.HTTP_200_OK, content={"msg": "Resource de-allocated successfully."})
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"msg": "De-allocation not successfully, please try again."},
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"msg": "No allocation details found for the provided hotkey."}
                )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail={"msg": "An error occurred during de-allocation", "error": e.__repr__()}
            )
        finally:
            cursor.close()
            db.close()
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"msg": "Missing authorization"},
        )

@app.post(
    "/service/list_allocations",
    response_model=List[Allocation],
    responses={
        401: {"description": "Missing authorization token"},
        403: {"description": "An error occurred while retrieving allocation details"},
        404: {"description": "There is no allocation available"},
        200: {"description": "List allocations successfully."},
    },
)
async def list_allocations(
    token: str,
) -> JSONResponse | Any:
    """
    The list allocation API endpoint. <br>
    The API will return the current allocation on the validator. <br>
    token: The user token for the authorization. <br>
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )

    else:
        db = ComputeDb()
        cursor = db.get_cursor()
        allocation_list = []

        try:
            # Retrieve all records from the allocation table
            cursor.execute("SELECT id, hotkey, details FROM allocation")
            rows = cursor.fetchall()

            bt.logging.info(f"LIST OF ALLOCATED RESOURCES")

            if not rows:
                bt.logging.info(
                    "No resources allocated. Allocate a resource with validator"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"msg": "No resources allocated. Allocate a resource with validator."},
)

            for row in rows:
                id, hotkey, details = row
                info = json.loads(details)
                entry = Allocation()

                entry.hotkey = hotkey
                # entry.regkey = info["regkey"]
                entry.resource = info["resource"]
                entry.ssh_username = info["username"]
                entry.ssh_password = info["password"]
                entry.ssh_port = info["port"]
                entry.ssh_ip = info["ip"]
                entry.ssh_command = (
                    f"ssh {info['username']}@{info['ip']} -p {info['port']}"
                )
                allocation_list.append(entry)

        except Exception as e:
            bt.logging.error(
                f"An error occurred while retrieving allocation details: {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"msg": "An error occurred while retrieving allocation details.", "detail": e.__repr__()},
            )
        finally:
            cursor.close()
            db.close()

        return JSONResponse(status_code=status.HTTP_200_OK, content=jsonable_encoder(allocation_list))


@app.post(
    "/service/list_resources",
    response_model=List[Resource],
    responses={
        401: {"description": "Missing authorization"},
        404: {"description": "There is no resource available"},
        200: {"description": "List resources successfully."},
    },
)
async def list_resources(token: str):
    """
    The list resources API endpoint. <br>
    The API will return the current miner resource and their detail specs on the validator. <br>
    token: The user token for the authorization. <br>
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization"
        )
    else:
        db = ComputeDb()
        specs_details = get_miner_details(db)

        bt.logging.info(f"LIST OF RESOURCES ON COMPUTE SUBNET")

        # Initialize a dictionary to keep track of GPU instances
        resource_list = []
        gpu_instances = {}
        total_gpu_counts = {}
        
        # Iterate through the miner specs details and print the table
        for hotkey, details in specs_details.items():
            if details:  # Check if details are not empty
                resource = Resource()
                try:
                    # Extract GPU details
                    gpu_miner = details["gpu"]
                    gpu_capacity = "{:.2f}".format((gpu_miner["capacity"] / 1024))
                    gpu_name = str(gpu_miner["details"][0]["name"]).lower()
                    gpu_count = gpu_miner["count"]
        
                    # Extract CPU details
                    cpu_miner = details["cpu"]
                    cpu_count = cpu_miner["count"]
        
                    # Extract RAM details
                    ram_miner = details["ram"]
                    ram = "{:.2f}".format(ram_miner["available"] / 1024.0**3)
        
                    # Extract Hard Disk details
                    hard_disk_miner = details["hard_disk"]
                    hard_disk = "{:.2f}".format(hard_disk_miner["free"] / 1024.0**3)
        
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
            allocate_status = "N/A"
            allocated_hotkeys = wandb.get_allocated_hotkeys([], False)
        
            if hotkey in allocated_hotkeys:
                allocate_status = "Res."
            else:
                allocate_status = "Avail."
        
            # Print the row with column separators
            resource.hotkey = hotkey
            resource.cpu_count = cpu_count
            resource.gpu_name = gpu_name
            resource.gpu_capacity = gpu_capacity
            resource.gpu_count = gpu_count
            resource.ram = ram
            resource.hard_disk = hard_disk
            resource.allocate_status = allocate_status
            resource_list.append(resource)

        return JSONResponse(status_code=status.HTTP_200_OK, content=jsonable_encoder(resource_list))

def get_config_api(user_config: UserConfig, requirements: Union[Requirement, None] = None):
    """
    Get the config from user config and spec requirement for the API. <br>
    user_config: The user configuration which contain the validator's hotkey and wallet information. <br>
    requirements: The device requirements. <br>
    """
    parser = argparse.ArgumentParser()
    # Adds bittensor specific arguments
    parser.add_argument("--netuid", type=int, default=27, help="The chain subnet uid.")
    parser.add_argument("--gpu_type", type=str, help="The GPU type.")
    parser.add_argument("--gpu_size", type=int, help="The GPU memory in MB.")
    parser.add_argument("--timeline", type=int, help="The allocation timeline.")
    bt.subtensor.add_args(parser)
    bt.logging.add_args(parser)
    bt.wallet.add_args(parser)

    if not user_config.subtensor_chain_endpoint:
        if user_config.subtensor_network=="finney":
            user_config.subtensor_chain_endpoint = "wss://entrypoint-finney.opentensor.ai:443"
        elif user_config.subtensor_network=="test":
            user_config.subtensor_chain_endpoint = "wss://test.finney.opentensor.ai:443"

    # Add user configuration and requirement to list for the bt config parser
    # args = [f"--{v.alias}";getattr(entry,k) for entry in [user_config, requirements] for k, v in entry.__fields__.items()]
    args_list = []
    for entry in [user_config, requirements]:
        if entry:
            for k, v in entry.__fields__.items():
                args_list.append(f"--{(v.alias)}")
                args_list.append(getattr(entry, k))

    # Parse the initial config to check for provided arguments
    config = bt.config(parser=parser, args=args_list)

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

def get_wandb_api(config: bt.config):
    """
    Get the wandb from the config. <br>
    config: The config object. <br>
    """
    wallet = bt.wallet(config=config)
    wandb = ComputeWandb(config, wallet, "validator.py")
    return wandb


# Run the FastAPI app
if __name__ == "__main__":
    os.environ["WANDB_SILENT"] = "true"
    uvicorn.run(app, host="0.0.0.0", port=9981)
