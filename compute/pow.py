import hashlib

import torch

__all__ = ["calculate_hash"]


def simple_calculate_hash(header, nonce):
    data = f"{header}{nonce}".encode("utf-8")
    hash_result = hashlib.sha256(data).hexdigest()
    return hash_result


def calculate_hash(header, nonce):
    data = f"{header}{nonce}".encode("utf-8")

    # Convert data to a PyTorch tensor
    try:
        tensor_data = torch.tensor(bytearray(data), dtype=torch.uint8, device="cuda")
    except Exception as e:
        return simple_calculate_hash(header=header, nonce=nonce)

    # Use PyTorch's SHA-256 implementation
    sha256 = hashlib.sha256()
    sha256.update(tensor_data.numpy())  # Update the hash object with the tensor data
    hash_result = sha256.hexdigest()

    return hash_result
