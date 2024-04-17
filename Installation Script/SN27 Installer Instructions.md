# Bittensor/Compute Subnet Installer Script
This repository contains an installation script for setting up a Bittensor miner with the necessary dependencies and configurations for SN27 (Subnet 27) of the Bittensor network.

## Features

- Installs Bittensor and its dependencies
- Installs Docker for containerization
- Installs NVIDIA docker support for optimized GPU functionality
- Installs Subtensor and Starts a Lite Node on Mainnet
- Installs PM2 for process management
- Clones and installs the Compute-Subnet repository and its dependencies
- Starts the Docker service within Compute Subnet
- Installs Hashcat for computational tasks
- Installs NVIDIA drivers and CUDA toolkit for GPU functionality
- Installs UFW and configures ports for miners
- Provides a convenient one-line command for easy installation

## Usage

To install Bittensor with SN27 dependencies, simply run the following command in your terminal:

/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/cisterciansis/Bittensor-Compute-Subnet-Installer-Script/main/install_sn27.sh)"

The script will guide you through the installation process and set up the necessary components for running a Bittensor miner on SN27.

Please note that this script is designed for Linux systems with the apt package manager. If you're using a different Linux distribution or package manager, you may need to modify the script accordingly.

## Disclaimer

This script is provided as-is and without warranty. Use it at your own risk. Make sure to review the script and understand its actions before running it on your system.

## Contributions

Contributions to improve the script or add support for other platforms are welcome! Please feel free to open issues or submit pull requests.

## License

This script is released under the [MIT License](https://opensource.org/licenses/MIT).
