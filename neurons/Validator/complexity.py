# The MIT License (MIT)
# Copyright © 2023 GitPhantom

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
import bittensor as bt

# This function is responsible for estimating the complexity of benchmark based on the performance information
def calculate_complexity(performance):
    
    base_value = 5
    if(performance == {}):
        return 10

    # The detailed information of GPU
    gpu_info = performance['gpu']

    #The detailed information of CPU
    cpu_info = performance['cpu']

    #Valuate cpu's ability
    cpu_count = cpu_info['count']
    cpu_speed = float(cpu_info['hz_advertised_friendly'].split()[0])
    cpu_value = cpu_count * cpu_speed
    cpu_per_complexity = 10
    cpu_only_complexity = base_value + cpu_value / cpu_per_complexity

    if gpu_info['count'] == 0:
        return int(cpu_only_complexity)
    
    #In case of GPU
    gpu_count = gpu_info['count']
    gpu_details= gpu_info['details']
    gpu_value = sum(float(obj['memoryTotal']) for obj in gpu_details)
    gpu_per_complexity = 1024.0
    gpu_only_complexity = gpu_value / gpu_per_complexity

    return int(gpu_only_complexity)