# The MIT License (MIT)
# Copyright © 2023 Rapiiidooo
# Copyright © 2023 Crazydevlegend
# Copyright © 2023 GitPhantomman
# Copyright © 2024 Andrew O'Flaherty
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

from colorama import Fore, Style
import compute
import docker
import hashlib
from io import BytesIO
import os
import random
import readline
import secrets
import subprocess
import time
from typing import List, Union, Tuple

import bittensor as bt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

challenges_solved = {}
challenge_solve_durations = {}
challenge_totals = {}

min_diff = compute.pow_min_difficulty
max_diff = compute.pow_max_difficulty

class Challenge:
    """Store challenge object properties."""

    def __init__(self, 
    _hash: str = "",
    salt: str = "",
    mode: str = "",
    chars: str = "",
    mask: str = "",
    difficulty: int = min_diff,
    run_id: str = "",
    ):
        self._hash = _hash
        self.salt = salt
        self.mode = mode
        self.chars = chars
        self.mask = mask
        self.run_id = run_id
        self.difficulty = difficulty

def build_benchmark_container(image_name: str, container_name: str):
    """Create the benchmark container to check Docker's functionality."""

    client = docker.from_env()
    dockerfile = '''
    FROM alpine:latest
    CMD echo "compute-subnet"
    '''
    try:
        # Create a file-like object from the Dockerfile
        f = BytesIO(dockerfile.encode('utf-8'))

        # Build the Docker image
        image, _ = client.images.build(fileobj=f, tag=image_name)

        # Create the container from the built image
        container = client.containers.create(image_name, name=container_name)
        return container
    except docker.errors.BuildError:
        pass
    except docker.errors.APIError:
        pass
    finally:
        client.close()

