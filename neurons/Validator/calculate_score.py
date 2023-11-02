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

import numpy as np

#Calculate score based on the performance information
def score(data):
    if not data:
        return 0
    #Calculate score for each device
    cpu_score = get_cpu_score(data["cpu"])
    gpu_score = get_gpu_score(data["gpu"])
    hard_disk_score = get_hard_disk_score(data["hard_disk"])
    ram_score = get_ram_score(data["ram"])

    score_list = np.array([[cpu_score, gpu_score, hard_disk_score, ram_score]])

    #Define weights for devices
    cpu_weight = 0.3
    gpu_weight = 0.45
    hard_disk_weight = 0.1
    ram_weight = 0.15

    weight_list = np.array([[cpu_weight], [gpu_weight], [hard_disk_weight], [ram_weight]])

    return np.dot(score_list, weight_list).item()

#Score of cpu
def get_cpu_score(cpu_info):
    if not cpu_info:
        return 0
    count = cpu_info['count']
    frequency = cpu_info['frequency']
    return count * frequency / 1024

#Score of gpu
def get_gpu_score(gpu_info):
    if not gpu_info:
        return 0
    capacity = gpu_info['capacity'] / 1024
    return capacity
    
#Score of hard disk
def get_hard_disk_score(hard_disk_info):
    if not hard_disk_info:
        return 0
    capacity = hard_disk_info['free'] / 1024 / 1024 / 1024
    return capacity

#Score of ram
def get_ram_score(ram_info):
    if not ram_info:
        return 0
    capacity = ram_info['available'] / 1024 / 1024 / 1024
    return capacity