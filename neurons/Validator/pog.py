import hashlib
from itertools import zip_longest
import json
import secrets  # For secure random seed generation
import tempfile

import bittensor as bt
import numpy as np
import yaml


def load_yaml_config(file_path):
    """
    Load GPU performance data from a YAML file.
    """
    try:
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)
        return data
    except FileNotFoundError:
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    except yaml.YAMLError as e:
        raise ValueError(f"Error decoding YAML file {file_path}: {e}")

def identify_gpu(fp16_tflops, fp32_tflops, estimated_avram, gpu_data, reported_name=None, tolerance_pairs=None):
    """
    Identify GPU based on TFLOPS and AVRAM with a tolerance check for GPUs with similar fingerprints.

    Parameters:
        fp16_tflops (float): Measured FP16 TFLOPS.
        fp32_tflops (float): Measured FP32 TFLOPS.
        estimated_avram (float): Estimated available VRAM in GB.
        reported_name (str): GPU name reported by the system (optional).
        tolerance_pairs (dict): Dictionary of GPUs with similar performance to apply tolerance adjustments.

    Returns:
        str: Identified GPU name with tolerance handling.
    """
    tolerance_pairs = tolerance_pairs or {}  # Default to empty dict if not provided
    GPU_TFLOPS_FP16 = gpu_data["GPU_TFLOPS_FP16"]
    GPU_TFLOPS_FP32 = gpu_data["GPU_TFLOPS_FP32"]
    GPU_AVRAM = gpu_data["GPU_AVRAM"]

    combined_scores = []
    for gpu in GPU_TFLOPS_FP16.keys():
        fp16_theoretical = GPU_TFLOPS_FP16[gpu]
        fp32_theoretical = GPU_TFLOPS_FP32[gpu]
        avram_theoretical = GPU_AVRAM[gpu]

        fp16_deviation = abs(fp16_tflops - fp16_theoretical) / fp16_theoretical
        fp32_deviation = abs(fp32_tflops - fp32_theoretical) / fp32_theoretical
        avram_deviation = abs(estimated_avram - avram_theoretical) / avram_theoretical

        combined_score = (fp16_deviation + fp32_deviation + avram_deviation) / 3
        combined_scores.append((gpu, combined_score))
    
    # Sort by the lowest deviation
    identified_gpu = sorted(combined_scores, key=lambda x: x[1])[0][0]

    # Tolerance handling for nearly identical GPUs
    if reported_name:
        # Check if identified GPU matches the tolerance pair
        if identified_gpu in tolerance_pairs and reported_name == tolerance_pairs.get(identified_gpu):
            bt.logging.trace(f"[Tolerance Adjustment] Detected GPU {identified_gpu} matches reported GPU {reported_name}.")
            identified_gpu = reported_name
        # Check if reported GPU matches the tolerance pair in reverse
        elif reported_name in tolerance_pairs and identified_gpu == tolerance_pairs.get(reported_name):
            bt.logging.trace(f"[Tolerance Adjustment] Reported GPU {reported_name} matches detected GPU {identified_gpu}.")
            identified_gpu = reported_name

    return identified_gpu

