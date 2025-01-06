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

This repository requires python3.8 or higher. To install, simply clone this repository and install the requirements. You are limited to one external IP per UID. There is automatic blacklisting in place if validators detect anomalous behavior. 

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

### Cuda

To ensure **optimal performance and compatibility**, it is **strongly recommended** to install the **latest available CUDA version** from NVIDIA.

```bash
# Visit NVIDIA's official CUDA download page to get the latest version:
# https://developer.nvidia.com/cuda-downloads

# Select your operating system, architecture, distribution, and version to get the appropriate installer.

# Example for Ubuntu 22.04 (replace with the latest version as needed):

# Download the CUDA repository package (update the URL to the latest version)
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-repo-ubuntu2204-latest_amd64.deb

# Install the CUDA repository package
sudo dpkg -i cuda-repo-ubuntu2204-latest_amd64.deb

# Import the GPG key
sudo cp /var/cuda-repo-ubuntu2204-latest/cuda-*-keyring.gpg /usr/share/keyrings/

# Update the package lists
sudo apt-get update

# Install CUDA Toolkit and drivers
sudo apt-get -y install cuda-toolkit
sudo apt-get -y install cuda-drivers

# Set environment variables
export CUDA_PATH=/usr/local/cuda
export PATH=$PATH:$CUDA_PATH/bin
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CUDA_PATH/lib64

# Persist environment variables by adding them to ~/.bashrc
echo "export CUDA_PATH=/usr/local/cuda" >> ~/.bashrc
echo "export PATH=\$PATH:\$CUDA_PATH/bin" >> ~/.bashrc
echo "export LD_LIBRARY_PATH=\$LD_LIBRARY_PATH:\$CUDA_PATH/lib64" >> ~/.bashrc

# Apply the changes
source ~/.bashrc

# Reboot the system to finalize the installation
sudo reboot

# Verify the installation
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

To run a docker container for allocation, user must be added to docker group to run without sudo command.

```bash
sudo groupadd docker
sudo usermod -aG docker $USER
sudo systemctl restart docker
```

### Nvidia toolkit

To run a container for allocation, nvidia toolkit for docker needs to be installed.

```bash
sudo apt-get install -y nvidia-container-toolkit
sudo apt install -y nvidia-docker2
```

### WanDB

To log into the wandb project named opencompute from neuralinternet, miners and validators need a wandb API key.
Rename the `.env.example` file to `.env` and replace the placeholder with your actual API key.

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

Miners contribute processing resources, specifically GPU (Graphics Processing Unit) to enable optimal performance in essential GPU-based computing tasks. The system uses a hardware specification-based reward mechanism that incentivizes miners through a tiered structure, with rewards directly correlated to the processing capabilities of their hardware. High-performance devices receive greater compensation, reflecting their significant contributions to the network's overall computational throughput. Detailed scoring metrics and supported GPUs can be found in the config.yaml file under the gpu_scores section. A comprehensive explanation of scoring is provided below in the section titled "Understanding the Score Calculation Process".

The primary role of miners is to provide their resources to validators. The allocation and management of these resources are entirely handled on the validator's side. Validators dynamically allocate and deallocate a miner's resources based on availability and network demand. This ensures an efficient and flexible distribution of computational power, meeting the fluctuating needs of the network.

It is important to ensure that port 4444 is open on the host machine or that an alternative open port is specified. This allows validators to access the miner's allocated resources and retrieve GPU specifications seamlessly. Changing the miner's hardware while it is allocated is possible, but it will result in the validator deallocating your miner

```bash
# To run the miner
cd neurons
python -m miner.py 
    --netuid <your netuid>  # The subnet id you want to connect to
    --subtensor.network <your chain url>  # blockchain endpoint you want to connect
    --wallet.name <your miner wallet> # name of your wallet
    --wallet.hotkey <your miner hotkey> # hotkey name of your wallet
    --ssh.port <your ssh port> # The port you want to provide for allocations, default: 4444
    --logging.debug # Run in debug mode, alternatively --logging.trace for trace mode
