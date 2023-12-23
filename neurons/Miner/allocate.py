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


__all__ = ["register", "check"]

from Miner.container import check_container, kill_container, run_allocate_container
from Miner.schedule import start


# Register for given timeline and device_requirement
def register(timeline, requirement, public_key):
    try:
        _ = kill_container()

        run_status = run_allocate_container(requirement, public_key)

        # Kill container when it meets timeline
        start(timeline)
        return run_status
    except Exception as e:
        # bt.logging.info(f"Error registering container {e}")
        return {"status": False}


# Check if miner is acceptable
def check():
    # Check if miner is already allocated
    if check_container():
        return {"status": False}
    # Check if there is enough device
    return {"status": True}
