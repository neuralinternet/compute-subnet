#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import torch
import time
import sys
import os
import numpy as np
import hashlib
from multiprocessing.pool import ThreadPool
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
import gc

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512"

import subprocess
import sys

def get_gpu_info():
    """
    Detect the number and types of GPUs available on the system.

    Returns:
        dict: Dictionary containing the number of GPUs and their names.
    """
    if not torch.cuda.is_available():
        return {"num_gpus": 0, "gpu_names": []}

    num_gpus = torch.cuda.device_count()
    gpu_names = [torch.cuda.get_device_name(i) for i in range(num_gpus)]

    gpu_info = {"num_gpus": num_gpus, "gpu_names": gpu_names}

    print(json.dumps(gpu_info, indent=2))

def estimate_vram_size(buffer_factor=0.9, precision="fp16"):
    dtype = torch.float16 if precision == "fp16" else torch.float32
    element_size = 2 if precision == "fp16" else 4  # Size of each element in bytes
    total_elements = 1024 * 1024  # Start with a 1MB array

    try:
        while True:
            arr = torch.empty((total_elements,), dtype=dtype, device="cuda")
            total_elements *= 2
    except RuntimeError:
        total_elements //= 2  # Step back to last successful allocation
        vram_bytes = total_elements * element_size
        usable_vram = vram_bytes / (buffer_factor * 1e9)  # Convert to GB
        return usable_vram

