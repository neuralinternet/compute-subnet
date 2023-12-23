# The MIT License (MIT)
# Copyright © 2023 Crazydevlegend
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
# Step 1: Import necessary libraries and modules

import numpy as np
import wandb

import compute

__all__ = ["score"]


# Calculate score based on the performance information
def score(data):
    try:
        # Calculate score for each device
        registered = check_if_registered(data["axon"].hotkey)

        difficulty = data["difficulty"]
        time_elapsed = data["time_elapsed"]

        # Just in case but in theory, it is not possible to fake the difficulty as it is sent by the validator
        # Same occurs for the time, it's calculated by the validator so miners can not fake it
        difficulty = min(difficulty, compute.pow_max_difficulty)

        score_list = np.array([[difficulty, time_elapsed]])

        # Define weights for the pow
        difficulty_weight = 0.95
        time_elapsed_weight = 0.05

        weight_list = np.array([[time_elapsed_weight], [difficulty_weight]])
        registration_bonus = registered * 100

        return 10 + np.dot(score_list, weight_list).item() * 100 + registration_bonus
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
