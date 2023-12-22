# The MIT License (MIT)
# Copyright © 2023 Rapiiidooo
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import hashlib
import random
import string

import torch
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from neurons.Validator.pow_miner import proof_of_work_miner


def string_to_tensor(string):
    return torch.tensor(bytearray(string.encode()), dtype=torch.uint8, device="cuda")


def generate_private_key() -> RSAPrivateKey:
    # Generating an RSA private key with a key size of 2048 bits
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    return private_key


def generate_random_question(private_key, length: int = 20):
    # Extracting bytes from the private key
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Use the private key bytes as seed for random number generation
    seed = int.from_bytes(private_bytes, byteorder="big")
    random.seed(seed)

    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(length))


def sign_question(question, private_key):
    # Signing the question with the private key
    signature = private_key.sign(
        question.encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return signature


def verify_signature(question, signature, public_key):
    # Vérification de la signature avec la clé publique
    try:
        public_key.verify(
            signature,
            question.encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return True
    except Exception as e:
        return False


def verify_answer(question, answer, difficulty_level, signature, public_key):
    # Verify the signature for the given question
    try:
        public_key.verify(
            signature,
            question.encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
    except Exception as e:
        return False

    # Calculate the hash of (question + answer) and check the difficulty level
    data = question + str(answer)
    hashed_data = hashlib.sha256(data.encode()).hexdigest()
    return hashed_data.startswith("0" * difficulty_level)


def proof_of_work():
    # Generating private/public keys
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    public_key = private_key.public_key()

    # Generating a random question of a certain length
    question = generate_random_question(private_key=private_key)

    # Difficulty: number of leading zeros in the answer
    difficulty_level = 4

    # Signing the question with the private key
    signature = sign_question(question, private_key)

    # Time limit to find an answer
    time_limit = 120  # in seconds

    nonce_found, valid_answer, time_taken = proof_of_work_miner(question, difficulty_level, time_limit, signature, public_key)
    print(valid_answer)
    if nonce_found is not None and verify_answer(question, valid_answer, difficulty_level, signature, public_key):
        print(f"Question: {question}")
        print(f"Nonce found: {nonce_found}")
        print(f"Valid answer: {valid_answer}")
        print(f"Time taken: {time_taken} seconds")
    else:
        print("Unable to find a valid answer within 120 seconds or the signature is not valid.")


if __name__ == "__main__":
    print(f"{proof_of_work()}")
