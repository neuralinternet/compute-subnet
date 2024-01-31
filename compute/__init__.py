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

import string

# Define the version of the template module.
__version__ = "1.3.7"
__minimal_miner_version__ = "1.3.6"
__minimal_validator_version__ = "1.3.6"

version_split = __version__.split(".")
__version_as_int__ = (100 * int(version_split[0])) + (10 * int(version_split[1])) + (1 * int(version_split[2]))

# General static vars
validator_permit_stake = 1.024e3  # Stake amount to be a permitted validator
weights_rate_limit = 100

# Validators static vars
pow_timeout = 30  # Time before the proof of work requests will time out. time unit = seconds
pow_min_difficulty = 6  # Initial and minimal proof of work difficulty. Needs benchmark and adjustment.
pow_max_difficulty = 12  # Maximal proof of work difficulty, this to ensure a miner can not be rewarded for an unlimited unreasonable difficulty. Needs benchmark and adjustment.
pow_default_mode = "610"  # Model: BLAKE2b-512($pass.$salt)
pow_default_chars = str(string.ascii_letters + string.digits + "!@#$%^&*()-_+=[]{};:,.<>/")

# Miners static vars
miner_priority_specs = 1  # Lowest priority
miner_priority_challenge = 2  # Medium priority
miner_priority_allocate = 3  # The highest priority
miner_hashcat_location = "hashcat"
miner_hashcat_workload_profile = "3"

SUSPECTED_EXPLOITERS_COLDKEYS = []
SUSPECTED_EXPLOITERS_HOTKEYS = [
    "5HZ1ATsziEMDm1iUqNWQatfEDb1JSNf37AiG8s3X4pZzoP3A",
    "5H679r89XawDrMhwKGH1jgWMZQ5eeJ8RM9SvUmwCBkNPvSCL",
    "5FnMHpqYo1MfgFLax6ZTkzCZNrBJRjoWE5hP35QJEGdZU6ft",
    "5H3tiwVEdqy9AkQSLxYaMewwZWDi4PNNGxzKsovRPUuuvALW",
    "5E6oa5hS7a6udd9LUUsbBkvzeiWDCgyA2kGdj6cXMFdjB7mm",
    "5DFaj2o2R4LMZ2zURhqEeFKXvwbBbAPSPP7EdoErYc94ATP1",
    "5H3padRmkFMJqZQA8HRBZUkYY5aKCTQzoR8NwqDfWFdTEtky",
    "5HBqT3dhKWyHEAFDENsSCBJ1ntyRdyEDQWhZo1JKgMSrAhUv",
    "5FAH7UesJRwwLMkVVknW1rsh9MQMUo78d5Qyx3KpFpL5A7LW",
    "5GUJBJmSJtKPbPtUgALn4h34Ydc1tjrNfD1CT4akvcZTz1gE",
    "5E2RkNBMCrdfgpnXHuiC22osAxiw6fSgZ1iEVLqWMXSpSKac",
    "5DaLy2qQRNsmbutQ7Havj49CoZSKksQSRkCLJsiknH8GcsN2",
    "5GNNB5kZfo6F9hqwXvaRfYdTuJPSzrXbtABzwoL499jPNBjt",
    "5GVjcJLQboN5NcQoP4x8oqovjAiEizdscoocWo9HBYYmPdR3",
    "5FswTe5bbs9n1SzaGpzUd6sDfnzdPfWVS2MwDWNbAneeT15k",
    "5F4bqDZkx79hCxmbbsVMuq312EW9hQLvsBzKsAJgcEqpb8L9",
]

# TODO feat(Validators): Implement the dynamic difficulty.
# TODO feat(Validators/Miners): Random hashes used for challenge ? maybe not necessary thanks to Blake algo.
# TODO feat(Miners): Remove docker requirement, to support containerized providers.
# TODO Partially done: Run black everywhere. Use Classes instead of big main and unclassified methods.
