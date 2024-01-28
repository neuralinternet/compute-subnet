# The MIT License (MIT)
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

import json

import bittensor as bt

from compute.utils.db import ComputeDb


# Fetch hotkeys from database that meets device_requirement
def select_allocate_miners_hotkey(db: ComputeDb, device_requirement):
    cursor = db.get_cursor()
    try:
        # Fetch all records from miner_details table
        cursor.execute("SELECT * FROM miner_details")
        rows = cursor.fetchall()

        # Check if the miner meets device_requirement
        hotkey_list = []
        for row in rows:
            details = json.loads(row[2])
            if allocate_check_if_miner_meet(details, device_requirement) == True:
                hotkey_list.append(row[1])
        return hotkey_list
    except Exception as e:
        bt.logging.error(f"Error while getting hotkeys from miner_details : {e}")
        return []
    finally:
        cursor.close()


#  Update the miner_details with specs
def update_miner_details(db: ComputeDb, hotkey_list, benchmark_responses):
    cursor = db.get_cursor()
    try:
        cursor.execute(f"DELETE FROM miner_details")
        for index, response in enumerate(benchmark_responses):
            cursor.execute("INSERT INTO miner_details (hotkey, details) VALUES (?, ?)", (hotkey_list[index], json.dumps(response)))
        db.conn.commit()
    except Exception as e:
        db.conn.rollback()
        bt.logging.error(f"Error while updating miner_details : {e}")
    finally:
        cursor.close()


# Check if the miner meets required details
def allocate_check_if_miner_meet(details, required_details):
    if not details:
        return False
    try:
        # CPU side
        cpu_miner = details["cpu"]
        required_cpu = required_details["cpu"]
        if required_cpu and (not cpu_miner or cpu_miner["count"] < required_cpu["count"]):
            return False

        # GPU side
        gpu_miner = details["gpu"]
        required_gpu = required_details["gpu"]
        if required_gpu:
            if not gpu_miner or gpu_miner["capacity"] != required_gpu["capacity"] or gpu_miner["count"] < required_gpu["count"]:
                return False
            else:
                gpu_name = str(gpu_miner["details"][0]["name"]).lower()
                required_type = str(required_gpu["type"]).lower()
                if required_type not in gpu_name:
                    return False

        # Hard disk side
        hard_disk_miner = details["hard_disk"]
        required_hard_disk = required_details["hard_disk"]
        if required_hard_disk and (not hard_disk_miner or hard_disk_miner["free"] < required_hard_disk["capacity"]):
            return False

        # Ram side
        ram_miner = details["ram"]
        required_ram = required_details["ram"]
        if required_ram and (not ram_miner or ram_miner["available"] < required_ram["capacity"]):
            return False
    except Exception as e:
        bt.logging.error("The format is wrong, please check it again.")
        return False
    return True
