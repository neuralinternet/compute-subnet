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

__all__ = ["calc_score"]

from compute.utils.math import percent, percent_yield


def normalize(val, min_value, max_value):
    return (val - min_value) / (max_value - min_value)


def prevent_none(val):
    return 0 if not val else val


# Calculate score based on the performance information
def calc_score(response, hotkey, mock=False):
    """
    Method to calculate the score attributed to this miner dual uid - hotkey
    :param response:
    {'challenge_attempts': 7, 'challenge_successes': 6, 'challenge_failed': 0, 'challenge_elapsed_time_avg': 5.804196675618489, 'challenge_difficulty_avg': 2.0}
    challenge_failed is batched over the last 10 challenges only
    :param hotkey:
    :param mock: During testing phase
    :return:
    """
    try:
        challenge_attempts = prevent_none(response["challenge_attempts"])
        challenge_successes = prevent_none(response["challenge_successes"])
        challenge_failed = prevent_none(response["challenge_failed"])
        last_20_challenge_failed = prevent_none(response["last_20_challenge_failed"])
        challenge_elapsed_time_avg = prevent_none(response["challenge_elapsed_time_avg"])
        challenge_difficulty_avg = prevent_none(response["challenge_difficulty_avg"])

        if last_20_challenge_failed >= 10 or challenge_successes == 0:
            return 0

        # Define base weights for the PoW
        success_weight = 0.8
        difficulty_weight = 0.18
        time_elapsed_weight = 0.02
        failed_penalty_weight = 0.5
        total_failed_penalty_weight = 0.2

        # Just in case but in theory, it is not possible to fake the difficulty as it is sent by the validator
        # Same occurs for the time, it's calculated by the validator so miners can not fake it
        difficulty = min(challenge_difficulty_avg, compute.pow_max_difficulty) * difficulty_weight

        # Success ratio
        successes_ratio = percent(challenge_successes, challenge_attempts)
        successes = successes_ratio * success_weight

        # Apply a bonus for registered miners
        registration_bonus = check_if_registered(hotkey, mock=mock) * 1

        # Modifier for elapsed time effect
        time_elapsed_modifier = percent_yield(challenge_elapsed_time_avg, compute.pow_timeout)
        time_elapsed = time_elapsed_modifier * time_elapsed_weight

        failed_penalty = failed_penalty_weight * last_20_challenge_failed
        total_failed_penalty = total_failed_penalty_weight * challenge_failed

        # Calculate the score
        final_score = successes + difficulty + time_elapsed + registration_bonus - failed_penalty - total_failed_penalty

        # Normalize the score
        normalized_score = normalize(final_score, 0, 100)
        return normalized_score
    except Exception as e:
        bt.logging.error(f"An error occurred while calculating score for the following hotkey - {hotkey}: {e}")
        return 0


# Check if miner is registered
def check_if_registered(hotkey, mock=False):
    try:
        if mock is True:
            return True

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
