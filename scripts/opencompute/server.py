from fastapi import FastAPI
from typing import Dict, List, Any
import bittensor as bt
import wandb
import os
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = FastAPI()

# Load environment variables
load_dotenv()
api_key = os.getenv("WANDB_API_KEY")

# Constants for W&B
PUBLIC_WANDB_NAME = "opencompute"
PUBLIC_WANDB_ENTITY = "neuralinternet"

# Initialize the Bittensor metagraph with the specified netuid
metagraph = bt.metagraph(netuid=27)

# Cache to store fetched data
hardware_specs_cache: Dict[int, Dict[str, Any]] = {}
allocated_hotkeys_cache: List[str] = []
penalized_hotkeys_cache: List[str] = []

# Create a ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=4)

# Function to fetch hardware specs from wandb
def fetch_hardware_specs(api, hotkeys: List[str]) -> Dict[int, Dict[str, Any]]:
    db_specs_dict: Dict[int, Dict[str, Any]] = {}
    project_path = f"{PUBLIC_WANDB_ENTITY}/{PUBLIC_WANDB_NAME}"
    runs = api.runs(project_path)
    try:
        for run in runs:
            run_config = run.config
            hotkey = run_config.get('hotkey')
            details = run_config.get('specs')
            role = run_config.get('role')
            if hotkey in hotkeys and isinstance(details, dict) and role == 'miner':
                index = hotkeys.index(hotkey)
                db_specs_dict[index] = {"hotkey": hotkey, "details": details}
    except Exception as e:
        print(f"An error occurred while getting specs from wandb: {e}")
    return db_specs_dict

# Function to get all allocated hotkeys from all validators
def get_allocated_hotkeys(api) -> List[str]:
    api.flush()
    runs = api.runs(f"{PUBLIC_WANDB_ENTITY}/{PUBLIC_WANDB_NAME}")

    if not runs:
        print("No validator info found in the project opencompute.")
        return []

    validator_runs = [run for run in runs if run.config.get('role') == 'validator']
    allocated_keys_list: List[str] = []

    for run in validator_runs:
        try:
            run_config = run.config
            allocated_keys = run_config.get('allocated_hotkeys')
            if allocated_keys:
                allocated_keys_list.extend(allocated_keys)
        except Exception as e:
            print(f"Run ID: {run.id}, Name: {run.name}, Error: {e}")

    return allocated_keys_list

# Function to get penalized hotkeys from a specific validator run
def get_penalized_hotkeys_id(api, run_id: str) -> List[str]:
    api.flush()

    # Fetch the specific run by its ID
    run = api.run(run_id)

    if not run:
        print(f"No run info found for ID {run_id}.")
        return []

    penalized_keys_list: List[str] = []

    try:
        run_config = run.config
        # Updated to get the checklist of penalized hotkeys
        penalized_hotkeys_checklist = run_config.get('penalized_hotkeys_checklist', [])
        if penalized_hotkeys_checklist:
            # Loop through the checklist and extract the 'hotkey' field
            for entry in penalized_hotkeys_checklist:
                # hotkey = entry.get('hotkey')
                #if hotkey:
                penalized_keys_list.append(entry)
    except Exception as e:
        print(f"Run ID: {run.id}, Name: {run.name}, Error: {e}")

    return penalized_keys_list

# Function to get penalized hotkeys
def get_penalized_hotkeys(api) -> List[str]:
    api.flush()
    runs = api.runs(f"{PUBLIC_WANDB_ENTITY}/{PUBLIC_WANDB_NAME}")

    if not runs:
        print("No validator info found in the project opencompute.")
        return []

    validator_runs = [run for run in runs if run.config.get('role') == 'validator']
    penalized_keys_list: List[str] = []

    for run in validator_runs:
        try:
            run_config = run.config
            # Updated to get the checklist of penalized hotkeys
            penalized_hotkeys_checklist = run_config.get('penalized_hotkeys_checklist', [])
            if penalized_hotkeys_checklist:
                # Loop through the checklist and extract the 'hotkey' field
                for entry in penalized_hotkeys_checklist:
                    hotkey = entry.get('hotkey')
                    if hotkey:
                        penalized_keys_list.append(hotkey)
        except Exception as e:
            print(f"Run ID: {run.id}, Name: {run.name}, Error: {e}")

    return penalized_keys_list

# Background task to sync the metagraph and fetch hardware specs and allocated hotkeys periodically
async def sync_data_periodically():
    global hardware_specs_cache, allocated_hotkeys_cache, penalized_hotkeys_cache
    while True:
        try:
            metagraph.sync()

            # Run the blocking W&B API calls in a separate thread
            loop = asyncio.get_event_loop()
            wandb.login(key=api_key)
            api = wandb.Api()

            hotkeys = metagraph.hotkeys

            hardware_specs_cache = await loop.run_in_executor(executor, fetch_hardware_specs, api, hotkeys)
            allocated_hotkeys_cache = await loop.run_in_executor(executor, get_allocated_hotkeys, api)
            #penalized_hotkeys_cache = await loop.run_in_executor(executor, get_penalized_hotkeys, api)
            penalized_hotkeys_cache = await loop.run_in_executor(executor, get_penalized_hotkeys_id, api, "neuralinternet/opencompute/0djlnjjs")

        except Exception as e:
            print(f"An error occurred during periodic sync: {e}")

        await asyncio.sleep(600)  # Sleep for 10 minutes

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(sync_data_periodically())

@app.get("/keys")
async def get_keys() -> Dict[str, List[str]]:
    hotkeys = metagraph.hotkeys
    return {"keys": hotkeys}

@app.get("/specs")
async def get_specs() -> Dict[str, Dict[int, Dict[str, Any]]]:
    return {"specs": hardware_specs_cache}

@app.get("/allocated_keys")
async def get_allocated_keys() -> Dict[str, List[str]]:
    return {"allocated_keys": allocated_hotkeys_cache}

@app.get("/penalized_keys")
async def get_penalized_keys() -> Dict[str, List[str]]:
    return {"penalized_keys": penalized_hotkeys_cache}

# To run the server (example):
# uvicorn server:app --reload --host 0.0.0.0 --port 8316
# pm2 start uvicorn --interpreter python3 --name opencompute_server -- --host 0.0.0.0 --port 8000 server:app
