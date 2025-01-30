# Bittensor and Compute-Subnet Setup Guide

## Overview
This guide provides comprehensive instructions for setting up Bittensor and Compute-Subnet on a Linux system. Follow these steps to prepare your machine for mining and earning rewards.

## Prerequisites

### Required Items
- **Weights & Biases (WANDB) API Key**
  - Generate from WANDB Account Settings
  - Required for logging mining statistics
  
- **Bittensor Wallets**
  - Coldkey and Hotkey required
  - Must be registered on Bittensor network
  - Can be created using `btcli new_coldkey` and `btcli new_hotkey`
  
- **GPU Drivers**
  - Ubuntu 22.04: Automatic NVIDIA driver installation
  - Other distributions: Manual CUDA driver installation required
  - Verify installation with `nvidia-smi` and `nvcc --version`

## CUDA Installation
Visit NVIDIA's official CUDA download page to get the latest version:
https://developer.nvidia.com/cuda-downloads

For Ubuntu 22.04 (update version numbers as needed):

1. Download CUDA repository package:
```bash
wget https://developer.download.nvidia.com/compute/cuda/12.3.1/local_installers/cuda-repo-ubuntu2204-12-3-local_12.3.1-545.23.08-1_amd64.deb
```

2. Install repository package:
```bash
sudo dpkg -i cuda-repo-ubuntu2204-12-3-local_12.3.1-545.23.08-1_amd64.deb
```

3. Copy keyring:
```bash
sudo cp /var/cuda-repo-ubuntu2204-12-3-local/cuda-*-keyring.gpg /usr/share/keyrings/
```

4. Update and install CUDA:
```bash
sudo apt-get update
sudo apt-get -y install cuda-toolkit-12-3
sudo apt-get -y install -y cuda-drivers
```

5. Set up environment variables:
```bash
export CUDA_VERSION=cuda-12.3
export PATH=$PATH:/usr/local/$CUDA_VERSION/bin
export LD_LIBRARY_PATH=/usr/local/$CUDA_VERSION/lib64
```

6. Add to bashrc:
```bash
echo "">>~/.bashrc
echo "PATH=$PATH">>~/.bashrc
echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH">>~/.bashrc
source ~/.bashrc
```

7. Reboot system:
```bash
sudo reboot
```

### Verify CUDA Installation
Run `nvidia-smi`. Expected output should look like:
```
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 545.29.06              Driver Version: 545.29.06    CUDA Version: 12.3     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|                                         |                      |               MIG M. |
|=========================================+======================+======================|
|   0  NVIDIA RTX                     Off | 00000000:05:00.0 Off |                  Off |
| 30%   34C    P0              70W / 300W |  400MiB / 4914000MiB |      4%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
```

Run `nvcc --version`. Expected output:
```
nvcc: NVIDIA (R) Cuda compiler driver
Copyright (c) 2005-2023 NVIDIA Corporation
Built on Fri_Nov__3_17:16:49_PDT_2023
Cuda compilation tools, release 12.3, V12.3.103
Build cuda_12.3.r12.3/compiler.33492891_0
```

## Bittensor Installation

### Step 1: Download and Prepare Installer
```bash
curl -sL https://raw.githubusercontent.com/neuralinternet/compute-subnet/main/scripts/installer/install_sn27.sh
 -o SN27_installer.sh
chmod +x SN27_installer.sh
```

### Step 2: Run Installation Script
```bash
./SN27_installer.sh
```

The installer will:
- Set up Docker with NVIDIA support
- Configure PM2 and NodeJS
- Create Python 3.10 virtual environment
- Clone and set up Compute-Subnet repository
- Install Bittensor dependencies

## Post-Installation Verification

### Reboot your machine
```bash
sudo reboot
```

### Enter Virtual Environment
```bash
source /home/ubuntu/venv/bin/activate
```

### Docker Verification
```bash
docker --version
```

### Bittensor CLI Verification
```bash
btcli --version
```

### Directory Check
```bash
cd /home/ubuntu/Compute-Subnet
ls
```

## Running a Miner

### Basic Miner Command
```bash
cd /home/ubuntu/Compute-Subnet
pm2 start ./neurons/miner.py --name MINER --interpreter python3 -- \
  --netuid 15 \
  --subtensor.network test \
  --wallet.name default \
  --wallet.hotkey default \
  --axon.port 8091 \
  --logging.debug \
  --miner.blacklist.force_validator_permit \
  --auto_update yes
```

## Troubleshooting

### Common Issues and Solutions
1. **Missing WANDB Key**
   - Edit `/home/ubuntu/Compute-Subnet/.env`
   - Add your WANDB API key

2. **Unregistered Wallet**
   - Register your coldkey on Bittensor network first
   - Use `btcli register` command

3. **Docker Permissions**
   ```bash
   sudo usermod -aG docker $USER
   ```
   Requires system relogin

4. **Driver Issues**
   - Manual installation required for non-Ubuntu 22.04 systems
   - Verify with `nvidia-smi`
   - Follow CUDA installation steps above if needed

## Additional Resources
- [Weights & Biases Documentation](https://docs.wandb.ai/)
- [Bittensor Documentation](https://docs.bittensor.com/)
- [Compute-Subnet Documentation](https://docs.neuralinternet.ai)
- [NVIDIA CUDA Downloads](https://developer.nvidia.com/cuda-downloads)