```

## Running Validator

Validators play a crucial role in meticulously evaluating and verifying the computational capabilities of miners. This thorough assessment begins with validators requesting detailed performance data from miners, encompassing hardware specifications, efficiencies, and critical metrics such as Random Access Memory (RAM) capacity and disk space availability.

The inclusion of RAM and disk space metrics is essential, as these components significantly influence the overall performance and reliability of a miner's hardware. RAM capacity determines the ability to manage large or multiple tasks simultaneously, while sufficient disk space ensures adequate storage for sustained operations.

Once this comprehensive hardware and performance information is received, validators test the computational integrity of miners using torch-based computational tasks, such as matrix multiplications. These tests are designed to accurately determine the hardware specifications and performance capabilities of the miners' systems.

Based on the results of this hardware identification process, validators update the miners' scores. These scores determine the miners' weight within the network, directly affecting their potential rewards and standing in the system.

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

## Understanding the Score Calculation Process

**The scoring system has been updated!**

The score calculation function now determines a miner's performance primarily based on their GPU hardware and resource allocation. Only the GPUs listed below are supported and scored correctly.

**GPU Base Scores**: The following GPUs are assigned specific base scores, reflecting their relative performance:
- NVIDIA H200: 4.00
- NVIDIA H100 80GB HBM3: 3.30
- NVIDIA H100: 2.80
- NVIDIA A100-SXM4-80GB: 1.90
- NVIDIA A100 80GB PCIe: 1.65
- NVIDIA L40s: 1.10
- NVIDIA L40: 1.00
- NVIDIA RTX 6000 Ada Generation: 0.90
- NVIDIA RTX A6000: 0.78
- NVIDIA RTX 4090: 0.68
- NVIDIA GeForce RTX 3090: 0.43
- NVIDIA L4: 0.43
- NVIDIA A40: 0.39
- NVIDIA RTX A5000: 0.36
- NVIDIA RTX A4500: 0.34

**Scaling Factor**: Determine the highest GPU base score, multiply it by 8 (the maximum number of GPUs), and set this scenario as the 100-point baseline. A scaling factor is derived so that using eight of the top GPU models equals 50 points.

**GPU Score**: Multiply the chosen GPU’s base score by the number of GPUs (up to 8) and by the scaling factor to find the miner’s GPU score (0–50).

**Allocation Bonus**: If a miner has allocated machine resources, the GPU score is multiplied by 2, allowing a maximum score of up to 100.

**Total Score**:

- Score (not allocated) = GPU Score (0–50)
- Score (allocated) = GPU Score * 2 (up to 100)

### Example 1: Miner A's Total Score

- **GPU**: NVIDIA H200 (Base Score: 3.90)
- **Number of GPUs**: 8
- **Allocation**: False

Step-by-step calculation:
1. Highest scenario: 4 * 8 = 32
2. Scaling factor: 50 / 32 ≈ 1.5625
3. GPU Score: 4 * 8 * 1.5625 ≈ 50
4. Allocation Bonus: 0

Total Score = 50

### Example 2: Miner B's Total Score

- **GPU**: NVIDIA RTX 4090 (Base Score: 0.69)
- **Number of GPUs**: 2
- **Allocation**: True

Step-by-step calculation:
1. Scaling factor (same as above): 1.5625
2. GPU Score: 0.68 * 2 * 1.5625 ≈ 2.125
3. Allocation Bonus: 2.125 * 2 = 4.25

Total Score = 4.25

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
- `--validator.specs.batch.size <size>`: (Optional) Batch size that perform the specs queries - For lower hardware specifications you might want to use a different batch_size than default. Keep in mind the lower is the batch_size the longer it will take to perform all challenge queries. Default: 64.
- `--validator.force.update.prometheus`: (Optional) Force the try-update of prometheus version. Default: False.
- `--validator.whitelist.updated.threshold`: (Optional) Total quorum before starting the whitelist. Default: 60. (%)

## Miners options

---

- `--miner.whitelist.not.enough.stake`: (Optional) Whitelist the validators without enough stake. Default: False.
- `--miner.whitelist.not.updated`: (Optional) Whitelist validators not using the last version of the code. Default: False.
- `--miner.whitelist.updated.threshold`: (Optional) Total quorum before starting the whitelist. Default: 60. (%)

## Benchmarking the machine

**Note**: Starting from v1.6.0, hashcat benchmarking is no longer performed. The information below is provided purely as legacy reference and will be updated in future releases.

### Benchmarking hashcat's performance directly:
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

### Benchmarking the system using challenge emulations:
```bash
cd compute-subnet
python3 ./test-scripts/benchmark.py
```

> "What challenge difficulties would you like to benchmark?"

Any positive integer or list of positive integers ranging from the minimum challenge difficulty (6) to the maximum challenge difficulty (12) can be entered. An invalid entry will default to the minimum or maximum challenge difficulty based on whichever is closer. Entering ```all``` will add 1 challenge of each available difficulty to the benchmark list.

Example challenge difficulty selections:
```bash
Example 1: 6
Example 2: 7 8 9
Example 3: 10, 11, 12
Example 4: all
```
> "How many benchmarks would you like to perform?"

Any positive integer > 0, ```n```, can be used. This will benchmark each entered difficulty ```n``` times.\
Example:
```bash
Difficulties = [6, 7, 8]
Benchmarks to perform = 2
Benchmarks performed: [6, 6, 7, 7, 8, 8]
```

> "What hashcat workload profile (1, 2, 3, or 4) would you like to use?"

A workload profile from 1 to 4 can be used. An invalid or empty entry will default to workload profile 3.

> "Enter any extra hashcat options to use. Leave this empty to use the recommended -O option. Enter None for no extended options."

Enter any additional options for hashcat to use. It's recommended to use the ```-O``` option by either explicitly stating it or submitting a blank entry, which will use ```-O``` by default. Enter ```None``` to exclude all extra hashcat options. Additional options can be listed with the command ```hashcat -h```.

![alt text](<miner_benchmark_sample.png>)

## Troubleshooting

> "I don't receive any request, 'Challenge' or 'Specs' or 'Allocation', what could be the reason ?"

Starting from v1.6.0, hashcat challenge benchmarking is no longer performed.
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

python -m pip install -e .
python -m pip install --no-deps -r requirements-compute.txt
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
