# The MIT License (MIT)
# Copyright © 2023 GitPhantom

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
import time
import bcrypt
import bittensor as bt

#The following function is responsible for hashing strings given in the input_list
def hash_str(input):
    #Encode count
    encode_count = input['complexity']

    #The list of input string
    input_list = input['str_list']

    #The list of hashed string
    result = []

    #Estimate the time frame
    start_time = time.time()
    
    #Hash strings with bcrypt
    for string in input_list:
        hashed = string.encode('utf-8')
        for index in range(encode_count):
            hashed = bcrypt.hashpw(hashed, b'$2b$12$9/zKmaaYPld3zfuC.Kb.Qe')
        result.append(hashed)

    elapsed_time = time.time() - start_time

    bt.logging.info(f"Clarify elapsed: {elapsed_time}")

    return result