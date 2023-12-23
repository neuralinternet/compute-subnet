# The MIT License (MIT)
# Copyright © 2023 Rapiiidooo
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
import time
import traceback

import bittensor as bt
import torch

from compute import pow, pow_timeout

__all__ = ["proof_of_work_miner"]


def proof_of_work_miner(header, target_difficulty):
    start_time = time.time()
    nonce = 0

    if not torch.cuda.is_available():
        bt.logging.error(traceback.format_exc())
        bt.logging.error("CUDA is not available.")
        bt.logging.error("Switched to CPUs, be careful you might never have results and might be de-registered.")

    while time.time() - start_time > pow_timeout:
        hash_result = pow.calculate_hash(header, nonce)

        # Ensure the hash satisfy the targeted difficulty
        if hash_result.startswith("0" * target_difficulty):
            return nonce, hash_result
        nonce += 1

        if nonce % 1_000_000 == 0:
            bt.logging.info(f"🔢 Nonce iterated : {nonce}")

    bt.logging.info("Unable to find a valid answer within 120 seconds.")
