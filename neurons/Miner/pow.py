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
import uuid
import shlex
import traceback
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
    hashcat_extended_options: str = compute.miner_hashcat_extended_options,
    initial_start_time=None,
    session: str,
    max_concurrent: int
):
    if not initial_start_time:
        initial_start_time = time.time()

    while True:
        current_time = time.time()
        elapsed_time = current_time - initial_start_time
        real_timeout = timeout - elapsed_time

        if run_id not in queue:
            return {
                "password": None,
                "local_execution_time": elapsed_time,
                "error": "Run id missing from queue?",
            }

        if queue and len(queue) > max_concurrent:
            time.sleep(1)
            continue

        bt.logging.info(f"{run_id}: ♻️  Challenge processing")

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
            "--session",
            session,
            hashcat_extended_options,
        ]
        command_str = " ".join(shlex.quote(arg) for arg in command)
        bt.logging.trace(command_str)

        if elapsed_time >= timeout:
            error_message = f"{run_id}: ❌ Timeout before starting hashcat"
            bt.logging.warning(error_message)
            queue.popleft()
            return {
                "password": None,
                "local_execution_time": elapsed_time,
                "error": error_message,
            }

        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=real_timeout,
            )

            if process.returncode == 0 and process.stdout:
                result = hashcat_verify(_hash, process.stdout)
                bt.logging.success(
                    f"{run_id}: ✅ Challenge {result} found in {elapsed_time:0.2f} seconds !"
                )
                queue.popleft()
                return {
                    "password": result,
                    "local_execution_time": elapsed_time,
                    "error": None,
                }
            elif process.returncode == 255:
                time.sleep(1)
                continue
            else:
                error_message = f"{run_id}: ❌ Hashcat execution failed with code {process.returncode}: {process.stderr}"
                bt.logging.warning(error_message)
                queue.popleft()
                return {
                    "password": None,
                    "local_execution_time": elapsed_time,
                    "error": error_message,
                }
        except subprocess.TimeoutExpired:
            error_message = f"{run_id}: ❌ Hashcat execution timed out"
            bt.logging.warning(error_message)
            queue.popleft()
            return {
                "password": None,
                "local_execution_time": elapsed_time,
                "error": error_message,
            }
        except Exception as e:
            traceback.print_exc()
            error_message = f"{run_id}: ❌ run_hashcat execution failed: {e}"
            bt.logging.warning(error_message)
            queue.popleft()
            return {
                "password": None,
                "local_execution_time": elapsed_time,
                "error": error_message,
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
    max_concurrent: int
):
    bt.logging.info(f"{run_id}: 💻 Challenge received")

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
        session=str(uuid.uuid4()).replace("-", ""),
        max_concurrent=max_concurrent
    )
    return result
