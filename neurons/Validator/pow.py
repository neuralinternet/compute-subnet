# The MIT License (MIT)
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
import hashlib
import random
import secrets
import struct

import bittensor as bt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import compute


def random_numeric_string(length):
    numbers = '0123456789'
    return ''.join([numbers[random.randint(0, 9)] for _ in range(length)])

def gen_hash(password, mode=compute.pow_default_mode, salt=None):
    if salt is None:
        salt = secrets.token_hex(8) if mode == compute.pow_mode_blake2b512 else random_numeric_string(8)
    salted_password = password + salt
    data = salted_password.encode("utf-8")

    if mode == compute.pow_mode_ruby_on_rails_ra:
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
    # compute.pow_mode_blake2b512:
    hash_result = hashlib.blake2b(data).hexdigest()
    return f"$BLAKE2${hash_result}", salt


def gen_random_string(available_chars=compute.pow_default_chars, length=compute.pow_min_difficulty):
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


def gen_password(available_chars=compute.pow_default_chars, length=compute.pow_min_difficulty, mode=compute.pow_default_mode):
    try:
        password = gen_random_string(available_chars=available_chars, length=length)

        _mask = "".join(["?1" for _ in range(length)])
        _hash, _salt = gen_hash(password, mode)
        return password, _hash, _salt, _mask
    except Exception as e:
        bt.logging.error(f"Error during PoW generation (gen_password): {e}")
        return None


def run_validator_pow(length=compute.pow_min_difficulty):
    """
    Don't worry this function is fast enough for validator to use CPUs
    """
    available_chars = compute.pow_default_chars
    available_chars = list(available_chars)
    random.shuffle(available_chars)
    available_chars = "".join(available_chars)
    # only 2 modes for now, might switch to just 19500 to incentivize better GPUs
    mode = compute.pow_modes_list[random.randint(0, len(compute.pow_modes_list))]
    # parametrize length by mode, a 10-char 19500 hash is as hard as a 12-char 610 hash
    if mode == compute.pow_mode_ruby_on_rails_ra:
        length -= 2
    password, _hash, _salt, _mask = gen_password(available_chars=available_chars[:10], length=length, mode=mode)
    return password, _hash, _salt, mode, available_chars[:10], _mask
