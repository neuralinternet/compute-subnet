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

def calc_score_pog(gpu_specs, hotkey, allocated_hotkeys, config_data, mock=False):
    try:
        gpu_data = config_data["gpu_performance"]
        gpu_scores = gpu_data.get("gpu_scores", {})
        # Get the GPU with the maximum score
        max_gpu = max(gpu_scores, key=gpu_scores.get)
        max_score = gpu_scores[max_gpu]*8
        score_factor = 100/max_score

        gpu_name = gpu_specs.get("gpu_name")
        num_gpus = min(gpu_specs.get("num_gpus"), 8)

        # Get GPU score
        score = gpu_scores.get(gpu_name) * num_gpus * score_factor

        # Allocation score multiplier = 1 (no allocation bonus)
        if hotkey in allocated_hotkeys:
            score = score * 1

        # Logging score
        # bt.logging.info(f"Score - {hotkey}: {score:.2f}/100")

        # Normalize the score
        normalized_score = normalize(score, 0, 100)

        return normalized_score
    except Exception as e:
        bt.logging.error(f"An error occurred while calculating score for the following hotkey - {hotkey}: {e}")
        return 0
