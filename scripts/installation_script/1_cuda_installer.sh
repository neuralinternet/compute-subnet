#!/bin/bash
set -u
set -o history -o histexpand

# 1_cuda_installer.sh - Automated installer for Docker, NVIDIA drivers, NVIDIA Docker support, the CUDA Toolkit, and Bittensor
# Usage: ./1_cuda_installer.sh [--automated]

AUTOMATED=false

if [[ "$#" -gt 0 ]]; then
  if [[ "$1" == "--automated" ]]; then
    AUTOMATED=true
    shift
  fi
fi

abort() {
  echo "Error: $1" >&2
  exit 1
}

ohai() {
  echo "==> $*"
}

wait_for_user() {
  if $AUTOMATED; then
    ohai "Automated mode: skipping user confirmation."
  else
    echo
    echo "Press ENTER to continue or CTRL+C to abort..."
    read -r
  fi
}

if [[ "$(uname)" != "Linux" ]]; then
  abort "This installer only supports Linux."
fi

ohai "WARNING: This script will install Docker, NVIDIA drivers, NVIDIA Docker support, the CUDA Toolkit, and Bittensor (via the official installer), and then reboot."
wait_for_user

HOME=${HOME:-/home/ubuntu}

if [[ -n "${SUDO_USER:-}" ]]; then
  USER_NAME="$SUDO_USER"
  HOME_DIR=$(eval echo "~$SUDO_USER")
else
  if [ "$(whoami)" == "root" ]; then
    # When running as root in cloud-init, force use of the ubuntu user home directory
    USER_NAME="ubuntu"
    HOME_DIR="/home/ubuntu"
  else
    USER_NAME=$(whoami)
    HOME_DIR="$HOME"
  fi
fi

ohai "Updating package lists and installing prerequisites..."
sudo apt-get update || abort "Failed to update package lists."
sudo apt-get install --no-install-recommends --no-install-suggests -y apt-utils curl git cmake build-essential ca-certificates || abort "Failed to install prerequisites."

ohai "Setting up Docker repository..."
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc || abort "Failed to download Docker GPG key."
sudo chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release || abort "Cannot determine OS version."
DOCKER_REPO="deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable"
echo "$DOCKER_REPO" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update || abort "Failed to update package lists after adding Docker repository."
ohai "Installing Docker packages..."
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin || abort "Docker installation failed."

ohai "Adding user ${USER_NAME} to docker group..."
sudo usermod -aG docker "$USER_NAME" || abort "Failed to add user to docker group."

ohai "Installing 'at' package..."
sudo apt-get install -y at || abort "Failed to install 'at'."

ohai "Installing NVIDIA Docker support..."
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/nvidia-docker.gpg > /dev/null || abort "Failed to add NVIDIA Docker GPG key."

UBUNTU_CODENAME=$(lsb_release -cs)
if [[ "$UBUNTU_CODENAME" == "jammy" ]]; then
  NVIDIA_DIST="ubuntu22.04"
else
  NVIDIA_DIST="$UBUNTU_CODENAME"
fi

curl -s -L "https://nvidia.github.io/nvidia-docker/${NVIDIA_DIST}/nvidia-docker.list" | sudo tee /etc/apt/sources.list.d/nvidia-docker.list || abort "Failed to add NVIDIA Docker repository."
sudo apt-get update -y || abort "Failed to update package lists after adding NVIDIA Docker repository."
sudo apt-get install -y nvidia-container-toolkit nvidia-docker2 || abort "Failed to install NVIDIA Docker packages."
ohai "NVIDIA Docker support installed."

# Detect installed CUDA version robustly
SKIP_CUDA_INSTALL=false
INSTALLED_CUDA_VERSION=""

# First try: Check if /usr/local/cuda/version.txt exists
if [ -f "/usr/local/cuda/version.txt" ]; then
  INSTALLED_CUDA_VERSION=$(grep "CUDA Version" /usr/local/cuda/version.txt | awk '{print $3}' | cut -d'.' -f1,2)
