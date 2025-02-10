#!/bin/bash
set -u
set -o history -o histexpand

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

# Pre-check: Ensure Bittensor wallets exist
if $AUTOMATED; then
  HOME_DIR="/home/ubuntu"
  USER_NAME="ubuntu"
else
  USER_NAME=${SUDO_USER:-$(whoami)}
  HOME_DIR=$(eval echo "~${USER_NAME}")
fi
DEFAULT_WALLET_DIR="${HOME_DIR}/.bittensor/wallets"

if [ ! -d "${DEFAULT_WALLET_DIR}" ] || [ -z "$(ls -A "${DEFAULT_WALLET_DIR}" 2>/dev/null)" ]; then
  ohai "WARNING: No Bittensor wallets detected in ${DEFAULT_WALLET_DIR}."
  echo "Before running this installer, create a wallet pair by executing:"
  echo "    btcli w new_coldkey"
  echo "    btcli w new_hotkey"
  exit 1
fi

if [ "$AUTOMATED" = true ]; then
  if [ -f "/home/ubuntu/compute-subnet/setup.py" ] || [ -f "/home/ubuntu/compute-subnet/pyproject.toml" ]; then
      CS_PATH="/home/ubuntu/compute-subnet"
      ohai "Automated mode: Using repository root at ${CS_PATH}."
  else
      ohai "Automated mode: Repository root not found at /home/ubuntu/compute-subnet, using current directory."
      CS_PATH="$(pwd)"
  fi
  cd "$CS_PATH" || abort "Failed to change directory to repository root at ${CS_PATH}"
else
    if REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null); then
         ohai "Detected repository root: ${REPO_ROOT}"
         cd "$REPO_ROOT" || abort "Failed to change directory to repository root at ${REPO_ROOT}"
         CS_PATH="$REPO_ROOT"
    else
         CS_PATH="$(pwd)"
         if [ ! -f "$CS_PATH/setup.py" ] && [ ! -f "$CS_PATH/pyproject.toml" ]; then
             if [ -f "$(dirname "$CS_PATH")/setup.py" ] || [ -f "$(dirname "$CS_PATH")/pyproject.toml" ]; then
                  ohai "Detected running in a subdirectory; switching to repository root."
                  cd "$(dirname "$CS_PATH")" || abort "Failed to change directory to repository root"
                  CS_PATH="$(pwd)"
             else
                  abort "Repository root not found. Please run this script from within the compute‑subnet repository."
             fi
         fi
    fi
fi


VENV_DIR="${HOME_DIR}/venv"

cat << "EOF"

   NI compute‑subnet Installer - compute‑subnet Setup
   (This script is running from within the compute‑subnet repository)

EOF

if [ -z "${VIRTUAL_ENV:-}" ] || [ "$VIRTUAL_ENV" != "$VENV_DIR" ]; then
    if [ -f "$VENV_DIR/bin/activate" ]; then
         ohai "Activating virtual environment from ${VENV_DIR}..."
         source "$VENV_DIR/bin/activate"
    else
         ohai "Virtual environment not found. Creating a new virtual environment at ${VENV_DIR}..."
         if ! python3 -m ensurepip --version > /dev/null 2>&1; then
             ohai "ensurepip is not available. Installing the appropriate python-venv package..."
             py_ver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
             sudo apt-get update || abort "Failed to update package lists."
             sudo apt-get install -y python${py_ver}-venv || abort "Failed to install python${py_ver}-venv."
         fi
         python3 -m venv "$VENV_DIR" || abort "Failed to create virtual environment."
         ohai "Activating virtual environment..."
         source "$VENV_DIR/bin/activate"
    fi
fi

ohai "Updating package lists and installing system prerequisites..."
sudo apt-get update || abort "Failed to update package lists."
sudo apt-get install -y python3 python3-pip python3-venv build-essential dkms linux-headers-$(uname -r) || abort "Failed to install prerequisites."

ohai "Upgrading pip in the virtual environment..."
pip install --upgrade pip || abort "Failed to upgrade pip in virtual environment."

ohai "Installing compute‑subnet base dependencies..."
pip install -r requirements.txt || abort "Failed to install base requirements."
pip install --no-deps -r requirements-compute.txt || abort "Failed to install compute requirements."

ohai "Installing compute‑subnet in editable mode..."
pip install -e . || abort "Editable install of compute‑subnet failed."

if ! python -c "import torch" &>/dev/null; then
    ohai "PyTorch is not installed. Installing torch, torchvision, and torchaudio..."
    pip install torch torchvision torchaudio || abort "Failed to install PyTorch packages."
