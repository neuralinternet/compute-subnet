# Bittensor and Compute-Subnet Setup Guide

## Overview
This guide provides comprehensive instructions for setting up Bittensor and Compute-Subnet on a Linux system for mining operations. The installation process is divided into two separate scripts:

1. `1_cuda_installer.sh`: Installs Docker, NVIDIA drivers, NVIDIA Docker support, the CUDA Toolkit, and Bittensor (via the btcli source installation)
2. `2_compute_subnet_installer.sh`: Sets up the environment and launches the miner

## Prerequisites

### Required Items

#### Weights & Biases (WANDB) API Key
- Generate from your WANDB account settings
- Required for logging mining statistics

#### Bittensor Wallets and TAO
- You must create and fund your wallets before running the second installer
- The script will check for existing wallets in `~/.bittensor/wallets`
- You need TAO (mainnet) or TestTAO (testnet) for registration
- If no wallets are found, the script will abort

#### GPU Drivers and CUDA Toolkit
- The installer scripts automatically install NVIDIA drivers and the CUDA Toolkit (version 12.8) for Ubuntu 22.04 and 24.04
- For other distributions or CUDA versions, manual installation may be required

## Installation Steps

### Clone the Repository

First, clone the Compute-Subnet repository and navigate to the installation scripts directory:

```bash
git clone https://github.com/neuralinternet/compute-subnet.git
cd compute-subnet/scripts/installation_script
```

### Step 1: Run the CUDA and System Installer (1_cuda_installer.sh)

This script installs Docker, NVIDIA drivers, NVIDIA Docker support, the CUDA Toolkit, and btcli from source.

```bash
bash 1_cuda_installer.sh
```

**Note**: The script will prompt for confirmations and may reboot your system to finalize the driver and CUDA setup.

### Step 2: Create and Fund Your Wallets

Before running the second installer, you must create and fund your wallets. You have two options:

#### Option 1: Create New Wallets
```bash
# Create a new coldkey
btcli wallet new_coldkey

# Create a new hotkey
btcli wallet new_hotkey
```

#### Option 2: Import Existing Wallets
```bash
# Import existing coldkey
btcli wallet regen_coldkey --mnemonic "your twelve words mnemonic here"

# Import existing hotkey
btcli wallet regen_hotkey --mnemonic "your twelve words mnemonic here"
```

#### Fund Your Wallet
1. For mainnet:
   - Transfer TAO to your coldkey wallet address
   - You'll need TAO for registration and mining

2. For testnet:
   - Transfer TestTAO to your coldkey wallet address
   - Required for testnet registration

**⚠️ Important:**
- The second installer will verify that wallets exist in `~/.bittensor/wallets`
- If no wallets are found, the installation will abort
- Make sure to create and fund your wallets before proceeding

### Step 3: Run the Compute-Subnet Installer (2_compute_subnet_installer.sh)

After creating and funding your wallets, proceed with the second script:

```bash
bash 2_compute_subnet_installer.sh
```

The script will:
- Verify existing wallets
- Set up the environment
- Configure and launch the miner

## Troubleshooting

### Common Issues and Solutions

#### Missing Wallets
- Ensure you have created your wallets using btcli before running the second installer
- Check that your wallets exist in `~/.bittensor/wallets`
- Verify your wallet has sufficient TAO/TestTAO

#### Missing WANDB API Key
- Edit the file `/home/ubuntu/compute-subnet/.env` to add your WANDB API key

#### Docker Permissions
If you encounter Docker permission issues:
```bash
sudo usermod -aG docker $USER
```
You might need to re-login or reboot after modifying group membership.

## Additional Resources
- [Weights & Biases Documentation](https://docs.wandb.ai/)
- [Bittensor Documentation](https://docs.bittensor.com/)
- [Compute-Subnet Documentation](https://github.com/neuralinternet/compute-subnet)
