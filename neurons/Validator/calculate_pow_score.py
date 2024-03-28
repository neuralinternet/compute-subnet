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


import sentry_sdk
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
        challenge_difficulty_avg = prevent_none(response["challenge_difficulty_avg"])
        has_docker = response.get("has_docker", False)

        if last_20_challenge_failed >= 10 or challenge_successes == 0:
            return 0

        # Define base weights for the PoW
        success_weight = 1
        difficulty_weight = 1
        time_elapsed_weight = 0.5
        failed_penalty_weight = 0.5
        allocation_weight = 0.4

        # Just in case but in theory, it is not possible to fake the difficulty as it is sent by the validator
        # Same occurs for the time, it's calculated by the validator so miners can not fake it
        
        # Difficulty, score range: [0,100] * difficulty_weight
        difficulty_val = max(min(challenge_difficulty_avg, compute.pow_max_difficulty) - compute.pow_min_difficulty,0)
        difficulty_delta = compute.pow_max_difficulty - compute.pow_min_difficulty
        difficulty_modifier = percent(difficulty_val,difficulty_delta)

        difficulty = difficulty_modifier * difficulty_weight

        # Success ratio, score range: [0,100] * success_weight
        successes_ratio = percent(challenge_successes, challenge_attempts)
        successes = successes_ratio * success_weight

        # Time elapsed, score range: [0,100] * time_elapsed_weight
        # The time weight is a function of difficulty, the higher the difficulty, the higher the weight for time. 
        time_elapsed_weight_m = time_elapsed_weight*(difficulty_modifier/100)
        # Modifier for elapsed time effect
        time_elapsed_modifier = percent_yield(challenge_elapsed_time_avg, compute.pow_timeout)
        time_elapsed = time_elapsed_modifier * time_elapsed_weight_m

        # Failed penalty, score range [0,100] * failed_penalty_weight
        # Failed penalty has exponential weigt, the higher the failure rate, the higher the penalty
        failed_penalty_exp = 1.5
        last_20_challenge_failed_modifier = percent(last_20_challenge_failed, 20) #Normalize with defined limits (0,100)
        failed_penalty = failed_penalty_weight * (last_20_challenge_failed_modifier/100)**failed_penalty_exp*100

        # Allocation, score range [0, 100] * allocation_weight
        # The score for allocation is proportional to the average difficulty reached before allocation
        allocation_score = difficulty_modifier * allocation_weight
        allocation_status = check_latest_allocation_status(hotkey, mock=mock)

        # Calculate the score
        max_score_challenge = 100 * (success_weight + difficulty_weight + time_elapsed_weight)
        max_score_allocation = 100 * allocation_weight
        max_score = max_score_challenge + max_score_allocation

        # Docker and specs penalty
        penalty = not(has_docker)

        final_score = 0
        if allocation_status:
            final_score = max_score_challenge + allocation_score
        else:
            final_score = difficulty + successes + time_elapsed - failed_penalty
            if penalty:
                final_score = final_score * 0.5

        # Final score is > 0
        final_score = max(0, final_score)

        # Debugging
        # print("Final score:", final_score)
        # print("Penalty:", penalty)
        # print("Allocation status:",allocation_status)

        # Normalize the score
        normalized_score = normalize(final_score, 0, max_score)
        return normalized_score
    except Exception as e:
        sentry_sdk.capture_exception()
        
        
        bt.logging.error(f"An error occurred while calculating score for the following hotkey - {hotkey}: {e}")
        return 0
    
    
# Check the status of the latest allocation for a specific key across multiple runs
def check_latest_allocation_status(hotkey, mock=False):
    try:
        if mock:
            return True

        # Project
        project="allocated-miners"

        # Initialize W&B API
        api = wandb.Api()

        # Get all runs in the specified project
        runs = api.runs(project)

        # Initialize variables to store the latest key and status
        latest_status = None

        # Iterate over all runs
        for run in runs:
            try:
                # Get the logged data for the key from the run's history (with pandas=False)
                logged_data = run.history(keys=["key", "allocated"], pandas=False)

                # Find the latest logged data for the specified key and return it if available
                latest_data = None
                for data in logged_data:
                    if data["key"] == hotkey:
                        latest_data = data
                        if "allocated" in latest_data:
                            latest_status = latest_data["allocated"]
                            return latest_status
                    
            except Exception as e:
                sentry_sdk.capture_exception()
                
                
                print(f"Error fetching data from run '{run.id}': {e}")

        # Return False if the hotkey was not found 
        return False
          
    except Exception as e:
        sentry_sdk.capture_exception()
        
        
        bt.logging.error("Error checking latest allocation status:", e)
        return None
