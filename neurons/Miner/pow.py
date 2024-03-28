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
import sentry_sdk
import sentry_sdk
import shlex
import subprocess
from typing import Union

import bittensor as bt
import time

import compute

from collections import deque


queue = deque()


def check_cuda_availability():
    import torch

    if torch.cuda.is_available():
        device_count = torch.cuda.device_count()
        bt.logging.info(f"CUDA is available with {device_count} CUDA device(s)!")
    else:
        bt.logging.warning(
            "CUDA is not available or not properly configured on this system."
        )


def hashcat_verify(_hash, output) -> Union[str, None]:
    for item in output.split("\n"):
        if _hash in item:
            return item.strip().split(":")[-1]
    return None


# @fifo
def run_hashcat(
    run_id: str,
    _hash: str,
    salt: str,
    mode: str,
    chars: str,
    mask: str,
    timeout: int = compute.pow_timeout,
    hashcat_path: str = compute.miner_hashcat_location,
    hashcat_workload_profile: str = compute.miner_hashcat_workload_profile,
    hashcat_extended_options: str = "",
    initial_start_time=None,
    execution_time=None,
):
    if initial_start_time:
        start_time = initial_start_time
        real_timeout = timeout - (time.time() - initial_start_time)
    else:
        start_time = time.time()
        real_timeout = timeout - (time.time() - start_time)

    if queue and queue[0] != run_id:
        time.sleep(1)
        execution_time = time.time() - start_time
        return run_hashcat(
            run_id=run_id,
            _hash=_hash,
            salt=salt,
            mode=mode,
            chars=chars,
            mask=mask,
            hashcat_path=hashcat_path,
            hashcat_workload_profile=hashcat_workload_profile,
            hashcat_extended_options=hashcat_extended_options,
            initial_start_time=start_time,
            execution_time=execution_time,
        )
    else:
        bt.logging.info(f"{run_id}: ♻️  Challenge processing")

    unknown_error_message = f"{run_id}: ❌ run_hashcat execution failed"
    try:
        command = [
            hashcat_path,
            f"{_hash}:{salt}",
            "-a",
            "3",
            "-D",
            "2",
            "-m",
            mode,
            "-1",
            str(chars),
            mask,
            "-w",
            hashcat_workload_profile,
            hashcat_extended_options,
        ]
        command_str = " ".join(shlex.quote(arg) for arg in command)
        bt.logging.trace(command_str)

        if execution_time and execution_time >= timeout:
            raise subprocess.TimeoutExpired(command, timeout)

        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=real_timeout,
        )

        execution_time = time.time() - start_time

        # If hashcat returns a valid result
        if process.returncode == 0:
            if process.stdout:
                result = hashcat_verify(_hash, process.stdout)
                bt.logging.success(
                    f"{run_id}: ✅ Challenge {result} found in {execution_time:0.2f} seconds !"
                )
                queue.popleft()
                return {
                    "password": result,
                    "local_execution_time": execution_time,
                    "error": None,
                }
        else:
            error_message = f"{run_id}: ❌ Hashcat execution failed with code {process.returncode}: {process.stderr}"
            bt.logging.warning(error_message)
            queue.popleft()
            return {
                "password": None,
                "local_execution_time": execution_time,
                "error": error_message,
            }

    except subprocess.TimeoutExpired:
        sentry_sdk.capture_exception()
        sentry_sdk.capture_exception()
        execution_time = time.time() - start_time
        error_message = f"{run_id}: ❌ Hashcat execution timed out"
        bt.logging.warning(error_message)
        queue.popleft()
        return {
            "password": None,
            "local_execution_time": execution_time,
            "error": error_message,
        }
    except Exception as e:
        sentry_sdk.capture_exception()
        sentry_sdk.capture_exception()
        execution_time = time.time() - start_time
        bt.logging.warning(f"{unknown_error_message}: {e}")
        queue.popleft()
        return {
            "password": None,
            "local_execution_time": execution_time,
            "error": f"{unknown_error_message}: {e}",
        }
    bt.logging.warning(f"{unknown_error_message}: no exceptions")
    queue.popleft()
    return {
        "password": None,
        "local_execution_time": execution_time,
        "error": f"{unknown_error_message}: no exceptions",
    }


def run_miner_pow(
    run_id: str,
    _hash: str,
    salt: str,
    mode: str,
    chars: str,
    mask: str,
    hashcat_path: str = compute.miner_hashcat_location,
    hashcat_workload_profile: str = compute.miner_hashcat_workload_profile,
    hashcat_extended_options: str = "",
):
    if len(queue) <= 0:
        bt.logging.info(f"{run_id}: 💻 Challenge received")
    else:
        bt.logging.info(f"{run_id}: ⏳ An instance running - added in the queue.")

    # Add to the queue the challenge id
    queue.append(run_id)

    result = run_hashcat(
        run_id=run_id,
        _hash=_hash,
        salt=salt,
        mode=mode,
        chars=chars,
        mask=mask,
        hashcat_path=hashcat_path,
        hashcat_workload_profile=hashcat_workload_profile,
        hashcat_extended_options=hashcat_extended_options,
    )
    return result
