# The MIT License (MIT)
# Copyright © 2023

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

import bittensor as bt

from compute import pow_min_difficulty

__all__ = ["Challenge", "Allocate", "DeviceInfo"]


class Challenge(bt.Synapse):
    """
    A challenge protocol representation which uses bt.Synapse as its base.
    This protocol helps in handling performance information request and response communication between
    the miner and the validator.
    """

    # Query parameters
    challenge_header: str = ""
    challenge_difficulty: int = pow_min_difficulty

    challenge_nonce: str = ""
    challenge_hash: str = ""


class Allocate(bt.Synapse):
    """
    A simple Allocate protocol representation which uses bt.Synapse as its base.
    This protocol helps in handling Allocate request and response communication between
    the miner and the validator.

    Attributes:
    - timeline: The living time of this allocation.
    - requirement: Detailed information of requirements.
    - checking: Flag that indicates whether it is checking or allocating
    - public_key: Public key for encryption of data.
    - output: Respond of miner.
    """

    timeline: int = 0
    requirement: dict = {}
    checking: bool = True
    output: dict = {}
    public_key: str = ""

    def deserialize(self) -> dict:
        """
        Deserialize the output. This method retrieves the response from
        the miner in the form of output, deserializes it and returns it
        as the output of the dendrite.query() call.

        Returns:
        - dict: The deserialized response, which in this case is the value of output.

        Example:
        Assuming a Allocate instance has a output value of {}:
        >>> allocate_instance = Allocate()
        >>> allocate_instance.output = {}
        >>> allocate_instance.deserialize()
        {}
        """
        return self.output


class DeviceInfo(bt.Synapse):
    """
    A simple device information protocol representation which uses bt.Synapse as its base.
    This protocol helps in handling device information request and response communication between
    the miner and the validator.

    Attributes:
    - device_info_input: The byte data of application that will be sent.
    - device_info_output: A dictionary with the detailed information of cpu, gpu, hard disk and ram.
    """

    device_info_input: str = ""

    device_info_output: str = ""
    """
    Request output, filled by receiving axon.
    Example: {"CPU":{'count' : 4, 'vendor_id_raw' : 'AuthenticAMD', ...}}
    """

    def deserialize(self) -> str:
        """
        Deserialize the device information output. This method retrieves the response from
        the miner in the form of device_info_output, deserializes it and returns it
        as the output of the dendrite.query() call.

        Returns:
        - str: The deserialized response, which in this case is the value of device_info_output.

        Example:
        Assuming a Performance instance has a device_info_output value of {}:
        >>> device_info_instance = DeviceInfo()
        >>> device_info_instance.device_info_output = ''
        >>> device_info_instance.deserialize()
        ''
        """
        return self.device_info_output
