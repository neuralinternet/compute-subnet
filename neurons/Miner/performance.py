# The MIT License (MIT)
# Copyright © 2023 GitPhantomman

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
# Step 1: Import necessary libraries and modules
import json
from Miner.perfinfo import get_perf_info
import base64
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet

#Respond the execution of the application
def get_respond(input):
    try:
        decoded_pem = base64.b64decode(input)
        
        public_key = serialization.load_pem_public_key(decoded_pem)
        # Generate a random encryption key
        key = Fernet.generate_key()

        # Initialize the Fernet cipher with the key
        cipher_suite = Fernet(key)

        # Message to be encrypted
        system_info  = get_perf_info()

        # Encrypt the message
        encrypted_message = cipher_suite.encrypt(system_info)

       
        crypted_key = public_key.encrypt(
            key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        return_dict = {
            "key": base64.b64encode(crypted_key).decode(),
            "msg": base64.b64encode(encrypted_message).decode()
        }

        return json.dumps(return_dict)

    except Exception as e:
        return {}
