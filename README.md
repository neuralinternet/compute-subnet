# Compute Subnet

[![Discord Chat](https://img.shields.io/discord/308323056592486420.svg)](https://discord.gg/bittensor)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

### The Incentivized Internet

[Discord](https://discord.gg/bittensor) • [Network](https://taostats.io/) • [Research](https://bittensor.com/whitepaper)

This repository contains all the necessary files and functions to define Bittensor's Compute Subnet. It enables running miners on netuid 15 in Bittensor's test network or netuid 27 in Bittensor's main network.

## Introduction

This repository serves as a compute-composable subnet, integrating various cloud platforms (e.g., Runpod, Lambda, AWS) into a cohesive unit. Its purpose is to enable higher-level cloud platforms to offer seamless compute composability across different underlying platforms. With the proliferation of cloud platforms, there's a growing need for a subnet that can seamlessly integrate these platforms, allowing efficient resource sharing and allocation. This compute-composable subnet empowers nodes to contribute computational power, with validators ensuring the integrity and efficiency of the shared resources.

### File Structure

- `compute/protocol.py`: Defines the wire-protocol used by miners and validators.
- `neurons/miner.py`: Defines the miner's behavior in responding to requests from validators.
- `neurons/validator.py`: Defines the validator's behavior in requesting information from miners and determining scores.

## Installation

This repository requires python3.8 or higher. To install, simply clone this repository and install the requirements.

### Bittensor

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/opentensor/bittensor/master/scripts/install.sh)"
```

## Dependencies - Validators / Miners

```bash
git clone https://github.com/neuralinternet/Compute-Subnet.git
cd Compute-Subnet
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
```

## Extra dependencies - Miners

### Hashcat

```bash
# Minimal hashcat version >= v6.2.6
wget https://hashcat.net/files/hashcat-6.2.6.tar.gz
tar xzvf hashcat-6.2.6.tar.gz
cd hashcat-6.2.6/
make
make install  # prefixed by sudo if not in the sudoers
hashcat --version
```

### Cuda

```bash
# Recommended cuda version: 12.3
wget https://developer.download.nvidia.com/compute/cuda/12.3.1/local_installers/cuda-repo-ubuntu2204-12-3-local_12.3.1-545.23.08-1_amd64.deb
dpkg -i cuda-repo-ubuntu2204-12-3-local_12.3.1-545.23.08-1_amd64.deb
cp /var/cuda-repo-ubuntu2204-12-3-local/cuda-*-keyring.gpg /usr/share/keyrings/
apt-get update
apt-get -y install cuda-toolkit-12-3
apt-get -y install -y cuda-drivers

# Valid for x64 architecture. Consult nvidia documentation for any other architecture.
export CUDA_VERSION=cuda-12.3
export PATH=$PATH:/usr/local/$CUDA_VERSION/bin
export LD_LIBRARY_PATH=/usr/local/$CUDA_VERSION/lib64

echo "">>~/.bashrc
echo "PATH=$PATH">>~/.bashrc
echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH">>~/.bashrc

reboot  # Changes might need a restart depending on the system

nvidia-smi
nvcc --version

# Version should match
```

### Docker

To run a miner, you must [install](https://docs.docker.com/engine/install/ubuntu) and start the docker service.

```bash
sudo apt install docker.io -y
sudo apt install docker-compose -y
sudo systemctl start docker
sudo apt install at
docker run hello-world  # Must not return you any error.
```

### Running subtensor locally

```bash
git clone https://github.com/opentensor/subtensor.git
cd subtensor
docker-compose up --detach
```

If you have more complicated needs, see the [subtensor](https://github.com/opentensor/subtensor/) repo for more details and understanding.


---

# Running a Miner / Validator

Prior to running a miner or validator, you must [create a wallet](https://github.com/opentensor/docs/blob/main/reference/btcli.md)
and [register the wallet to a netuid](https://github.com/opentensor/docs/blob/main/subnetworks/registration.md). 
Once you have done so, you can run the miner and validator with the following commands.

## Running Miner

A dedicated medium article is available [here](https://medium.com/@neuralinternet/how-to-run-a-compute-miner-82498b93e7e1)

Miners contribute processing resources, notably GPU (Graphics Processing Unit) and CPU (Central Processing Unit)
instances, to facilitate optimal performance in essential GPU and CPU-based computing tasks. The system operates on a
performance-based reward mechanism, where miners are incentivized through a tiered reward structure correlated to the
processing capability of their hardware. High-performance devices are eligible for increased compensation, reflecting
their greater contribution to the network's computational throughput. Emphasizing the integration of GPU instances is
critical due to their superior computational power, particularly in tasks demanding parallel processing capabilities.
Consequently, miners utilizing GPU instances are positioned to receive substantially higher rewards compared to their
CPU counterparts, in alignment with the greater processing power and efficiency GPUs bring to the network.

A key aspect of the miners' contribution is the management of resource reservations. Miners have the autonomy to set
specific timelines for each reservation of their computational resources. This timeline dictates the duration for which
the resources are allocated to a particular task or user. Once the set timeline reaches its conclusion, the reservation
automatically expires, thereby freeing up the resources for subsequent allocations. This mechanism ensures a dynamic and
efficient distribution of computational power, catering to varying demands within the network.

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

Validators hold the critical responsibility of rigorously assessing and verifying the computational capabilities of
miners. This multifaceted evaluation process commences with validators requesting miners to provide comprehensive
performance data, which includes not only processing speeds and efficiencies but also critical metrics like Random
Access Memory (RAM) capacity and disk space availability.

The inclusion of RAM and disk space measurements is vital, as these components significantly impact the overall
performance and reliability of the miners' hardware. RAM capacity influences the ability to handle large or multiple
tasks simultaneously, while adequate disk space ensures sufficient storage.

Following the receipt of this detailed hardware and performance information, validators proceed to test the miners'
computational integrity. This is achieved by presenting them with complex hashing challenges, designed to evaluate the
processing power and reliability of the miners' systems. Validators adjust the difficulty of these problems based on the
comprehensive performance profile of each miner, including their RAM and disk space metrics.

In addition to measuring the time taken by miners to resolve these problems, validators meticulously verify the accuracy
of the responses. This thorough examination of both speed and precision, complemented by the assessment of RAM and disk
space utilization, forms the crux of the evaluation process.

Based on this extensive analysis, validators update the miners' scores, reflecting a holistic view of their
computational capacity, efficiency, and hardware quality. This score then determines the miner's weight within the
network, directly influencing their potential rewards and standing.
This scoring process, implemented through a Python script, considers various factors including CPU, GPU, hard disk, and
RAM performance. The script's structure and logic are outlined below:

## Understanding the Score Calculation Process

**The scoring system has been updated, if you want to check the old hardware mechanism:** [Hardware scoring](docs/hardware_scoring.md)

The score calculation function determines a miner's performance based on various factors:

**Successful Problem Resolution**: It first checks if the problem was solved successfully. If not, the score remains at zero.

**Problem Difficulty**: This measures the complexity of the solved task. The code restricts this difficulty to a maximum allowed value.

**Weighting Difficulty and Elapsed Time**: The function assigns a weight to both the difficulty of the solved problem (75%) and the time taken to solve it (25%).

**Exponential Rewards for Difficulty**: Higher problem difficulty leads to more significant rewards. An exponential formula is applied to increase rewards based on difficulty.

**Allocation Bonus**: Miners that have allocated machine receive an additional bonus added to their final score.

**Effect of Elapsed Time**: The time taken to solve the problem impacts the score. A shorter time results in a higher score.

- Max Score = 1e5
- Score = Lowest Difficulty + (Difficulty Weight * Problem Difficulty) + (Elapsed Time * 1 / (1 + Elapsed Time) * 10000) + Allocation Bonus
- Normalized Score = (Score / Max Score) * 100

### Example 1: Miner A's Hardware Scores and Weighted Total

- **Successful Problem Resolution**: True
- **Elapsed Time**: 4 seconds
- **Problem Difficulty**: 6
- **Allocation**: True

Score = 8.2865

### Example 2: Miner B's Hardware Scores and Weighted Total

- **Successful Problem Resolution**: True
- **Elapsed Time**: 16 seconds
- **Problem Difficulty**: 8
- **Allocation**: True

Score = 24.835058823529412

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

## Resource Allocation Mechanism

The allocation mechanism within subnet 27 is designed to optimize the utilization of computational resources
effectively. Key aspects of this mechanism include:

1. **Resource Requirement Analysis:** The mechanism begins by analyzing the specific resource requirements of each task,
   including CPU, GPU, memory, and storage needs.

2. **Miner Selection:** Based on the analysis, the mechanism selects suitable miners that meet the resource
   requirements. This selection process considers the current availability, performance history, and network weights of
   the miners.

3. **Dynamic Allocation:** The allocation of tasks to miners is dynamic, allowing for real-time adjustments based on
   changing network conditions and miner performance.

4. **Efficiency Optimization:** The mechanism aims to maximize network efficiency by matching the most suitable miners
   to each task, ensuring optimal use of the network's computational power.

5. **Load Balancing:** It also incorporates load balancing strategies to prevent overburdening individual miners,
   thereby maintaining a healthy and sustainable network ecosystem.

Through these functionalities, the allocation mechanism ensures that computational resources are utilized efficiently
and effectively, contributing to the overall robustness and performance of the network.

Validators can send requests to reserve access to resources from miners by specifying the specs manually in the
in `register.py` and running this script: https://github.com/neuralinternet/Compute-Subnet/blob/main/neurons/register.py
for example:
```{'cpu':{'count':1}, 'gpu':{'count':1}, 'hard_disk':{'capacity':10737418240}, 'ram':{'capacity':1073741824}}```

## Options

All the list arguments are now using coma separator.

- `--netuid`: (Optional) The chain subnet uid. Default: 27.
- `--auto_update`: (Optional) Auto update the repository. Default: True.
- `--blacklist.exploiters`: (Optional) Automatically use the list of internal exploiters hotkeys. Default: True.
- `--blacklist.hotkeys <hotkey_0,hotkey_1,...>`: (Optional) List of hotkeys to blacklist. Default: [].
- `--blacklist.coldkeys <coldkey_0,coldkey_1,...>`: (Optional) List of coldkeys to blacklist. Default: [].
- `--whitelist.hotkeys <hotkey_0,hotkey_1,...>`: (Optional) List of hotkeys to whitelist. Default: [].
- `--whitelist.coldkeys <coldkey_0,coldkey_1,...>`: (Optional) List of coldkeys to whitelist. Default: [].

## Validators options

---
Flags that you can use with the validator script.

- `--validator.whitelist.unrecognized`: (Optional) Whitelist the unrecognized miners. Default: False.
- `--validator.perform.hardware.query <bool>`: (Optional) Perform the specs query - useful to register to a miner's machine. Default: True.
- `--validator.challenge.batch.size <size>`: (Optional) Batch size that perform the challenge queries - For lower hardware specifications you might want to use a different batch_size than default. Keep in mind the lower is the batch_size the longer it will take to perform all challenge queries. Default: 256.
- `--validator.specs.batch.size <size>`: (Optional) Batch size that perform the specs queries - For lower hardware specifications you might want to use a different batch_size than default. Keep in mind the lower is the batch_size the longer it will take to perform all challenge queries. Default: 64.
- `--validator.force.update.prometheus`: (Optional) Force the try-update of prometheus version. Default: False.
- `--validator.whitelist.updated.threshold`: (Optional) Total quorum before starting the whitelist. Default: 60. (%)

## Miners options

---

- `--miner.hashcat.path <path>`: (Optional) The path of the hashcat binary. Default: hashcat.
- `--miner.hashcat.workload.profile <profile>`: (Optional) Performance to apply with hashcat profile: 1 Low, 2 Economic, 3 High, 4 Insane. Run `hashcat -h` for more information. Default: 3.
- `--miner.hashcat.extended.options <options>`: (Optional) Any extra options you found usefull to append to the hascat runner (I'd perhaps recommend -O). Run `hashcat -h` for more information. Default: ''.
- `--miner.whitelist.not.enough.stake`: (Optional) Whitelist the validators without enough stake. Default: False.
- `--miner.whitelist.not.updated`: (Optional) Whitelist validators not using the last version of the code. Default: False.
- `--miner.whitelist.updated.threshold`: (Optional) Total quorum before starting the whitelist. Default: 60. (%)

## Benchmarking the machine

```bash
hashcat -b -m 610
```

Output
```
Speed.#1.........: 12576.1 MH/s (75.69ms) @ Accel:8 Loops:1024 Thr:1024 Vec:1
Speed.#2.........: 12576.1 MH/s (75.69ms) @ Accel:8 Loops:1024 Thr:1024 Vec:1
...
...
```

Recommended minimum hashrate for the current difficulty: >= 3000 MH/s.

Difficulty will increase over time.

## Troubleshooting

> "I don't receive any request, 'Challenge' or 'Specs', what could be the reason ?"

Most probably you are running into a **network issue**. 
- check your ports 
- check your firewall

> "I have been deregistered, why ?"

There might be a thousand reason for this. Ensure your script is running correctly.
Otherwise, the simplest answer is the following: **competition is really hard over the network**.
Maybe people are running stronger devices than you, maybe you had internet issues, maybe you did not isolate your environment and another script that you ran broke it, etc.


## Action todo for updates

__**No action required when using auto-update flag**__.

```sh
git pull
python -m pip install -r requirements.txt
python -m pip install -e .
pm2 restart <id>
```

Exception for 1.3.10:
```sh
git pull
python -m pip install --force-reinstall --ignore-installed --no-deps -r requirements.txt
python -m pip install --force-reinstall --ignore-installed --no-deps -e .
pm2 restart <id>
```

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