fi

ohai "Installing extra OpenCL libraries..."
sudo apt-get install -y ocl-icd-libopencl1 pocl-opencl-icd || abort "Failed to install OpenCL libraries."

ohai "Installing npm and PM2..."
sudo apt-get update
sudo apt-get install -y npm || abort "Failed to install npm."
sudo npm install -g pm2 || abort "Failed to install PM2."

if $AUTOMATED; then
  NETUID="${NETUID:-15}"
  if [[ "$NETUID" -eq 27 ]]; then
    SUBTENSOR_NETWORK_DEFAULT="subvortex.info:9944"
  elif [[ "$NETUID" -eq 15 ]]; then
    SUBTENSOR_NETWORK_DEFAULT="test"
  else
    SUBTENSOR_NETWORK_DEFAULT="subvortex.info:9944"
  fi
  SUBTENSOR_NETWORK="${SUBTENSOR_NETWORK:-$SUBTENSOR_NETWORK_DEFAULT}"
  axon_port="${AXON_PORT:-8091}"
  ohai "Automated mode: using parameters:"
  echo "    NETUID: ${NETUID}"
  echo "    subtensor.network: ${SUBTENSOR_NETWORK}"
  echo "    axon_port: ${axon_port}"
else
  echo
  echo "Configure your miner setup."
  echo "-------------------------------------"
  echo "Select the Bittensor network:"
  echo "  1) Main Network (netuid 27)"
  echo "  2) Test Network (netuid 15)"
  read -rp "Enter your choice [1 or 2]: " network_choice
  if [[ "$network_choice" == "1" ]]; then
    NETUID=27
    SUBTENSOR_NETWORK_DEFAULT="subvortex.info:9944"
  elif [[ "$network_choice" == "2" ]]; then
    NETUID=15
    SUBTENSOR_NETWORK_DEFAULT="test"
  else
    echo "Invalid choice. Defaulting to Main Network."
    NETUID=27
    SUBTENSOR_NETWORK_DEFAULT="subvortex.info:9944"
  fi
  read -rp "Enter the --subtensor.network value (default: ${SUBTENSOR_NETWORK_DEFAULT}): " SUBTENSOR_NETWORK
  SUBTENSOR_NETWORK=${SUBTENSOR_NETWORK:-$SUBTENSOR_NETWORK_DEFAULT}
  read -rp "Enter the axon port (default: 8091): " axon_port
  axon_port=${axon_port:-8091}
fi

if $AUTOMATED; then
  COLDKEY_WALLET="${COLDKEY_WALLET:-}"
  if [[ -z "$COLDKEY_WALLET" ]]; then
      COLDKEY_WALLET=$(ls -1 "${DEFAULT_WALLET_DIR}" | head -n 1)
      ohai "Automated mode: automatically selected coldkey wallet: ${COLDKEY_WALLET}"
  else
      ohai "Automated mode: using provided coldkey wallet: ${COLDKEY_WALLET}"
  fi

  HOTKEY_DIR="${DEFAULT_WALLET_DIR}/${COLDKEY_WALLET}/hotkeys"
  HOTKEY_WALLET="${HOTKEY_WALLET:-}"
  if [[ -z "$HOTKEY_WALLET" ]]; then
      HOTKEY_WALLET=$(ls -1 "$HOTKEY_DIR" | head -n 1)
      ohai "Automated mode: automatically selected hotkey: ${HOTKEY_WALLET}"
  else
      ohai "Automated mode: using provided hotkey: ${HOTKEY_WALLET}"
  fi
