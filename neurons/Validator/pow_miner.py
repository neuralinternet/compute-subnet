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
import time

import torch
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


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


def proof_of_work_miner(question, difficulty_level, time_limit, signature, public_key):
    start_time = time.time()
    nonce = 0

    while time.time() - start_time < time_limit:
        if verify_answer(question, nonce, difficulty_level, signature, public_key):
            return nonce, hashlib.sha256((question + str(nonce)).encode()).hexdigest(), time.time() - start_time
        nonce += 1

    return None, None, None
