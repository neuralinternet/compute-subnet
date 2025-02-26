# Bittensor & NI Compute Setup Guide (Two-Pass Installer)

This guide explains how to install all necessary components (Docker, CUDA, NVIDIA Docker, Bittensor) and then set up the Compute-Subnet miner. You will run the unified installer script in two passes:

1. **First Pass**: Installs system dependencies (Docker, NVIDIA drivers, CUDA, Bittensor).
2. **Wallet Creation / Funding**: A manual step where you create/import and fund your wallet.
3. **Second Pass**: Re-run the installer to configure and launch the miner, now that the wallet exists.

By splitting things up, you can reboot if needed after installing drivers, and ensure your wallet is funded before finalizing the miner setup.

## Prerequisites

- Ubuntu 22.04 or 24.04 (other distros may require manual steps).
- NVIDIA GPU (the script installs drivers and CUDA 12.8).
- WANDB Account (optional, recommended).
- Sudo/Root access on your machine.

## Step 1: Get the Unified Installer Script

### Option 1: Clone the Repository

```bash
git clone https://github.com/neuralinternet/compute-subnet.git
cd compute-subnet/scripts/installation_script
```

You will find the installer script named `compute_subnet_installer.sh` in the `scripts/installation_script/` folder. Make it executable:

```bash
chmod +x compute_subnet_installer.sh
```

### Option 2: Download via curl

If you prefer, you can fetch the script directly:

```bash
curl -sL \
  https://raw.githubusercontent.com/neuralinternet/compute-subnet/main/scripts/installation_script/compute_subnet_installer.sh \
  -o compute_subnet_installer.sh

chmod +x compute_subnet_installer.sh
```

## Step 2: First-Pass Installation

Run the script to install Docker, NVIDIA drivers, CUDA, and Bittensor. Choose automated or interactive:

```bash
# Automated (skips confirmations)
./compute_subnet_installer.sh --automated

# Or Interactive (step-by-step questions)
./compute_subnet_installer.sh
```

During this first pass:

- The script checks for Docker, CUDA, Bittensor; installs them if missing.
- If you install new GPU drivers, it may prompt you to reboot afterward.
- It looks for your wallet. If none exists, it will likely skip final miner setup.

## Step 3: Create & Fund Your Bittensor Wallet

The script does not automatically create or import your wallet. You must do one of the following:

### 3.1 Create a New Wallet

```bash
# Create a new coldkey
btcli w new_coldkey

# Create a new hotkey
btcli w new_hotkey
```

### 3.2 Import an Existing Wallet

```bash
# Import coldkey from mnemonic
btcli w regen_coldkey --mnemonic "twelve words..."
--wallet.name mycold

# Import hotkey from mnemonic
btcli w regen_hotkey --mnemonic "twelve words..."
```

### 3.3 Fund the Wallet

- **Mainnet**: Send TAO to your coldkey address.
- **Testnet**: Send TestTAO from other source to your coldkey.

You must have enough TAO/TestTAO to register and mine.

## Step 4: Second-Pass Installation (Miner Setup)

Once your wallet is created and funded, re-run the script:

```bash
./compute_subnet_installer.sh --automated
```
(or without `--automated` for interactive prompts).

Now, the script detects a funded wallet in `~/.bittensor/wallets` and proceeds:

- Compute-Subnet dependencies installation (Python, PM2, etc.).
- UFW firewall configuration (opens ports 22, 4444, and Axon port, typically 8091).
- Optionally asks for a WANDB key (used for logging).
- Creates a PM2 config for the miner and launches it in the background.

At the end, you have a running miner process, assuming your wallet is registered and funded.

## Verification

Check PM2:

```bash
pm2 list
pm2 logs subnetXX_miner
```
(XX depends on the netuid you selected.)

Register Hotkey (if you haven't yet):

```bash
btcli register --wallet.name mycold --wallet.hotkey myhot
```

This requires sufficient TAO in the coldkey.

## Troubleshooting

### Docker Permissions

```bash
sudo usermod -aG docker $USER
```

Then re-login or reboot to apply group changes.

### Wallet Not Found

- Check if `~/.bittensor/wallets/<coldkey>/hotkeys/<hotkey>` exists.
- Ensure you used the correct wallet/hotkey names.

### WANDB Key

- If you skip it, you can later edit `~/.env` in the compute-subnet repo folder to add `WANDB_API_KEY="..."`.

### CUDA/Driver Issues

- A reboot often fixes driver initialization problems.

## Summary

1. **First Pass**: Installs Docker, NVIDIA drivers, CUDA, Bittensor.
2. **Wallet Creation**: Manually create/import and fund your wallet.
3. **Second Pass**: Sets up the Compute-Subnet miner (PM2, firewall, WANDB, etc.).

Using this approach, you ensure that all dependencies are in place and that you have a funded wallet before the miner is configured.

## Additional Resources

- [Weights & Biases Documentation](https://docs.wandb.ai/)
- [Bittensor Documentation](https://docs.bittensor.com/)
- [Compute-Subnet Repository](https://github.com/neuralinternet/compute-subnet)