else
  ohai "Detecting available wallets in ${DEFAULT_WALLET_DIR}..."
  i=1
  declare -A wallet_map
  for wallet in "${DEFAULT_WALLET_DIR}"/*; do
    wallet_name=$(basename "$wallet")
    echo "  [$i] $wallet_name"
    wallet_map[$i]="$wallet_name"
    ((i++))
  done

  read -rp "Enter the number corresponding to your COLDKEY wallet: " coldkey_choice
  COLDKEY_WALLET="${wallet_map[$coldkey_choice]}"
  if [[ -z "$COLDKEY_WALLET" ]]; then
    abort "Invalid selection for coldkey wallet."
  fi

  HOTKEY_DIR="${DEFAULT_WALLET_DIR}/${COLDKEY_WALLET}/hotkeys"
  if [ ! -d "$HOTKEY_DIR" ] || [ -z "$(ls -A "$HOTKEY_DIR")" ]; then
      abort "No hotkeys found for coldkey wallet ${COLDKEY_WALLET} in $HOTKEY_DIR"
  fi

  ohai "Available hotkeys for coldkey ${COLDKEY_WALLET}:"
  i=1
  declare -A hotkey_map
  for hotkey in "$HOTKEY_DIR"/*; do
    hk_name=$(basename "$hotkey")
    echo "  [$i] $hk_name"
    hotkey_map[$i]="$hk_name"
    ((i++))
  done

  read -rp "Enter the number corresponding to your HOTKEY: " hotkey_choice
  HOTKEY_WALLET="${hotkey_map[$hotkey_choice]}"
  if [[ -z "$HOTKEY_WALLET" ]]; then
    abort "Invalid selection for hotkey."
  fi
fi

ohai "Installing and configuring UFW..."
sudo apt-get update
sudo apt-get install -y ufw || abort "Failed to install ufw."
ohai "Allowing SSH (port 22) through UFW..."
sudo ufw allow 22/tcp
ohai "Allowing validator port 4444 through UFW..."
sudo ufw allow 4444/tcp
ohai "Allowing Axon port ${axon_port} through UFW..."
sudo ufw allow "${axon_port}/tcp"
ohai "Enabling UFW..."
sudo ufw --force enable
ohai "UFW configured. Open ports: 22 (SSH), 4444 (validators), ${axon_port} (Axon)."

ask_user_for_wandb_key() {
  read -rp "Enter WANDB_API_KEY (leave blank if none): " WANDB_API_KEY
}

inject_wandb_env() {
  local env_example="${CS_PATH}/.env.example"
  local env_path="${CS_PATH}/.env"
  ohai "Configuring .env for compute‑subnet..."
  if [[ ! -f "$env_path" ]] && [[ -f "$env_example" ]]; then
    ohai "Copying .env.example to .env"
    cp "$env_example" "$env_path" || abort "Failed to copy .env.example to .env"
  fi

  ohai "Updating WANDB_API_KEY in .env"
  sed -i "s@^WANDB_API_KEY=.*@WANDB_API_KEY=\"$WANDB_API_KEY\"@" "$env_path" || abort "Failed to update .env"
  ohai "Finished configuring .env"
}

if $AUTOMATED; then
  WANDB_API_KEY="${WANDB_KEY:-}"
else
  ask_user_for_wandb_key
fi

inject_wandb_env

if [ ! -f "$CS_PATH/neurons/miner.py" ]; then
  abort "miner.py not found in ${CS_PATH}/neurons. Please check the repository."
fi

if [ ! -x "$CS_PATH/neurons/miner.py" ]; then
  ohai "miner.py is not executable; setting executable permission..."
  chmod +x "$CS_PATH/neurons/miner.py" || abort "Failed to set executable permission on miner.py."
fi

ohai "Creating PM2 configuration file for the miner process..."
CURRENT_PATH=${PATH}
CURRENT_LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-""}

PM2_CONFIG_FILE="${CS_PATH}/pm2_miner_config.json"
cat > "$PM2_CONFIG_FILE" <<EOF
{
  "apps": [{
    "name": "subnet27_miner",
    "cwd": "${CS_PATH}",
    "script": "./neurons/miner.py",
    "interpreter": "${VENV_DIR}/bin/python3",
    "args": "--netuid ${NETUID} --subtensor.network ${SUBTENSOR_NETWORK} --wallet.name ${COLDKEY_WALLET} --wallet.hotkey ${HOTKEY_WALLET} --axon.port ${axon_port} --logging.debug --miner.blacklist.force_validator_permit --auto_update yes",
    "env": {
      "HOME": "${HOME_DIR}",
      "PATH": "/usr/local/cuda-12.8/bin:${CURRENT_PATH}",
      "LD_LIBRARY_PATH": "/usr/local/cuda-12.8/lib64:${CURRENT_LD_LIBRARY_PATH}"
    },
    "out_file": "${CS_PATH}/pm2_out.log",
    "error_file": "${CS_PATH}/pm2_error.log"
  }]
}
EOF

ohai "PM2 configuration file created at ${PM2_CONFIG_FILE}"

ohai "Starting miner process with PM2..."
pm2 start "$PM2_CONFIG_FILE" || abort "Failed to start PM2 process."

ohai "Miner process started."
echo "You can view logs using: pm2 logs subnet27_miner (or check ${CS_PATH}/pm2_out.log and ${CS_PATH}/pm2_error.log)"
echo "Ensure your chosen hotkey is registered on-chain (using btcli register)."
echo "The miner process will start in the background once your hotkey is registered on-chain."
echo
echo "Installation and setup complete. Your miner is now running in the background."
