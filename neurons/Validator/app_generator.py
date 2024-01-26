# The MIT License (MIT)
# Copyright © 2023 Crazydevlegend

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

import os
import re

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
# Step 1: Import necessary libraries and modules
import subprocess

import bittensor as bt


def run(secret_key):
    try:
        main_dir = os.path.dirname(os.path.abspath(__file__))
        script_name = os.path.join(main_dir, "script.py")

        # Read the content of the script.py file
        with open(script_name, "r") as file:
            script_content = file.read()

        # Find and replace the script_key value

        pattern = r"secret_key\s*=\s*.*?#key"
        script_content = re.sub(pattern, f"secret_key = {secret_key}#key", script_content, count=1)

        # Write the modified content back to the file
        with open(script_name, "w") as file:
            file.write(script_content)

        # Run the pyinstaller command
        command = f"cd {main_dir}\npyinstaller --onefile script.py"
        try:
            subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            bt.logging.error("An error occurred while generating the app.")
            bt.logging.error(f"Error output:{e.stderr.decode()}")
    except Exception as e:
        bt.logging.error(f"{e}")
