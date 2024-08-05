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
def calc_score(response, hotkey, allocated_hotkeys, max_score_uid, mock=False):
    """
    Method to calculate the score attributed to this miner dual uid - hotkey
    :param response:
    {
        'challenge_attempts': 7,
        'challenge_successes': 6,
        'challenge_failed': 0,
        'challenge_elapsed_time_avg': 5.804196675618489,
        'challenge_difficulty_avg': 2.0,
        'has_docker': True,
    }
    challenge_failed is batched over the last 10 challenges only
    :param hotkey:
    :param mock: During testing phase
    :return:
    """
    try:
        challenge_attempts = prevent_none(response["challenge_attempts"])
        challenge_successes = prevent_none(response["challenge_successes"])
        last_20_challenge_failed = prevent_none(response["last_20_challenge_failed"])
        challenge_elapsed_time_avg = prevent_none(response["challenge_elapsed_time_avg"])
        challenge_difficulty_avg = prevent_none(response["last_20_difficulty_avg"])
        has_docker = response.get("has_docker", False)

        # Define base weights for the PoW
        success_weight = 1.0
        difficulty_weight = 1.0
        time_elapsed_weight = 0.4
        failed_penalty_weight = 0.35
        allocation_weight = 0.10

        # Just in case but in theory, it is not possible to fake the difficulty as it is sent by the validator
        # Same occurs for the time, it's calculated by the validator so miners cannot fake it
        
        # Difficulty, score range: [0,100] * difficulty_weight
        difficulty_val = max(min(challenge_difficulty_avg, compute.pow_max_difficulty),compute.pow_min_difficulty)
        difficulty_modifier = percent(difficulty_val,compute.pow_max_difficulty)

        difficulty = difficulty_modifier * difficulty_weight

        # Success ratio, score range: [0,100] * success_weight
        successes_ratio = percent(challenge_successes, challenge_attempts)
        successes = successes_ratio * success_weight

        # Time elapsed, score range: [0,100] * time_elapsed_weight
        # Modifier for elapsed time effect
        time_elapsed_modifier = percent_yield(challenge_elapsed_time_avg, compute.pow_timeout)
        time_elapsed = time_elapsed_modifier * time_elapsed_weight

        # Failed penalty, score range [0,100] * failed_penalty_weight
        # Failed penalty has exponential weigt, the higher the failure rate, the higher the penalty
        failed_penalty_exp = 1.5
        last_20_challenge_failed_modifier = percent(last_20_challenge_failed, 20) #Normalize with defined limits (0,100)
        failed_penalty = failed_penalty_weight * (last_20_challenge_failed_modifier/100)**failed_penalty_exp*100

        # Allocation, score range [0, 100] * allocation_weight
        # The score for allocation is proportional to the average difficulty reached before allocation
        allocation_score = difficulty_modifier * allocation_weight
        allocation_status = hotkey in allocated_hotkeys

        if last_20_challenge_failed >= 19 or challenge_successes == 0 and not allocation_status:
            return 0

        # Calculate the score
        max_score_challenge = 100 * (success_weight + difficulty_weight + time_elapsed_weight)
        max_score_allocation = max_score_challenge  * allocation_weight
        max_score = max_score_challenge + max_score_allocation
        final_score = difficulty + successes + time_elapsed - failed_penalty

        # denormalize max score
        max_score_uid_dn = max_score_uid * max_score

        # Docker and specs penalty
        penalty = not(has_docker)

        if allocation_status:
            final_score = max_score_uid_dn * (1 + allocation_score/100)
        else:
            final_score = difficulty + successes + time_elapsed - failed_penalty
            if penalty:
                final_score = final_score/2

        # Final score is > 0
        final_score = max(0, final_score)

        # Normalize the score
        normalized_score = normalize(final_score, 0, max_score)
        return normalized_score
    except Exception as e:
        bt.logging.error(f"An error occurred while calculating score for the following hotkey - {hotkey}: {e}")
        return 0
