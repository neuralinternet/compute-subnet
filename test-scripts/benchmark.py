# The MIT License (MIT)
# Copyright © 2023 Rapiiidooo
# Copyright © 2023 Crazydevlegend
# Copyright © 2023 GitPhantomman
# Copyright © 2024 Andrew O'Flaherty
# Copyright © 2024 Thomas Chu
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
import threading

import bittensor as bt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import base64
import struct

challenges_solved = {}
challenge_solve_durations = {}
challenge_totals = {}
challenge_allocated = {}

min_diff = compute.pow_min_difficulty
max_diff = compute.pow_max_difficulty

pow_quantity = 3

pow_mode_list = ["610", "8900", "1410", "10810", "1710", "7801", "19500"]
pow_mode_blake2b = "610"
pow_mode_scrypt = "8900"
pow_mode_sha256 = "1410"
pow_mode_sha384 = "10810"
pow_mode_sha512 = "1710"
pow_mode_sap = "7801"
pow_mode_ruby = "19500"

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
        result = subprocess.run(["docker", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                check=True)
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


def random_numeric_string(length):
    numbers = '0123456789'
    return ''.join([numbers[random.randint(0, 9)] for _ in range(length)])


def gen_hash(password, salt=None, mode: str = compute.pow_default_mode):
    """
    Generate the hash and salt for a challenge.
    :param password: The password to hash.
    :param salt: The salt to use for the hash.
    :param mode: The hashcat mode to use for the hash.
    :return: The hash and salt for the challenge.
    """
    if mode == pow_mode_scrypt: # For Scrypt
        salt = secrets.token_bytes(24) if salt is None else base64.b64decode(salt.encode("utf-8"))
        password_bytes = password.encode('ascii')
        hashed_password = hashlib.scrypt(password_bytes, salt=salt, n=1024, r=1, p=1, dklen=32)
        hash_result = str(base64.b64encode(hashed_password).decode('utf-8'))
        salt = str(base64.b64encode(salt).decode('utf-8'))
        return f"SCRYPT:1024:1:1:{hash_result}", salt
    elif mode== pow_mode_blake2b or mode== pow_mode_sha256 or mode== pow_mode_sha384 or mode== pow_mode_sha512:  # For Blake2b-512, SHA-256, SHA-384, SHA-512
        salt = secrets.token_hex(8) if salt is None else salt
        salted_password = password + salt
        data = salted_password.encode("utf-8")
        padding = ""
        if mode == pow_mode_blake2b:
            hash_result = hashlib.blake2b(data).hexdigest()
            padding = "$BLAKE2$"
        elif mode == pow_mode_sha256:
            hash_result = hashlib.sha256(data).hexdigest()
        elif mode == pow_mode_sha384:
            hash_result = hashlib.sha384(data).hexdigest()
        elif mode == pow_mode_sha512:
            hash_result = hashlib.sha512(data).hexdigest()
        return f"{padding}{hash_result}", salt
    elif mode == pow_mode_sap: # For SAP CODVN F/G (PASSCODE)
        if not salt:
            salt = random_numeric_string(8)

        theMagicArray_s = (
            b"\x91\xac\x51\x14\x9f\x67\x54\x43\x24\xe7\x3b\xe0\x28\x74\x7b\xc2"
            b"\x86\x33\x13\xeb\x5a\x4f\xcb\x5c\x08\x0a\x73\x37\x0e\x5d\x1c\x2f"
            b"\x33\x8f\xe6\xe5\xf8\x9b\xae\xdd\x16\xf2\x4b\x8d\x2c\xe1\xd4\xdc"
            b"\xb0\xcb\xdf\x9d\xd4\x70\x6d\x17\xf9\x4d\x42\x3f\x9b\x1b\x11\x94"
            b"\x9f\x5b\xc1\x9b\x06\x05\x9d\x03\x9d\x5e\x13\x8a\x1e\x9a\x6a\xe8"
            b"\xd9\x7c\x14\x17\x58\xc7\x2a\xf6\xa1\x99\x63\x0a\xd7\xfd\x70\xc3"
            b"\xf6\x5e\x74\x13\x03\xc9\x0b\x04\x26\x98\xf7\x26\x8a\x92\x93\x25"
            b"\xb0\xa2\x0d\x23\xed\x63\x79\x6d\x13\x32\xfa\x3c\x35\x02\x9a\xa3"
            b"\xb3\xdd\x8e\x0a\x24\xbf\x51\xc3\x7c\xcd\x55\x9f\x37\xaf\x94\x4c"
            b"\x29\x08\x52\x82\xb2\x3b\x4e\x37\x9f\x17\x07\x91\x11\x3b\xfd\xcd"
        )

        salt = salt.upper()
        word_salt = (password + salt).encode('utf-8')
        digest = hashlib.sha1(word_salt).digest()

        a, b, c, d, e = struct.unpack("IIIII", digest)

        length_magic_array = 0x20
        offset_magic_array = 0

        length_magic_array += ((a >> 0) & 0xff) % 6
        length_magic_array += ((a >> 8) & 0xff) % 6
        length_magic_array += ((a >> 16) & 0xff) % 6
        length_magic_array += ((a >> 24) & 0xff) % 6
        length_magic_array += ((b >> 0) & 0xff) % 6
        length_magic_array += ((b >> 8) & 0xff) % 6
        length_magic_array += ((b >> 16) & 0xff) % 6
        length_magic_array += ((b >> 24) & 0xff) % 6
        length_magic_array += ((c >> 0) & 0xff) % 6
        length_magic_array += ((c >> 8) & 0xff) % 6
        offset_magic_array += ((c >> 16) & 0xff) % 8
        offset_magic_array += ((c >> 24) & 0xff) % 8
        offset_magic_array += ((d >> 0) & 0xff) % 8
        offset_magic_array += ((d >> 8) & 0xff) % 8
        offset_magic_array += ((d >> 16) & 0xff) % 8
        offset_magic_array += ((d >> 24) & 0xff) % 8
        offset_magic_array += ((e >> 0) & 0xff) % 8
        offset_magic_array += ((e >> 8) & 0xff) % 8
        offset_magic_array += ((e >> 16) & 0xff) % 8
        offset_magic_array += ((e >> 24) & 0xff) % 8

        hash_str = (password.encode('utf-8') +
                theMagicArray_s[offset_magic_array:offset_magic_array + length_magic_array] +
                salt.encode('utf-8'))

        hash_buf = hashlib.sha1(hash_str).hexdigest()
        hash_val = salt + "$" + hash_buf.upper()[:20] + "0" * 20
        return hash_val, salt

    elif mode == pow_mode_ruby: # For Ruby on Rails Restful-Authentication
        if not salt:
            salt = random_numeric_string(12)
        site_key = random_numeric_string(12)
        # Construct the base string with separators
        base_string = f"{site_key}--{salt}--{password}--{site_key}"
        # Apply SHA-1 iteratively for 10 rounds (including the initial one)
        digest = hashlib.sha1(base_string.encode('utf-8')).hexdigest()
        for _ in range(9):
            digest = hashlib.sha1(f"{digest}--{salt}--{password}--{site_key}".encode('utf-8')).hexdigest()
        # Format the final hash string
        return f"{digest}", f"{salt}:{site_key}"

    else:
        bt.logging.error("Not recognized hash mode")
        return


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

def gen_challenge_details(available_chars=compute.pow_default_chars, length=min_diff, mode: str = compute.pow_default_mode):
    """Generate the hashing details for a challenge."""

    try:
        password = gen_hash_password(available_chars=available_chars, length=length)
        _mask = "".join(["?1" for _ in range(length)])
        _hash, _salt = gen_hash(password=password, mode=mode)
        return password, _hash, _salt, _mask
    except Exception as e:
        print(f"Error during PoW generation (gen_challenge_details): {e}")
        return None

def gen_challenge(
        length=min_diff,
        run_id: str = "",
        device_list: List[str] = [],
        random_challenge: str = "N",
) -> Challenge:
    """Generate a challenge from a given hashcat mode, difficulty, and identifier."""

    challenge = Challenge()
    if random_challenge=="Y" or random_challenge=="y":
        challenge.mode = random.choice(pow_mode_list)
    else:
        challenge.mode = compute.pow_default_mode
    available_chars = compute.pow_default_chars
    available_chars = list(available_chars)
    random.shuffle(available_chars)
    available_chars = "".join(available_chars)
    password, challenge._hash, challenge.salt, challenge.mask = gen_challenge_details(
        available_chars=available_chars[:10], length=length, mode=challenge.mode)
    challenge.chars, challenge.difficulty, challenge.run_id = available_chars[:10], length, run_id
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
        device_list: List[str] = [],
        run_sequence: bool = False,

) -> bool:
    """Solve a list of challenges and output the results."""
    threading_list = []
    max_device_id = len(device_list)
    device_id = 1

    for challenge in challenges:
        _hash = challenge._hash
        salt = challenge.salt
        mode = challenge.mode
        chars = challenge.chars
        mask = challenge.mask
        run_id = challenge.run_id
        difficulty = challenge.difficulty

        bt.logging.info(f"Running hash:{_hash} with id:{run_id} with mode:{mode} on #{device_id} GPU ")
        if device_id in challenge_allocated:
            challenge_allocated[device_id] += 1
        else:
            challenge_allocated[device_id] = 1

        if run_sequence:
            # hashcat thread function
            threading_list.append(
                threading.Thread(target=hashcat_thread, args=(difficulty, hashcat_path, _hash, salt, run_id, mode,
                                                              chars, mask, hashcat_workload_profile,
                                                              hashcat_extended_options, device_id)))
            if device_id < max_device_id:
                device_id += 1
            else:
                device_id = 1
        else:
            hashcat_thread(difficulty, hashcat_path, _hash, salt, run_id, mode, chars, mask, hashcat_workload_profile,
                           hashcat_extended_options, device_id)

    if run_sequence:
        for task in threading_list:
            task.start()

        for task in threading_list:
            task.join()


