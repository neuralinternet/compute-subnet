# Bittensor/Compute Subnet Installer Script
This repository contains an installation script for setting up a Bittensor miner with the necessary dependencies and configurations for SN27 (Subnet 27) of the Bittensor network. This installation process requires Ubuntu 22.04. You are limited to one external IP per UID. There is automatic blacklisting in place if validators detect anomalous behavior. 


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

This installation process requires Ubuntu 22.04.

Use a Virtual Environment

When working with Bittensor miners across various Subnets, it's highly recommended to use a virtual environment (venv) to isolate the dependencies and avoid potential conflicts. Each subnet may have different requirements, and using a separate virtual environment ensures that the dependencies are managed independently.

To create and activate a virtual environment, follow these steps:

1. Open a terminal and navigate to the directory where you want to create the virtual environment.

2. Run the following command to create a new virtual environment:
```
python3 -m venv myenv
```

Replace `myenv` with your desired name for the virtual environment.

3. Activate the virtual environment:
- For Linux or macOS:
  ```
  source myenv/bin/activate
  ```
- For Windows:
  ```
  myenv\Scripts\activate
  ```

4. Once the virtual environment is activated, you'll see the name of the environment in your terminal prompt, indicating that you're now working within the isolated environment.

5. Proceed with installing the required dependencies and running the Bittensor miner specific to the Subnet you're working on.

6. To deactivate the virtual environment when you're done, simply run:
```
deactivate
```
Using a virtual environment ensures that the dependencies and requirements are isolated and avoids potential conflicts.

Please remember to activate the appropriate virtual environment when you switch between Subnets or working on a different miner/project.

To install Bittensor with SN27 dependencies, simply run the following command in your terminal:
```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/cisterciansis/Bittensor-Compute-Subnet-Installer-Script/main/install_sn27.sh)"
```
The script will guide you through the installation process and set up the necessary components for running a Bittensor miner on SN27.

Please note that this script is designed for Linux systems with the apt package manager. If you're using a different Linux distribution or package manager, you may need to modify the script accordingly.

## Disclaimer

This script is provided as-is and without warranty. Use it at your own risk. Make sure to review the script and understand its actions before running it on your system.

## Contributions

Contributions to improve the script or add support for other platforms are welcome! Please feel free to open issues or submit pull requests.

## License

This script is released under the [MIT License](https://opensource.org/licenses/MIT).