fi

# Second try: If not found, check if /usr/local/cuda/version.json exists
if [ -z "$INSTALLED_CUDA_VERSION" ] && [ -f "/usr/local/cuda/version.json" ]; then
  INSTALLED_CUDA_VERSION=$(grep -oP '"cuda"\s*:\s*"\K[0-9]+\.[0-9]+' /usr/local/cuda/version.json)
fi

# Third try: Check if /usr/local/cuda is a symlink pointing to a versioned directory
if [ -z "$INSTALLED_CUDA_VERSION" ] && [ -L "/usr/local/cuda" ]; then
  REAL_CUDA=$(readlink -f /usr/local/cuda)
  if [[ "$REAL_CUDA" =~ cuda-([0-9]+\.[0-9]+) ]]; then
    INSTALLED_CUDA_VERSION="${BASH_REMATCH[1]}"
  fi
fi

# Fallback: if nvcc is available, try using it
if [ -z "$INSTALLED_CUDA_VERSION" ] && command -v nvcc >/dev/null 2>&1; then
  INSTALLED_CUDA_VERSION=$(nvcc --version | grep "release" | sed 's/.*release //' | sed 's/,.*//')
fi

if [ -n "$INSTALLED_CUDA_VERSION" ]; then
  ohai "Detected CUDA version: ${INSTALLED_CUDA_VERSION}"
  if [[ "$INSTALLED_CUDA_VERSION" == "12.8" ]]; then
    ohai "CUDA 12.8 is already installed; skipping CUDA installation."
    SKIP_CUDA_INSTALL=true
  else
    ohai "WARNING: Detected CUDA version ${INSTALLED_CUDA_VERSION} which is different from the required 12.8."
    ohai "Proceeding without installing CUDA 12.8 to avoid overwriting the existing installation."
    SKIP_CUDA_INSTALL=true
  fi
fi

if ! $SKIP_CUDA_INSTALL; then
  if [[ "$VERSION_CODENAME" == "jammy" ]]; then
    ohai "Installing CUDA Toolkit 12.8 for Ubuntu 22.04..."
    sudo apt-get update
    sudo apt-get install -y build-essential dkms linux-headers-$(uname -r) || abort "Failed to install build essentials for CUDA."
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin -O /tmp/cuda.pin || abort "Failed to download CUDA pin."
    sudo mv /tmp/cuda.pin /etc/apt/preferences.d/cuda-repository-pin-600
    wget https://developer.download.nvidia.com/compute/cuda/12.8.0/local_installers/cuda-repo-ubuntu2204-12-8-local_12.8.0-570.86.10-1_amd64.deb -O /tmp/cuda-repo.deb || abort "Failed to download CUDA repository package."
    sudo dpkg -i /tmp/cuda-repo.deb || abort "dpkg failed for CUDA repository package."
    sudo cp /var/cuda-repo-ubuntu2204-12-8-local/cuda-*-keyring.gpg /usr/share/keyrings/ || abort "Failed to copy CUDA keyring."
    sudo apt-get update
    sudo apt-get -y install cuda-toolkit-12-8 cuda-drivers || abort "Failed to install CUDA Toolkit or drivers."
  elif [[ "$VERSION_CODENAME" == "lunar" ]]; then
    ohai "Installing CUDA Toolkit 12.8 for Ubuntu 24.04..."
    sudo apt-get update
    sudo apt-get install -y build-essential dkms linux-headers-$(uname -r) || abort "Failed to install build essentials for CUDA."
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-ubuntu2404.pin -O /tmp/cuda.pin || abort "Failed to download CUDA pin."
    sudo mv /tmp/cuda.pin /etc/apt/preferences.d/cuda-repository-pin-600
    wget https://developer.download.nvidia.com/compute/cuda/12.8.0/local_installers/cuda-repo-ubuntu2404-12-8-local_12.8.0-570.86.10-1_amd64.deb -O /tmp/cuda-repo.deb || abort "Failed to download CUDA repository package."
    sudo dpkg -i /tmp/cuda-repo.deb || abort "dpkg failed for CUDA repository package."
    sudo cp /var/cuda-repo-ubuntu2404-12-8-local/cuda-*-keyring.gpg /usr/share/keyrings/ || abort "Failed to copy CUDA keyring."
    sudo apt-get update
    sudo apt-get -y install cuda-toolkit-12-8 cuda-drivers || abort "Failed to install CUDA Toolkit or drivers."
  else
    ohai "Automatic CUDA installation is not supported for Ubuntu ${VERSION_CODENAME}. Please install CUDA manually from https://developer.nvidia.com/cuda-downloads."
    exit 1
  fi

  ohai "Configuring CUDA environment variables in ${HOME_DIR}/.bashrc..."
  if ! grep -q "CUDA configuration added by 1_cuda_installer.sh" "${HOME_DIR}/.bashrc"; then
    {
      echo ""
      echo "# CUDA configuration added by 1_cuda_installer.sh"
      echo "export PATH=/usr/local/cuda-12.8/bin:\$PATH"
      echo "export LD_LIBRARY_PATH=/usr/local/cuda-12.8/lib64:\$LD_LIBRARY_PATH"
    } | sudo tee -a "${HOME_DIR}/.bashrc" > /dev/null
    ohai "CUDA environment variables appended to ${HOME_DIR}/.bashrc"
  else
    ohai "CUDA environment variables already present in ${HOME_DIR}/.bashrc"
  fi

  ohai "CUDA Toolkit 12.8 installed successfully!"