def format_difficulties(text: str = "") -> List[int]:
    """Format the challenge difficulty input text."""

    text = text.replace(" ", ",")
    text = text.replace("  ", ",")
    text = text.replace(",,", ",")

    # Use ":" to easy generate multiple challenges of the same difficulty
    if ":" in text:
        return [int(text.split(":")[0]) for _ in range(int(text.split(":")[1]))]

    if text.lower() == "all" or not text:
        return list(range(min_diff, max_diff + 1, 1))
    else:
        return [int(x) for x in text.split(",")] if "," in text else [int(text)]


# get the list of cuda devices
def get_cuda_device_list() -> List:
    device_list = []
    command = ["nvidia-smi", "--query-gpu=gpu_name,gpu_bus_id,vbios_version,memory.total", "--format=csv"]
    result = subprocess.run(command, capture_output=True, text=True).stdout
    device_list = [item for item in result.split("\n")[1:-1]]
    print(f"Found Devices:",device_list)
    return device_list

# Hashcat thread to handle send multiple hashcat commands to the GPU devices
def hashcat_thread(difficulty: int, hashcat_path: str, _hash: str, salt: str, run_id: str, mode: str, chars: str, mask: str,
                   hashcat_workload_profile: str, hashcat_extended_options: str, device_id: int):
    start_time = time.time()
    unknown_error_message = f"Difficulty {difficulty} challenge ID {run_id}: ❌ run_hashcat execution failed"

    # Check the hash algorithm and construct the hash and salt string accordingly
    if mode == pow_mode_scrypt:
        _hash_str = ":".join(_hash.split(":")[0:4]) + ":" + salt + ":" + _hash.split(":")[4]
    elif mode == pow_mode_sap:
        _hash_str = f"{_hash}"
    else:
        _hash_str = f"{_hash}:{salt}"

    try:
        command = [
            hashcat_path,
            _hash_str,
            "-a",
            "3",
            "-d",
            str(device_id),
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
            "--potfile-disable",
            "--runtime",
            "30",
        ]

        execute_command = " ".join(command)
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
        )

        execution_time = time.time() - start_time

        if process.returncode == 0:
            if process.stdout:
                if mode == pow_mode_scrypt:
                    _hash = ":".join(_hash.split(":")[0:4]) + ":" + salt + _hash.split(":")[4]
                result = hashcat_verify(_hash, process.stdout)
                # Convert hashcat output the $HEX[] format
                if "$HEX" in result:
                    result = decode_hex(result)
                    bt.logging.info(f"{run_id}: ✅ Convert $HEX format to {result}")
                bt.logging.success(
                    f"Difficulty {difficulty} challenge ID {run_id}: ✅ Result {result} found in {execution_time:0.2f} seconds !"
                )

                # check the challenges_solved dictionary with each GPU device
                if device_id in challenges_solved:
                    if difficulty in challenges_solved[device_id]:
                        challenges_solved[device_id][difficulty] = challenges_solved[device_id][difficulty]  + 1
                        challenge_solve_durations[device_id][difficulty] = (challenge_solve_durations[device_id][difficulty]
                                                                            + execution_time)
                    else:
                        challenges_solved[device_id].update({difficulty: 1})
                        challenge_solve_durations[device_id].update({difficulty: execution_time})
                else:
                    challenges_solved[device_id] = {difficulty: 1}
                    challenge_solve_durations[device_id] = {difficulty: execution_time}

        else:
            error_message = f"Difficulty {difficulty} challenge ID {run_id}: ❌ Hashcat execution failed with code {process.returncode}: {process.stderr}"
            bt.logging.warning(error_message)

    except subprocess.TimeoutExpired:
        # execution_time = time.time() - start_time
        error_message = f"Difficulty {difficulty} challenge ID {run_id}: ❌ Hashcat execution timed out"
        bt.logging.warning(error_message)

    except Exception as e:
        # execution_time = time.time() - start_time
        bt.logging.warning(f"{unknown_error_message}: {e}")

    # bt.logging.warning(f"{unknown_error_message}: no exceptions")