def adjust_matrix_size(vram, element_size=2, buffer_factor=0.8):
    usable_vram = vram * buffer_factor * 1e9  # Usable VRAM in bytes
    max_size = int((usable_vram / (2 * element_size)) ** 0.5)  # Max size fitting in VRAM
    aligned_size = (max_size // 32) * 32  # Ensure alignment to multiple of 32
    return aligned_size

def get_seeds():
    """Read n and seeds from /tmp/seeds.txt."""
    if not os.path.exists('/tmp/seeds.txt'):
        print("Seeds file not found.")
        sys.exit(1)
    with open('/tmp/seeds.txt', 'r') as f:
        content = f.read().strip()
    lines = content.split('\n')
    n = int(lines[0])
    seeds = {}
    for line in lines[1:]:
        gpu_id, s_A, s_B = line.strip().split()
        gpu_id = int(gpu_id)
        s_A = int(s_A)
        s_B = int(s_B)
        seeds[gpu_id] = (s_A, s_B)
    return n, seeds

def get_challenge_indices():
    """Read challenge indices from /tmp/challenge_indices.txt."""
    if not os.path.exists('/tmp/challenge_indices.txt'):
        print("Challenge indices file not found.")
        sys.exit(1)
    with open('/tmp/challenge_indices.txt', 'r') as f:
        content = f.read().strip()
    lines = content.split('\n')
    indices = {}
    for line in lines:
        gpu_id, idx_str = line.strip().split()
        gpu_id = int(gpu_id)
        idx_list = [tuple(map(int, idx.split(','))) for idx in idx_str.split(';')]
        indices[gpu_id] = idx_list
    return indices


def build_merkle_tree_rows(C, hash_func=hashlib.sha256, num_threads=None):
    if num_threads is None:
        num_threads = 8

    n = C.shape[0]

    # Hash each row of C using the specified hash function
    def hash_row(i):
        return hash_func(C[i, :].tobytes()).digest()

    # Parallelize row hashing
    with ThreadPool(num_threads) as pool:
        leaves = pool.map(hash_row, range(n))

    tree = leaves.copy()
    num_leaves = len(leaves)
    offset = 0

    # Function to hash pairs of nodes using the specified hash function
    def hash_pair(i):
        left = tree[offset + i]
        if i + 1 < num_leaves:
            right = tree[offset + i + 1]
        else:
            right = left  # Duplicate if odd number of leaves
        return hash_func(left + right).digest()

    # Build the Merkle tree
    while num_leaves > 1:
        with ThreadPool(num_threads) as pool:
            # Process pairs of leaves
            new_level = pool.map(hash_pair, range(0, num_leaves, 2))
        tree.extend(new_level)
        offset += num_leaves
        num_leaves = len(new_level)

    root_hash = tree[-1]
    return root_hash, tree

def get_merkle_proof_row(tree, row_index, total_leaves):
    proof = []
    idx = row_index
    num_leaves = total_leaves
    offset = 0
    while num_leaves > 1:
        sibling_idx = idx ^ 1
        if sibling_idx < num_leaves:
            sibling_hash = tree[offset + sibling_idx]
        else:
            sibling_hash = tree[offset + idx]  # Duplicate if sibling is missing
        proof.append(sibling_hash)
        idx = idx // 2
        offset += num_leaves
        num_leaves = (num_leaves + 1) // 2
    return proof

def xorshift32_torch(state):
    state = state.type(torch.int64)
    x = state & 0xFFFFFFFF
    x = x ^ ((x << 13) & 0xFFFFFFFF)
    x = x ^ ((x >> 17) & 0xFFFFFFFF)
    x = x ^ ((x << 5) & 0xFFFFFFFF)
    x = x & 0xFFFFFFFF
    return x

def generate_matrix_torch(s, n):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    dtype = torch.int64

    # Prepare indices
    i_indices = torch.arange(n, dtype=dtype, device=device).repeat_interleave(n)
    j_indices = torch.arange(n, dtype=dtype, device=device).repeat(n)

    # Convert s to signed 64-bit integer
    s_signed = (s + 2**63) % 2**64 - 2**63
    s_tensor = torch.tensor(s_signed, dtype=dtype, device=device)

    # Modify the computation to prevent overflow
    # Since 4294967296 mod 2^32 is 0, we can adjust the computation
    i_mod = i_indices % (2**32)
    states = (s_tensor + i_mod + j_indices) & 0xFFFFFFFF

    for _ in range(10):
        states = xorshift32_torch(states)

    matrix = (states.float() / float(0xFFFFFFFF)).reshape(n, n)
    return matrix

def run_benchmark():
    # Detect number of GPUs
    num_gpus = torch.cuda.device_count()

    # Estimate available VRAM
    estimated_vram = estimate_vram_size(buffer_factor=1.0, precision="fp16")

    # Adjust matrix sizes
    matrix_size_fp16 = adjust_matrix_size(estimated_vram, element_size=2, buffer_factor=1.0)
    matrix_size_fp32 = adjust_matrix_size(estimated_vram, element_size=4, buffer_factor=0.5)

    # Run benchmarks
    elapsed_time_fp16 = benchmark_matrix_multiplication(matrix_size_fp16, precision="fp16")
    elapsed_time_fp32 = benchmark_matrix_multiplication(matrix_size_fp32, precision="fp32")

    # Output results
    print(f"{num_gpus} {estimated_vram:.2f} {matrix_size_fp16} {elapsed_time_fp16:.6f} {matrix_size_fp32} {elapsed_time_fp32:.6f}")

def benchmark_matrix_multiplication(size, precision="fp16"):
    dtype = torch.float16 if precision == "fp16" else torch.float32
    A = torch.randn(size, size, dtype=dtype, device="cuda")
    B = torch.randn(size, size, dtype=dtype, device="cuda")

    torch.cuda.synchronize()
    start_time = time.time()
    torch.matmul(A, B)
    torch.cuda.synchronize()
    elapsed_time = time.time() - start_time
    return elapsed_time

def process_gpu(gpu_id, s_A, s_B, n):
    """
    Process computations for a single GPU.

    Args:
        gpu_id (int): ID of the GPU to use.
        s_A (int): Seed for matrix A.
        s_B (int): Seed for matrix B.
        n (int): Size of the matrices.

    Returns:
        tuple: (root_hash_result, gpu_timing_result)
    """
    try:
        # Set the current device
        torch.cuda.set_device(gpu_id)
        device = torch.device(f'cuda:{gpu_id}')

        # Initialize timing dictionary
        gpu_timing = {}

        # Step 2: Generate A and B with received seeds using PRNG
        start_time_generation = time.time()

        # Clear cache before allocation
        torch.cuda.empty_cache()

        # Generate A and B matrices
        A_torch = generate_matrix_torch(s_A, n)
        B_torch = generate_matrix_torch(s_B, n)

        end_time_generation = time.time()
        generation_time = end_time_generation - start_time_generation
        gpu_timing['generation_time'] = generation_time
        gpu_timing['n'] = n

        # Step 3: Compute C on GPU
        start_time_multiplication = time.time()
        C_torch = torch.matmul(A_torch, B_torch)
        torch.cuda.synchronize(device)  # Ensure computation is finished
        end_time_multiplication = time.time()
        multiplication_time = end_time_multiplication - start_time_multiplication
        gpu_timing['multiplication_time'] = multiplication_time
        print(f"GPU {gpu_id}: Matrix multiplication time on GPU: {multiplication_time:.2f} seconds")

        # Step 4: Move C back to CPU for Merkle tree construction
        start_time_transfer_back = time.time()
        C = C_torch.cpu().numpy()
        end_time_transfer_back = time.time()
        transfer_back_time = end_time_transfer_back - start_time_transfer_back
        gpu_timing['transfer_back_time'] = transfer_back_time
        # Optional: Uncomment to log transfer time
        # print(f"GPU {gpu_id}: Data transfer from GPU time: {transfer_back_time:.2f} seconds")

        # Step 5: Construct Merkle tree over rows of C
        start_time_merkle = time.time()
        root_hash, merkle_tree = build_merkle_tree_rows(C)
        end_time_merkle = time.time()
        merkle_tree_time = end_time_merkle - start_time_merkle
        gpu_timing['merkle_tree_time'] = merkle_tree_time
        # Optional: Uncomment to log Merkle tree construction time and root hash
        # print(f"GPU {gpu_id}: Merkle tree over rows construction time: {merkle_tree_time:.2f} seconds")
        # print(f"GPU {gpu_id}: Root hash: {root_hash.hex()}")

        # Save root hash and timings
        root_hash_result = (gpu_id, root_hash.hex())
        gpu_timing_result = (gpu_id, gpu_timing)

        # Save Merkle tree and C for later proof generation
        np.save(f'/dev/shm/merkle_tree_gpu_{gpu_id}.npy', merkle_tree)
        np.save(f'/dev/shm/C_gpu_{gpu_id}.npy', C)

        # Free GPU memory
        del A_torch, B_torch, C_torch, C, merkle_tree
        torch.cuda.empty_cache()
        gc.collect()

        return root_hash_result, gpu_timing_result

    except Exception as e:
        print(f"Error processing GPU {gpu_id}: {e}")
        return None, None

def run_compute():
    """
    Run compute operations on all available GPUs in parallel.
    """
    if not torch.cuda.is_available():
        print("Error: No GPU detected.")
        sys.exit(1)

    # Detect number of GPUs
    num_gpus = torch.cuda.device_count()

    # Read n and seeds
    n, seeds = get_seeds()

    # Initialize lists to store root hashes and timings per GPU
    root_hashes = []
    gpu_timings = []

    # Use ThreadPoolExecutor to parallelize GPU tasks
    with ThreadPoolExecutor(max_workers=num_gpus) as executor:
        # Submit tasks for each GPU
        futures = []
        for gpu_id in range(num_gpus):
            s_A, s_B = seeds[gpu_id]
            futures.append(executor.submit(process_gpu, gpu_id, s_A, s_B, n))

        for future in as_completed(futures):
            root_hash_result, gpu_timing_result = future.result()
            if root_hash_result:
                root_hashes.append(root_hash_result)
            if gpu_timing_result:
                gpu_timings.append(gpu_timing_result)

    # Output root hashes and timings
    print(f"Root hashes: {json.dumps(root_hashes)}")
    print(f"Timings: {json.dumps(gpu_timings)}")

def run_proof_gpu(gpu_id, indices, num_gpus):
    # Set the GPU device
    torch.cuda.set_device(gpu_id)

    # Load data for the specific GPU
    gpu_indices = indices[gpu_id]
    merkle_tree = np.load(f'/dev/shm/merkle_tree_gpu_{gpu_id}.npy', allow_pickle=True)
    C = np.load(f'/dev/shm/C_gpu_{gpu_id}.npy')

    # Start proof generation
    start_time_proof = time.time()
    responses = {'rows': [], 'proofs': [], 'indices': gpu_indices}
    total_leaves = C.shape[0]

    for idx, (i, j) in enumerate(gpu_indices):
        row = C[i, :]
        proof = get_merkle_proof_row(merkle_tree, i, total_leaves)
        responses['rows'].append(row)
        responses['proofs'].append(proof)

    end_time_proof = time.time()
    proof_time = end_time_proof - start_time_proof
    print(f"GPU {gpu_id}: Proof generation time: {proof_time:.2f} seconds")

    # Save responses to shared memory
    np.save(f'/dev/shm/responses_gpu_{gpu_id}.npy', responses)

def run_proof():
    # Get the challenge indices
    indices = get_challenge_indices()
    num_gpus = torch.cuda.device_count()

    # Use ThreadPoolExecutor for parallel GPU processing
    with ThreadPoolExecutor(max_workers=num_gpus) as executor:
        futures = [
            executor.submit(run_proof_gpu, gpu_id, indices, num_gpus)
            for gpu_id in range(num_gpus)
        ]
        # Wait for all threads to complete
        for future in futures:
            future.result()  # To raise any exceptions that occurred in the threads

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Miner script for GPU proof.')
    parser.add_argument('--mode', type=str, default='benchmark',
                        choices=['benchmark', 'compute', 'proof', 'gpu_info'],
                        help='Mode to run: benchmark, compute, proof, or gpu_info')
    args = parser.parse_args()

    if args.mode == 'benchmark':
        run_benchmark()
    elif args.mode == 'compute':
        run_compute()
    elif args.mode == 'proof':
        run_proof()
    elif args.mode == 'gpu_info':
        get_gpu_info()
