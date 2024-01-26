# The MIT License (MIT)
# Copyright © 2023 Crazydevlegend
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


import numpy as np
import wandb


# Calculate score based on the performance information
def score(data, hotkey):
    try:
        # Calculate score for each device
        cpu_score = get_cpu_score(data["cpu"])
        gpu_score = get_gpu_score(data["gpu"])
        hard_disk_score = get_hard_disk_score(data["hard_disk"])
        ram_score = get_ram_score(data["ram"])
        registered = check_if_registered(hotkey)

        # Define upper limits for scores
        # 128 (max nb cpu) * 5000 (5Ghz) / 1024 (const) / 75 (level)
        cpu_limit = 8.33333333333
        # 652472 (capacity) * 16000 (speed Mhz) / 100000 (level)
        gpu_limit = 104.39552
        # 10000000000000 (free space 10Tb) * 20000 (speed) / 10000000 (level)
        hard_disk_limit = 18.6264514923
        # 512 (free ram 512Gb) * 5000 (speed) / 200000 (level)
        ram_limit = 128

        # Applying upper limits to scores
        cpu_score = min(cpu_score, cpu_limit)
        gpu_score = min(gpu_score, gpu_limit)
        hard_disk_score = min(hard_disk_score, hard_disk_limit)
        ram_score = min(ram_score, ram_limit)

        score_list = np.array([[cpu_score, gpu_score, hard_disk_score, ram_score]])

        # Define weights for devices
        cpu_weight = 0.025
        gpu_weight = 0.95
        hard_disk_weight = 0.02
        ram_weight = 0.005

        weight_list = np.array([[cpu_weight], [gpu_weight], [hard_disk_weight], [ram_weight]])
        registration_bonus = registered * 100

        return 10 + np.dot(score_list, weight_list).item() * 100 + registration_bonus
    except Exception as e:
        return 0


# Score of cpu
def get_cpu_score(cpu_info):
    try:
        count = cpu_info["count"]
        frequency = cpu_info["frequency"]
        level = 75  # 30, 2.5
        return count * frequency / 1024 / level
    except Exception as e:
        return 0


# Score of gpu
def get_gpu_score(gpu_info):
    try:
        level = 100000000  # 10GB, 2GHz
        capacity = gpu_info["capacity"] / 1024 / 1024 / 1024
        speed = (gpu_info["graphics_speed"] + gpu_info["memory_speed"]) / 2
        return capacity * speed / level
    except Exception as e:
        return 0


# Score of hard disk
def get_hard_disk_score(hard_disk_info):
    try:
        level = 10000000  # 1TB, 10g/s
        capacity = hard_disk_info["free"] / 1024 / 1024 / 1024
        speed = (hard_disk_info["read_speed"] + hard_disk_info["write_speed"]) / 2

        return capacity * speed / level
    except Exception as e:
        return 0


# Score of ram
def get_ram_score(ram_info):
    try:
        level = 200000  # 100GB, 2g/s
        capacity = ram_info["free"] / 1024 / 1024 / 1024
        speed = ram_info["read_speed"]
        return capacity * speed / level
    except Exception as e:
        return 0


# Check if miner is registered
def check_if_registered(hotkey):
    try:
        runs = wandb.Api().runs("registered-miners")
        values = []
        for run in runs:
            if "key" in run.summary:
                values.append(run.summary["key"])
        if hotkey in values:
            return True
        else:
            return False
    except Exception as e:
        return False
