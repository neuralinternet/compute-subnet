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
    
    default = 5

    if(performance == {}):
        return default

    # The detailed information of GPU
    gpu_info = performance['gpu']

    #The detailed information of CPU
    cpu_info = performance['cpu']

    bt.logging.info(f"GPU :{gpu_info} CPU: {cpu_info}")

    if gpu_info['count'] == 0:
        return 10
    return 20