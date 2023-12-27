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
import subprocess
from typing import Union

import bittensor as bt

import compute


def check_cuda_availability():
    import torch

    if torch.cuda.is_available():
        device_count = torch.cuda.device_count()
        bt.logging.info(f"CUDA is available with {device_count} CUDA device(s)!")
    else:
        bt.logging.warning("CUDA is not available or not properly configured on this system.")


def hashcat_verify(_hash, output) -> Union[str, None]:
    for item in output.split("\n"):
        if _hash in item:
            return item.strip().split(":")[-1]
    return None


def run_hashcat(
    _hash: str, salt: str, mode: str, chars: str, mask: str, timeout: int = compute.pow_timeout, hashcat_path: str = compute.default_hashcat_location
):
    try:
        process = subprocess.run(
            [hashcat_path, f"{_hash}:{salt}", "-a", "3", "-m", mode, "-1", str(chars), mask, "-w", "3", "-O"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # If hashcat returns a valid result
        if process.returncode == 0:
            if process.stdout:
                result = hashcat_verify(_hash, process.stdout)
                bt.logging.debug(f"Challenge {result} found !")
                return {"password": result, "error": None}
        else:
            return {"password": None, "error": f"Hashcat execution failed with code {process.returncode}: {process.stderr}"}

    except subprocess.TimeoutExpired:
        return {"password": None, "error": "Hashcat execution timed out"}
    except Exception as e:
        return {"password": None, "error": f"run_hashcat execution failed with exception: {e}"}


def run_miner_pow(_hash: str, salt: str, mode: str, chars: str, mask: str, hashcat_path: str = compute.default_hashcat_location):
    result = run_hashcat(_hash=_hash, salt=salt, mode=mode, chars=chars, mask=mask, hashcat_path=hashcat_path)
    return result