def check_docker_availability() -> Tuple[bool, str]:
    """Check Docker is available and functioning correctly."""

    try:
        # Run 'docker --version' command
        result = subprocess.run(["docker", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        # If the command was successful, Docker is installed
        docker_version = result.stdout.strip()
        
        if check_docker_container('sn27-benchmark-container') is True:
            return True, docker_version
        else:
            error_message = "Docker is installed, but is unable to create or run a container. Please verify your system's permissions."
            return False, error_message
        
    except Exception as e:  # Catch all exceptions
        # If the command failed, Docker is not installed
        error_message = (
            "Docker is not installed or not found in the system PATH. "
            "Miner initialization has been stopped. Please install Docker and try running the miner again. "
            "Note: running a miner within containerized instances is not supported."
        )
        return False, error_message
    
def check_docker_container(container_id_or_name: str):
    """Confirm the benchmark container can be created and returns the correct output in its logs."""

    try:
        # Start the container
        subprocess.run(["docker", "start", container_id_or_name], 
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)

        # Wait for the container to finish running
        subprocess.run(["docker", "wait", container_id_or_name],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        
        # Get the logs from the container
        logs_result = subprocess.run(
            ["docker", "logs", container_id_or_name],
            capture_output=True,
            text=True,
            check=True
        )
        output = logs_result.stdout.strip()

        # Check if the output is compute-subnet
        if "compute-subnet" in output:
            return True
        else:
            return False

    except subprocess.CalledProcessError as e:
        # Handle errors from the Docker CLI
        return False
    
def check_cuda_availability():
    """Verify the number of available CUDA devices (Nvidia GPUs)"""

    import torch

    if torch.cuda.is_available():
        device_count = torch.cuda.device_count()
        print(Fore.GREEN + f"CUDA is available with {device_count} CUDA device(s)!")
    else:
        print(Fore.RED + "CUDA is not available or not properly configured on this system.")

def gen_hash(password, salt=None):
    """Generate the hash and salt for a challenge."""

    salt = secrets.token_hex(8) if salt is None else salt
    salted_password = password + salt
    data = salted_password.encode("utf-8")
    hash_result = hashlib.blake2b(data).hexdigest()
    return f"$BLAKE2${hash_result}", salt

def gen_hash_password(available_chars=compute.pow_default_chars, length=min_diff):
    """Generate a random string to be used as the challenge hash password."""

    # Generating private/public keys
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Using the private key bytes as seed for guaranteed randomness
    seed = int.from_bytes(private_bytes, "big")
    random.seed(seed)
    return "".join(random.choice(available_chars) for _ in range(length))

def gen_challenge_details(available_chars=compute.pow_default_chars, length=min_diff):
    """Generate the hashing details for a challenge."""

    try:
        password = gen_hash_password(available_chars=available_chars, length=length)
        _mask = "".join(["?1" for _ in range(length)])
        _hash, _salt = gen_hash(password)
        return password, _hash, _salt, _mask
    except Exception as e:
        print(f"Error during PoW generation (gen_challenge_details): {e}")
        return None

def gen_challenge(
    mode = compute.pow_default_mode,
    length = min_diff,
    run_id: str = ""
) -> Challenge:
    """Generate a challenge from a given hashcat mode, difficulty, and identifier."""
    
    challenge = Challenge()
    available_chars = compute.pow_default_chars
    available_chars = list(available_chars)
    random.shuffle(available_chars)
    available_chars = "".join(available_chars)
    password, challenge._hash, challenge.salt, challenge.mask = gen_challenge_details(available_chars=available_chars[:10], length=length)
    challenge.mode, challenge.chars, challenge.difficulty, challenge.run_id = mode, available_chars[:10], length, run_id
    return challenge

def hashcat_verify(_hash, output) -> Union[str, None]:
    """Verify the hashcat result is correct."""

    for item in output.split("\n"):
        if _hash in item:
            return item.strip().split(":")[-1]
    return None

def run_hashcat(
    challenges: List[Challenge],
    timeout: int = compute.pow_timeout,
    hashcat_path: str = compute.miner_hashcat_location,
    hashcat_workload_profile: str = "3",
    hashcat_extended_options: str = "",
) -> bool :
    """Solve a list of challenges and output the results."""

    for challenge in challenges:
        _hash = challenge._hash
        salt = challenge.salt
        mode = challenge.mode
        chars = challenge.chars
        mask = challenge.mask
        run_id = challenge.run_id
        difficulty = challenge.difficulty

        unknown_error_message = f"Difficulty {difficulty} challenge ID {run_id}: ❌ run_hashcat execution failed"
        start_time = time.time()

        try:

            command = [
                    hashcat_path,
                    f"{_hash}:{salt}",
                    "-a",
                    "3",
                    "-D",
                    "2",
                    "--session",
                    f"{run_id}",
                    "-m",
                    mode,
                    "-1",
                    str(chars),
                    mask,
                    "-w",
                    hashcat_workload_profile,
                    hashcat_extended_options,
                ]

            process = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

            execution_time = time.time() - start_time

            if process.returncode == 0:
                if process.stdout:
                    result = hashcat_verify(_hash, process.stdout)
                    bt.logging.success(
                        f"Difficulty {difficulty} challenge ID {run_id}: ✅ Result {result} found in {execution_time:0.2f} seconds !"
                    )

                    if difficulty in challenges_solved:
                        challenges_solved[difficulty] += 1
                        challenge_solve_durations[difficulty] += execution_time
                    else:
                        challenges_solved[difficulty] = 1
                        challenge_solve_durations[difficulty] = execution_time
                    continue
            else:
                error_message = f"Difficulty {difficulty} challenge ID {run_id}: ❌ Hashcat execution failed with code {process.returncode}: {process.stderr}"
                bt.logging.warning(error_message)
                continue

        except subprocess.TimeoutExpired:
            #execution_time = time.time() - start_time
            error_message = f"Difficulty {difficulty} challenge ID {run_id}: ❌ Hashcat execution timed out"
            bt.logging.warning(error_message)
            continue

        except Exception as e:
            #execution_time = time.time() - start_time
            bt.logging.warning(f"{unknown_error_message}: {e}")
            continue

        bt.logging.warning(f"{unknown_error_message}: no exceptions")

def format_difficulties(text: str = "") -> List[str]:
    """Format the challenge difficulty input text."""

    text = text.replace(" ", ",")
    text = text.replace("  ", ",")
    text = text.replace(",,", ",")

    if text.lower() == "all" or not text:
        return list(range(min_diff, max_diff + 1, 1))
    else:
        return [int(x) for x in text.split(",")] if "," in text else [int(text)]

def main():
    """Handle the core benchmarking logic."""

    # Use a list of challenges instead of a set to allow the entry of duplicate challenge difficulties
    challenges: List[Challenge] = []
    challenge = Challenge()
    benchmark_quantity: int
    hashcat_workload_profile: str = "3"
    hashcat_extended_options: str = "-O"

    os.system('clear')

    # Check CUDA devices and docker availability
    check_cuda_availability()
    build_benchmark_container('compute-subnet-benchmark','sn27-benchmark-container')
    has_docker, msg = check_docker_availability()

    if not has_docker:
        bt.logging.error(msg)
        print(Fore.RED + "DOCKER IS NOT INSTALLED OR IS NOT ACCESSIBLE. AS A RESULT, YOUR SCORE WILL BE REDUCED BY 50%!")
    else:
        print(Fore.GREEN + f"Docker is installed. Version: {msg}")
        print(Fore.YELLOW + "Please confirm port 4444 is open by running 'sudo ufw allow 4444'. Without this, validators cannot use your machine's resources.")

    print(Style.RESET_ALL)

    # Intake challenge difficulties and benchmark parameters
    print("Example 1: 6")
    print("Example 2: 7 8 9")
    print("Example 3: 10, 11, 12")
    print("Example 4: all" + "\n")

    while True:
        try:
            selected_difficulties = input("What challenge difficulties would you like to benchmark? Some examples are listed above. (all): ")
            challenge_difficulty_list = format_difficulties(selected_difficulties)
            break
        except:
            print("Please enter a valid difficulty or list of difficulties. You may also leave this section empty to benchmark all difficulties.")

    while True:
        try:
            benchmark_quantity = int(input("How many benchmarks would you like to perform? (1): ") or 1)
            break
        except:
            print("Please enter a number or leave this section empty to run the benchmark once.")

    try:
        hashcat_workload_profile = input("What hashcat workload profile (1, 2, 3, or 4) would you like to use? (3): ")
        if not hashcat_workload_profile:
            hashcat_workload_profile = "3"
        elif int(hashcat_workload_profile) not in range(0, 5):
            print("Invalid entry. Defaulting to workload profile 3.")
            hashcat_workload_profile = "3"
    except:
        print("Invalid entry. Defaulting to workload profile 3.")
        hashcat_workload_profile = "3"
        
    hashcat_extended_options = input("Enter any extra hashcat options to use. Leave this empty to use the recommended -O option. Enter None for no extended options. (-O): ")
    if hashcat_extended_options.lower() == "none":
        hashcat_extended_options = ""
    elif not hashcat_extended_options:
        hashcat_extended_options = "-O"

    if benchmark_quantity < 1:
        benchmark_quantity = 1

    # Sort the difficulty list so they're benchmarked in ascending difficulty order then generate the challenges from each entered difficulty
    challenge_difficulty_list.sort()

    for i, difficulty in enumerate(challenge_difficulty_list):
        current_diff = difficulty

        if difficulty < min_diff:
            print(Fore.YELLOW + f"Difficulty {difficulty} is below the minimum difficulty of {min_diff}. Adjusting it to {min_diff}.")
            current_diff = challenge_difficulty_list[i] = min_diff
        elif difficulty > max_diff:
            print(Fore.YELLOW + f"Difficulty {difficulty} is above the maximum difficulty of {max_diff}. Adjusting it to {max_diff}.")
            current_diff = challenge_difficulty_list[i] = max_diff

        for num in range(0, benchmark_quantity):
            if current_diff in challenge_totals:
                challenge_totals[current_diff] += 1
            else:
                challenge_totals[current_diff] = 1

            challenge = gen_challenge(length=current_diff, run_id=f"{current_diff}-{challenge_totals[current_diff]}")
            challenges.append(challenge)

    print(Style.RESET_ALL)

    # Run the benchmarks and output the results
    print(f"Hashcat profile set to {hashcat_workload_profile} with the following extended options: {'None' if not hashcat_extended_options else hashcat_extended_options}")
    print(f"Running {benchmark_quantity} benchmark(s) for the following challenge difficulties: {challenge_difficulty_list}" + "\n")
    run_hashcat(challenges, hashcat_workload_profile=hashcat_workload_profile, hashcat_extended_options=hashcat_extended_options)
    time.sleep(1)
    
    print("\n" + "Completed benchmarking with the following results:")
    # Convert the difficulty list to a set to prevent printing duplicate results. Sort the set to print the results in ascending difficulty order
    for difficulty in sorted(set(challenge_difficulty_list)):
        total = challenge_totals[difficulty]

        if difficulty in challenges_solved:
            solved = challenges_solved[difficulty]
            success_percentage = solved / total * 100
            solve_time = challenge_solve_durations[difficulty] / solved

            print(f"Difficulty {difficulty} | Successfully solved {solved}/{total} challenge(s) ({success_percentage:0.2f}%) with an average solve time of {solve_time:0.2f} seconds.")
        else:
            print(f"Difficulty {difficulty} | Failed all {total} challenge(s) with a 0% success rate.")

if __name__ == "__main__":
    main()