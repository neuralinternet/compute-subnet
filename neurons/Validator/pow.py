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

import bittensor as bt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import compute


def gen_hash(password):
    salt = secrets.token_hex(16)
    salted_password = password + salt
    data = salted_password.encode("utf-8")
    hash_result = hashlib.sha256(data).hexdigest()
    return hash_result, salt


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


def gen_password(length=compute.pow_min_difficulty):
    try:
        password = gen_random_string(length=length)
        _hash, _salt = gen_hash(password)
        return password, _hash, _salt
    except Exception as e:
        bt.logging.error(f"Error during PoW generation (gen_password): {e}")
        return None


def run_validator_pow(length=compute.pow_min_difficulty):
    """
    Don't worry this function is fast enough for validator to use CPUs
    """
    password, _hash, _salt = gen_password(length=length)
    return password, _hash, _salt, compute.pow_default_mode, compute.pow_default_chars, compute.pow_default_mask
