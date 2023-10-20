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
import paramiko
import os
import datetime
import threading
import time
import bittensor as bt

file_path = []
desired_timestamp = 0

#This function is responsible for deleting ssh key file at given timestamp
def delete_file_at_timestamp():
    while True:
        current_timestamp = int(time.time())
        if current_timestamp >= desired_timestamp:
            try:
                if(file_path != []):
                    os.remove(file_path[0])
                    os.remove(file_path[1])
                break
            except OSError as e:
                bt.logging.info(f"Error deleting file: {e}")
        time.sleep(10)

deletion_thread = threading.Thread(target=delete_file_at_timestamp)

#The following function is responsible for registering a new ssh key
def register(timeline, passphrase=None):
    #Generate path for private and public keys
    #key_filename = str(datetime.datetime.now().timestamp())
    key_filename = "key"
    home_directory = os.path.expanduser("~")
    ssh_directory = os.path.join(home_directory, ".ssh")
    private_path = os.path.join(ssh_directory, key_filename)
    pub_path = os.path.join(ssh_directory, key_filename + ".pub")

    path = [private_path, pub_path]
    desired_timestamp = datetime.datetime.now().timestamp() + timeline
    deletion_thread.start()
    #If the private key is existed, return it
    if os.path.exists(private_path):
        with open(private_path, "r") as file:
            file_contents = file.read()
            return file_contents

    #Otherwise generate new private and public keys and save them
    key = paramiko.RSAKey.generate(2048)
    key.write_private_key_file(private_path, password=passphrase)
    with open(pub_path, 'w') as public_key_file:
        public_key_file.write(f'{key.get_name()} {key.get_base64()}')
    
    return key


#The following function is responsible for deregistering the given ssh key
def deregister(ssh_key):
    #Generate path for private and public keys
    key_filename = "key"
    home_directory = os.path.expanduser("~")
    ssh_directory = os.path.join(home_directory, ".ssh")
    private_path = os.path.join(ssh_directory, key_filename)
    pub_path = os.path.join(ssh_directory, key_filename + ".pub")

    #If the keys are already existed, return successed
    if os.path.exists(private_path):
        os.remove(private_path)
        os.remove(pub_path)
        return "SUCCESSED"
    
    return "FAILED"