def compute_script_hash(script_path):
    with open(script_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def send_script_and_request_hash(ssh_client, script_path):
    sftp = ssh_client.open_sftp()
    sftp.put(script_path, "/tmp/miner_script.py")
    sftp.close()

    # Command to compute the hash on the remote server
    hash_command = """
    /opt/conda/bin/python -c "
import hashlib
with open('/tmp/miner_script.py', 'rb') as f:
    computed_hash = hashlib.sha256(f.read()).hexdigest()
print(computed_hash)
"
    """
    stdin, stdout, stderr = ssh_client.exec_command(hash_command)
    computed_hash = stdout.read().decode().strip()
    hash_error = stderr.read().decode().strip()

    if hash_error:
        raise RuntimeError(f"Hash computation failed: {hash_error}")
    return computed_hash

def execute_script_on_miner(ssh_client, mode):
    execution_command = f"/opt/conda/bin/python /tmp/miner_script.py --mode {mode}"
    stdin, stdout, stderr = ssh_client.exec_command(execution_command)
    execution_output = stdout.read().decode().strip()
    execution_error = stderr.read().decode().strip()

    if execution_error:
        raise RuntimeError(f"Script execution failed: {execution_error}")
    return execution_output

def parse_benchmark_output(output):
    try:
        parts = output.strip().split()
        num_gpus = int(parts[0])  # First value is the number of GPUs
        vram = float(parts[1])
        size_fp16 = int(parts[2])
        time_fp16 = float(parts[3])
        size_fp32 = int(parts[4])
        time_fp32 = float(parts[5])
        return num_gpus, vram, size_fp16, time_fp16, size_fp32, time_fp32
    except (ValueError, IndexError) as e:
        raise ValueError(f"Failed to parse execution output: {output}") from e

def parse_merkle_output(output):
    try:
        lines = output.strip().split('\n')
        root_hashes_line = None
        timings_line = None
        for line in lines:
            if line.startswith('Root hashes:'):
                root_hashes_line = line
            elif line.startswith('Timings:'):
                timings_line = line
        if root_hashes_line is None or timings_line is None:
            raise ValueError("Output does not contain root hashes or timings")
        # Parse root hashes
        root_hashes_str = root_hashes_line.split(': ', 1)[1]
        root_hashes = json.loads(root_hashes_str)  # List of tuples (gpu_id, root_hash)

        # Parse timings
        timings_str = timings_line.split(': ', 1)[1]
        gpu_timings = json.loads(timings_str)  # List of tuples (gpu_id, timings_dict)

        return root_hashes, gpu_timings
    except (ValueError, IndexError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to parse execution output: {output}") from e

def get_random_seeds(num_gpus):
    seeds = {}
    for gpu_id in range(num_gpus):
        s_A = secrets.randbits(64)
        s_B = secrets.randbits(64)
        seeds[gpu_id] = (s_A, s_B)
    return seeds

def send_seeds(ssh_client, seeds, n):
    lines = [str(n)]  # First line is n
    for gpu_id in seeds.keys():
        s_A, s_B = seeds[gpu_id]
        line = f"{gpu_id} {s_A} {s_B}"
        lines.append(line)
    content = '\n'.join(lines)
    command = f"echo '{content}' > /tmp/seeds.txt"
    stdin, stdout, stderr = ssh_client.exec_command(command)
    stdout.channel.recv_exit_status()

def send_challenge_indices(ssh_client, indices):
    lines = []
    for gpu_id in indices.keys():
        idx_list = indices[gpu_id]
        indices_str = ';'.join([f"{i},{j}" for i, j in idx_list])
        line = f"{gpu_id} {indices_str}"
        lines.append(line)
    content = '\n'.join(lines)
    command = f"echo '{content}' > /tmp/challenge_indices.txt"
    stdin, stdout, stderr = ssh_client.exec_command(command)
    stdout.channel.recv_exit_status()

def receive_responses(ssh_client, num_gpus):
    responses = {}
    try:
        with ssh_client.open_sftp() as sftp, tempfile.TemporaryDirectory() as temp_dir:
            for gpu_id in range(num_gpus):
                remote_path = f'/dev/shm/responses_gpu_{gpu_id}.npy'
                local_path = f'{temp_dir}/responses_gpu_{gpu_id}.npy'
                
                try:
                    sftp.get(remote_path, local_path)
                    response = np.load(local_path, allow_pickle=True)
                    responses[gpu_id] = response.item()
                except Exception as e:
                    print(f"Error processing GPU {gpu_id}: {e}")
                    responses[gpu_id] = None
    except Exception as e:
        print(f"SFTP connection error: {e}")
    
    return responses

def xorshift32_numpy(state):
    state = np.uint64(state)
    x = state & np.uint64(0xFFFFFFFF)
    x ^= (np.uint64((x << np.uint64(13)) & np.uint64(0xFFFFFFFF)))
    x ^= (np.uint64((x >> np.uint64(17)) & np.uint64(0xFFFFFFFF)))
    x ^= (np.uint64((x << np.uint64(5)) & np.uint64(0xFFFFFFFF)))
    x = x & np.uint64(0xFFFFFFFF)
    return x

def generate_prng_value(s, i, j):
    s = np.uint64(s)
    i = np.uint64(i % np.uint64(2**32))
    j = np.uint64(j)
    state = (s + i + j) & np.uint64(0xFFFFFFFF)

    for _ in range(10):
        state = xorshift32_numpy(state)

    return state / float(0xFFFFFFFF)

def verify_responses(seeds, root_hashes, responses, indices, n):
    """
    Verifies the responses from GPUs by checking computed values and Merkle proofs.

    Parameters:
        seeds (dict): Seeds used for generating PRNG values for each GPU.
        root_hashes (dict): Merkle root hashes for each GPU.
        responses (dict): Responses from each GPU containing computed rows and proofs.
        indices (dict): Challenge indices for each GPU.
        n (int): Total number of leaves in the Merkle tree.

    Returns:
        bool: True if verification passes within the allowed failure threshold, False otherwise.
    """
    verification_passed = True
    failed_gpus = []
    num_gpus = len(root_hashes.keys())

    # Define the minimum number of GPUs that must pass verification
    if num_gpus == 4:
        required_passes = 3
    elif num_gpus > 4:
        # For systems with more than 4 GPUs, adjust the required_passes as needed
        # Example: Require at least 75% to pass
        required_passes = int(np.ceil(0.75 * num_gpus))
    else:
        # For systems with 2 or fewer GPUs, require all to pass
        required_passes = num_gpus

    for gpu_id in root_hashes.keys():
        s_A, s_B = seeds[gpu_id]
        gpu_indices = indices[gpu_id]
        response = responses[gpu_id]
        root_hash = root_hashes[gpu_id]
        total_leaves = n

        gpu_failed = False  # Flag to track if the current GPU has failed

        for idx, (i, j) in enumerate(gpu_indices):
            # Generate only the necessary row and column entries using PRNG
            A_row = np.array([generate_prng_value(s_A, i, col) for col in range(n)], dtype=np.float32)
            B_col = np.array([generate_prng_value(s_B, row, j) for row in range(n)], dtype=np.float32)

            # Compute C_{i,j} as the dot product of A_row and B_col
            value_validator = np.dot(A_row, B_col)

            # Retrieve miner's computed value and corresponding Merkle proof
            row_miner = response['rows'][idx]
            proof = response['proofs'][idx]
            value_miner = row_miner[j]

            # Check if the miner's value matches the expected value
            if not np.isclose(value_miner, value_validator, atol=1e-5):
                bt.logging.trace(f"[Verification] GPU {gpu_id}: Value mismatch at index ({i}, {j}).")
                gpu_failed = True
                break  # Exit the loop for this GPU as it has already failed

            # Verify the Merkle proof for the row
            if not verify_merkle_proof_row(row_miner, proof, bytes.fromhex(root_hash), i, total_leaves):
                bt.logging.trace(f"[Verification] GPU {gpu_id}: Invalid Merkle proof at index ({i}).")
                gpu_failed = True
                break  # Exit the loop for this GPU as it has already failed

        if gpu_failed:
            failed_gpus.append(gpu_id)
            bt.logging.trace(f"[Verification] GPU {gpu_id} failed verification.")
        else:
            bt.logging.trace(f"[Verification] GPU {gpu_id} passed verification.")

    # Calculate the number of GPUs that passed verification
    passed_gpus = num_gpus - len(failed_gpus)

    # Determine if verification passes based on the required_passes
    if passed_gpus >= required_passes:
        verification_passed = True
        bt.logging.trace(f"[Verification] SUCCESS: {passed_gpus} out of {num_gpus} GPUs passed verification.")
        if len(failed_gpus) > 0:
            bt.logging.trace(f"            Note: {len(failed_gpus)} GPU(s) failed verification but within allowed threshold.")
    else:
        verification_passed = False
        bt.logging.trace(f"[Verification] FAILURE: Only {passed_gpus} out of {num_gpus} GPUs passed verification.")
        if len(failed_gpus) > 0:
            bt.logging.trace(f"            {len(failed_gpus)} GPU(s) failed verification which exceeds the allowed threshold.")

    return verification_passed

def verify_merkle_proof_row(row, proof, root_hash, index, total_leaves, hash_func=hashlib.sha256):
    """
    Verifies a Merkle proof for a given row.

    Parameters:
    - row (np.ndarray): The data row to verify.
    - proof (list of bytes): The list of sibling hashes required for verification.
    - root_hash (bytes): The root hash of the Merkle tree.
    - index (int): The index of the row in the tree.
    - total_leaves (int): The total number of leaves in the Merkle tree.
    - hash_func (callable): The hash function to use (default: hashlib.sha256).

    Returns:
    - bool: True if the proof is valid, False otherwise.
    """
    # Initialize the computed hash with the hash of the row using the specified hash function
    computed_hash = hash_func(row.tobytes()).digest()
    idx = index
    num_leaves = total_leaves
    
    # Iterate through each sibling hash in the proof
    for sibling_hash in proof:
        if idx % 2 == 0:
            # If the current index is even, concatenate computed_hash + sibling_hash
            combined = computed_hash + sibling_hash
        else:
            # If the current index is odd, concatenate sibling_hash + computed_hash
            combined = sibling_hash + computed_hash
        # Compute the new hash using the specified hash function
        computed_hash = hash_func(combined).digest()
        # Move up to the next level
        idx = idx // 2
    
    # Compare the computed hash with the provided root hash
    return computed_hash == root_hash

def adjust_matrix_size(vram, element_size=2, buffer_factor=0.8):
    usable_vram = vram * buffer_factor * 1e9  # Usable VRAM in bytes
    max_size = int((usable_vram / (2 * element_size)) ** 0.5)  # Max size fitting in VRAM
    aligned_size = (max_size // 32) * 32  # Ensure alignment to multiple of 32
    return aligned_size

def get_remote_gpu_info(ssh_client):
    """
    Execute the miner script in gpu_info mode to get GPU information from the remote miner.

    Args:
        ssh_client (paramiko.SSHClient): SSH client connected to the miner.

    Returns:
        dict: Dictionary containing GPU information (number and names).
    """
    command = "/opt/conda/bin/python /tmp/miner_script.py --mode gpu_info"
    stdin, stdout, stderr = ssh_client.exec_command(command)

    output = stdout.read().decode().strip()
    error = stderr.read().decode().strip()

    if error:
        raise RuntimeError(f"Failed to get GPU info: {error}")

    return json.loads(output)

def query_remote_gpu(ssh_client):
    """
    Execute nvidia-smi -q to query GPU attributes from the remote miner.
    Args:
        ssh_client (paramiko.SSHClient): SSH client connected to the miner.
    Returns:
        dict: Dictionary containing GPU Serial Numbers, UUID and PCI Bus Id.
    """
    command = "nvidia-smi -q"
    _, stdout, stderr = ssh_client.exec_command(command)

    error = stderr.read().decode().strip()
    stdout = stdout.read().decode().strip()
    if error or not stdout:
        if error:
            bt.logging.trace(f"[Query] nvidia-smi -q execution failed: {error}.")
        # fall back to use docker --gpus all
        command = "docker run --gpus all --rm ubuntu nvidia-smi -q"
        _, stdout, stderr = ssh_client.exec_command(command)

        error = stderr.read().decode().strip()
        if error:
            raise RuntimeError(f"Failed to get GPU query data: {error}")

    serials = []
    uuids = []
    bus_ids = []
    for line in stdout.read().decode().strip().splitlines():
        key_value = line.strip().split(':', maxsplit=1)
        if len(key_value) == 1:
            continue
        value = key_value[1].strip()
        match key_value[0].strip():
            case 'Serial Number':
                serials.append(value)
            case 'GPU UUID':
                uuids.append(value)
            case 'Bus Id':
                bus_ids.append(value)
            case _:
                pass

    return {'gpu_serials': serials, 'gpu_uuids': uuids, 'pci_bus_ids': bus_ids}


def verify_uuids(ssh_client, gpu_uuids, pci_bus_ids):
    """
    Verifies the responses from GPUs query by checking linux nvidia driver information.

    Parameters:
        ssh_client (paramiko.SSHClient): SSH client connected to the miner.
        gpu_uuids (list): The UUIDs of GPU(s)
        pci_bus_ids (list): The PCI Bus Id of GPU(s)

    Returns:
        bool: True if verification passes, False otherwise.
    """
    if not gpu_uuids or not pci_bus_ids:
        bt.logging.trace("[Verification] FAILURE: Missing UUID/PCI Bus Id")
        return False

    # check uuid from driver info using pci bus id
    for uuid, pci_bus_id in zip_longest(gpu_uuids, pci_bus_ids, fillvalue=None):
        if uuid is None or pci_bus_id is None:
            bt.logging.trace(
                f"[Verification] FAILURE: Misaligned UUID/PCI Bus Id information: {uuid}/{pci_bus_id}"
            )
            return False

        command = f"cat /proc/driver/nvidia/gpus/{pci_bus_id}/information"
        _, stdout, stderr = ssh_client.exec_command(command)

        error = stderr.read().decode().strip()
        stdout = stdout.read().decode().strip()
        if error or not stdout or uuid not in stdout:
            bt.logging.trace(
                f"[Verification] FAILURE: UUID/PCI Bus Id information Value mismatch: {uuid}/{pci_bus_id}"
            )
            return False
    return True
