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

import bittensor as bt
import wandb

import compute

__all__ = ["score"]


# Calculate score based on the performance information
def score(response, difficulty, hotkey):
    try:
        success = response["success"]
        elapsed_time = response["elapsed_time"]

        if not success:
            return 0

        # Just in case but in theory, it is not possible to fake the difficulty as it is sent by the validator
        # Same occurs for the time, it's calculated by the validator so miners can not fake it
        difficulty = min(difficulty, compute.pow_max_difficulty)

        # Define base weights for the PoW
        difficulty_weight = 0.5
        time_elapsed_weight = 0.5

        # Apply exponential rewards for difficulty
        difficulty_reward = difficulty * (1 + (difficulty**6))

        # Apply a bonus for registered miners
        registration_bonus = check_if_registered(hotkey) * 20000

        # Modifier for elapsed time effect
        time_modifier = 1 / (1 + elapsed_time) * 200000

        # Calculate the score
        final_score = difficulty_reward + (difficulty_weight * difficulty) + (time_elapsed_weight * time_modifier) + registration_bonus

        # Normalize the score
        max_score = 1e6
        normalized_score = (final_score / max_score) * 100
        return min(normalized_score, compute.pow_max_possible_score)
    except Exception as e:
        bt.logging.error(f"An error occurred while calculating score for the following hotkey - {hotkey}: {e}")
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
    except Exception as _:
        return False