def decode_hex(password):
    decoded = []
    pwd = password
    if "$HEX" in password:
        multihex = list(filter(None, password.split("$")))
        for x in multihex:
            if "HEX[" in x:
                endhex = x.find("]")
                try:
                    decoded.append((bytes.fromhex(x[4:endhex]).decode("utf-8")))
                except:
                    decoded.append((bytes.fromhex(x[4:endhex]).decode("cp1252")))
            else:
                decoded.append(x)
        if len(decoded) != 0:
            pwd = ''.join(decoded)
        return (pwd)
    else:
        return (pwd)

def main():
    """Handle the core benchmarking logic."""

    # Use a list of challenges instead of a set to allow the entry of duplicate challenge difficulties
    challenges: List[Challenge] = []
    challenge = Challenge()
    benchmark_quantity: int
    hashcat_workload_profile: str = "3"
    hashcat_extended_options: str = "-O"
    cuda_list = get_cuda_device_list()
    # For the random challenge
    random_challenge: str = "N"

    os.system('clear')

    # Check CUDA devices and docker availability
    check_cuda_availability()

    build_benchmark_container('compute-subnet-benchmark', 'sn27-benchmark-container')
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
    print("Example 4: 6:7") # For generate 7 challenges of difficulty 6
    print("Example 5: all" + "\n")

    while True:
        try:
            selected_difficulties = input(
                "What challenge difficulties would you like to benchmark? Some examples are listed above. (all): ")
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

    hashcat_extended_options = input(
        "Enter any extra hashcat options to use. Leave this empty to use the recommended -O option. Enter None for no extended options. (-O): ")
    if hashcat_extended_options.lower() == "none":
        hashcat_extended_options = ""
    elif not hashcat_extended_options:
        hashcat_extended_options = "-O"

    # Input selection for random hashcat challenge algorithm
    try:
        random_challenge = input("Would you like to use random hashcat challenge algorithm? (Y/N, default: N): ")
        if random_challenge == "Y" or random_challenge == "y":
            random_challenge = "Y"
        else:
            random_challenge = "N"
    except:
        random_challenge = "N"

    try:
        run_sequence = input("Would you like to run hashcat challenge in parallel? (Y/N, default: N): ")
        if run_sequence == "Y" or run_sequence == "y":
            run_sequence = True
        else:
            run_sequence = False
    except:
        run_sequence = False

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

            challenge = gen_challenge(length=current_diff,
                                    run_id=f"{current_diff}-{challenge_totals[current_diff]}", random_challenge=random_challenge)
            challenges.append(challenge)

    print(Style.RESET_ALL)

    # Run the benchmarks and output the results
    print(f"Hashcat profile set to {hashcat_workload_profile} with the following extended options: {'None' if not hashcat_extended_options else hashcat_extended_options}")
    print(f"Running {benchmark_quantity} benchmark(s) for the following challenge difficulties: {challenge_difficulty_list}" + "\n")
    run_hashcat(challenges=challenges, hashcat_workload_profile=hashcat_workload_profile,
                hashcat_extended_options=hashcat_extended_options, device_list=cuda_list, run_sequence=run_sequence)
    time.sleep(1)
    # print(challenges_solved)
    # print(challenge_solve_durations)

    print("\n" + "Completed benchmarking with the following results:")
    # Convert the difficulty list to a set to prevent printing duplicate results. Sort the set to print the results in ascending difficulty order
    # Loop the device_id to print the results for each GPU device
    for dev_id in range(1, len(cuda_list) + 1):
        if dev_id in challenge_allocated:
            print(f"GPU #{str(dev_id)} results:")
            for difficulty in sorted(set(challenge_difficulty_list)):
                total = challenge_totals[difficulty]
                total_by_device = challenge_allocated[dev_id]

                if challenges_solved and difficulty in challenges_solved[dev_id]:
                    solved = challenges_solved[dev_id][difficulty]
                    success_percentage = solved / total * 100
                    success_percentage_device = solved / total_by_device * 100
                    solve_time = challenge_solve_durations[dev_id][difficulty] / solved

                    print(
                        f"Difficulty {difficulty} | Successfully solved {solved}/{total} challenge(s) ({success_percentage:0.2f}%) with an average solve time of {solve_time:0.2f} seconds.")
                    print(
                        f"Total: Difficulty {difficulty} | Successfully solved {solved}/{total_by_device} challenge(s) ({success_percentage_device:0.2f}%) on GPU#{str(dev_id)} with an average solve time of {solve_time:0.2f} seconds.")
                else:
                    print(f"Difficulty {difficulty} | Failed all {total} challenge(s) with a 0% success rate.")
            print("")

if __name__ == "__main__":
    main()