fi


if $AUTOMATED; then
  ohai "Automated mode: installing btcli from source..."

  # Create virtual environment if not exists, attempting to install python3-venv if needed
  if [ ! -d "${HOME_DIR}/myenv" ]; then
    python3 -m venv "${HOME_DIR}/myenv" 2>/dev/null || {
      ohai "Virtual environment creation failed. Installing python3-venv..."
      sudo apt-get update && sudo apt-get install -y python3-venv || abort "Failed to install python3-venv."
      python3 -m venv "${HOME_DIR}/myenv" || abort "Failed to create btcli virtual environment even after installing python3-venv."
    }
  fi

  source "${HOME_DIR}/myenv/bin/activate" || abort "Failed to activate btcli virtual environment."

  # Append activation command to .bashrc if not already present
  if ! grep -q "source ${HOME_DIR}/myenv/bin/activate" "${HOME_DIR}/.bashrc"; then
    echo "source ${HOME_DIR}/myenv/bin/activate" >> "${HOME_DIR}/.bashrc"
    ohai "Virtual environment activation added to ${HOME_DIR}/.bashrc."
  else
    ohai "Virtual environment activation already present in ${HOME_DIR}/.bashrc."
  fi

  # Clone the btcli repository if not already present
  if [ ! -d "${HOME_DIR}/btcli" ]; then
    git clone https://github.com/opentensor/btcli.git "${HOME_DIR}/btcli" || abort "Failed to clone btcli repository."
  fi

  # Change into the btcli directory and install from source
  cd "${HOME_DIR}/btcli" || abort "Failed to change directory to btcli."
  pip3 install . || abort "Failed to install btcli from source."
  ohai "btcli installed successfully from source."
  cd - > /dev/null
else
  ohai "Installing Bittensor using the official installer script..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/opentensor/bittensor/master/scripts/install.sh)" || abort "Bittensor installation failed."
  ohai "Bittensor installed successfully."

  ohai "IMPORTANT: After reboot, create a wallet pair by running:"
  echo "    btcli w new_coldkey"
  echo "    btcli w new_hotkey"

  ohai "Installation of Docker, NVIDIA components, CUDA, and Bittensor is complete."
  ohai "A reboot is required to finalize installations."
  ohai "Remember to create a wallet pair and fund it before running script 2."
  sudo reboot
fi
