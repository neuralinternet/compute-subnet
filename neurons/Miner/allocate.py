# The MIT License (MIT)
# Copyright © 2023 GitPhantomman

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

import Miner.container as ctn
import bittensor as bt

#Register for given timeline and device_requirement
def register(timeline, device_requirement):
    kill_status = ctn.kill_container()

    bt.logging.info(f"Killed container : {kill_status}")

    #Extract requirements from device_requirement and format them
    cpu_usage = {'assignment' : '0-1'}
    gpu_usage = {'capabilities' : 'all,capabilities=utility'}
    ram_usage = {'capacity' : '1g'}
    volume_usage = {'capacity' : 1073741824}

    run_status = ctn.run_container(cpu_usage, ram_usage, volume_usage, gpu_usage)

    bt.logging.info(f"Runned containers: {run_status}")

    return run_status

#Check if miner is acceptable
def check(timeline, device_requirement):
    #Check if miner is already allocated
    #Check if there is enough device
    return True