
<div align="center">

# **Bittensor Compute Subnet** <!-- omit in toc -->
[![Discord Chat](https://img.shields.io/discord/308323056592486420.svg)](https://discord.gg/bittensor)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) 

---

### The Incentivized Internet <!-- omit in toc -->

[Discord](https://discord.gg/bittensor) • [Network](https://taostats.io/) • [Research](https://bittensor.com/whitepaper)

</div>

---

This repo contains all the necessary files and functions to define Bittensor's Compute Subnet. You can try running miners on netuid 15 in Bittensor's test network.

# Introduction
This repository is a compute-composable subnet. This subnet has integrated various cloud platforms (e.g., Runpod, Lambda, AWS) into a cohesive unit, enabling higher-level cloud platforms to offer seamless compute composability across different underlying platforms. With the proliferation of cloud platforms, there's a need for a subnet that can seamlessly integrate these platforms, allowing for efficient resource sharing and allocation. This compute-composable subnet will enable nodes to contribute computational power, with validators ensuring the integrity and efficiency of the shared resources.

- `compute/protocol.py`: The file where the wire-protocol used by miners and validators is defined.
- `neurons/miner.py`: This script which defines the miner's behavior, i.e., how the miner responds to requests from validators.
- `neurons/validator.py`: This script which defines the validator's behavior, i.e., how the validator requests information from miners and determines scores.

---

# Installation
This repository requires python3.8 or higher. To install, simply clone this repository and install the requirements.

## Install Bittensor
```bash
$ /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/opentensor/bittensor/master/scripts/install.sh)"
```
## Install Dependencies
```bash
git clone https://github.com/neuralinternet/Compute-Subnet.git
cd Compute-Subnet
python -m pip install -r requirements.txt
python -m pip install -e .
```
## Setup Docker for Miner
To run a miner, you must [install](https://docs.docker.com/engine/install/ubuntu) and start the docker service by running `sudo systemctl start docker` and `sudo apt install at`.

</div>

---
# Running a Miner / Validator
Prior to running a miner or validator, you must [create a wallet](https://github.com/opentensor/docs/blob/main/reference/btcli.md) and [register the wallet to a netuid](https://github.com/opentensor/docs/blob/main/subnetworks/registration.md). Once you have done so, you can run the miner and validator with the following commands.

## Running Miner

Miners contribute processing resources, notably GPU (Graphics Processing Unit) and CPU (Central Processing Unit) instances, to facilitate optimal performance in essential GPU and CPU-based computing tasks. The system operates on a performance-based reward mechanism, where miners are incentivized through a tiered reward structure correlated to the processing capability of their hardware. High-performance devices are eligible for increased compensation, reflecting their greater contribution to the network's computational throughput. Emphasizing the integration of GPU instances is critical due to their superior computational power, particularly in tasks demanding parallel processing capabilities. Consequently, miners utilizing GPU instances are positioned to receive substantially higher rewards compared to their CPU counterparts, in alignment with the greater processing power and efficiency GPUs bring to the network.

```bash
# To run the miner
cd neurons
python -m miner.py 
    --netuid <your netuid>  # The subnet id you want to connect to
    --subtensor.network <your chain url>  # blockchain endpoint you want to connect
    --wallet.name <your miner wallet> # name of your wallet
    --wallet.hotkey <your miner hotkey> # hotkey name of your wallet
    --logging.debug # Run in debug mode, alternatively --logging.trace for trace mode
```

## Running Validator

Validators hold the critical responsibility of rigorously assessing and verifying the computational capabilities of miners. This multifaceted evaluation process commences with validators requesting miners to provide comprehensive performance data, which includes not only processing speeds and efficiencies but also critical metrics like Random Access Memory (RAM) capacity and disk space availability.

The inclusion of RAM and disk space measurements is vital, as these components significantly impact the overall performance and reliability of the miners' hardware. RAM capacity influences the ability to handle large or multiple tasks simultaneously, while adequate disk space ensures sufficient storage.

Following the receipt of this detailed hardware and performance information, validators proceed to test the miners' computational integrity. This is achieved by presenting them with complex hashing challenges, designed to evaluate the processing power and reliability of the miners' systems. Validators adjust the difficulty of these problems based on the comprehensive performance profile of each miner, including their RAM and disk space metrics.

In addition to measuring the time taken by miners to resolve these problems, validators meticulously verify the accuracy of the responses. This thorough examination of both speed and precision, complemented by the assessment of RAM and disk space utilization, forms the crux of the evaluation process.

Based on this extensive analysis, validators update the miners' scores, reflecting a holistic view of their computational capacity, efficiency, and hardware quality. This score then determines the miner's weight within the network, directly influencing their potential rewards and standing.

It is important to note that the role of validators, in contrast to miners, does not require the integration of GPU instances. Their function revolves around data integrity and accuracy verification, involving relatively modest network traffic and lower computational demands. As a result, their hardware requirements are less intensive, focusing more on stability and reliability rather than high-performance computation.

```bash
# To run the validator
cd neurons
python -m validator.py 
    --netuid <your netuid> # The subnet id you want to connect to
    --subtensor.network <your chain url> # blockchain endpoint you want to connect
    --wallet.name <your validator wallet>  # name of your wallet
    --wallet.hotkey <your validator hotkey> # hotkey name of your wallet
    --logging.debug # Run in debug mode, alternatively --logging.trace for trace mode
```

</div>

---

## License
This repository is licensed under the MIT License.
```text
# The MIT License (MIT)
# Copyright © 2023 Neural Internet

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
```
