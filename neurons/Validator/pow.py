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

    if mode == compute.pow_mode_sap_codvn_b:
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
        # CODVN B uses md5 instead of sha1
        hash_buf = hashlib.md5(hash_str).hexdigest()
        hash_val = salt + "$" + hash_buf.upper()[:20] + "0" * 20
        return hash_val, salt
    elif mode == compute.pow_mode_ruby_on_rails_ra:
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


def gen_password(available_chars=compute.pow_default_chars, length=compute.pow_min_difficulty):
    try:
        password = gen_random_string(available_chars=available_chars, length=length)
        _mask = "".join(["?1" for _ in range(length)])
        _hash, _salt = gen_hash(password)
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
    mode = compute.pow_modes_list[random.randint(0, len(compute.pow_modes_list))]
    password, _hash, _salt, _mask = gen_password(available_chars=available_chars[:10], length=length)
    return password, _hash, _salt, mode, available_chars[:10], _mask
