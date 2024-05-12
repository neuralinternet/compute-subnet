#!/bin/bash
set -u

# enable  command completion
set -o history -o histexpand

python="python3"

abort() {
  printf "%s\n" "$1"
  exit 1
}

getc() {
  local save_state
  save_state=$(/bin/stty -g)
  /bin/stty raw -echo
  IFS= read -r -n 1 -d '' "$@"
  /bin/stty "$save_state"
}

exit_on_error() {
    exit_code=$1
    last_command=${@:2}
    if [ $exit_code -ne 0 ]; then
        >&2 echo "\"${last_command}\" command failed with exit code ${exit_code}."
        exit $exit_code
    fi
}

wait_for_user() {
  local c
  echo
  echo "Press RETURN to continue or any other key to abort"
  getc c
  # we test for \r and \n because some stuff does \r instead
  if ! [[ "$c" == $'\r' || "$c" == $'\n' ]]; then
    exit 1
  fi
}

shell_join() {
  local arg
  printf "%s" "$1"
  shift
  for arg in "$@"; do
    printf " "
    printf "%s" "${arg// /\ }"
  done
}

# string formatters
if [[ -t 1 ]]; then
  tty_escape() { printf "\033[%sm" "$1"; }
else
  tty_escape() { :; }
fi
tty_mkbold() { tty_escape "1;$1"; }
tty_underline="$(tty_escape "4;39")"
tty_blue="$(tty_mkbold 34)"
tty_red="$(tty_mkbold 31)"
tty_bold="$(tty_mkbold 39)"
tty_reset="$(tty_escape 0)"

ohai() {
  printf "${tty_blue}==>${tty_bold} %s${tty_reset}\n" "$(shell_join "$@")"
}

# Things can fail later if `pwd` doesn't exist.
# Also sudo prints a warning message for no good reason
cd "/usr" || exit 1

linux_install_pre() {
    sudo apt-get update 
    sudo apt-get install --no-install-recommends --no-install-suggests -y apt-utils curl git cmake build-essential ca-certificates

    # Add Docker's official GPG key:
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    # Add the repository to Apt sources:
    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update

    # Install the latest version of Docker
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    exit_on_error $?
}

linux_install_subtensor() {
    ohai "Cloning subtensor into ~/subtensor"
    mkdir -p ~/subtensor
    sudo apt install -y git
    git clone https://github.com/opentensor/subtensor.git
    cd subtensor
}

linux_install_python() {
    which $python
    if [[ $? != 0 ]] ; then
        ohai "Installing python"
        sudo apt-get install --no-install-recommends --no-install-suggests -y $python
    else
        ohai "Updating python"
        sudo apt-get install --only-upgrade $python
    fi
    exit_on_error $? 
    ohai "Installing python tools"
    sudo apt-get install --no-install-recommends --no-install-suggests -y $python-pip $python-dev 
    exit_on_error $? 
}

linux_update_pip() {
    PYTHONPATH=$(which $python)
    ohai "You are using python@ $PYTHONPATH$"
    ohai "Installing python tools"
    $python -m pip install --upgrade pip
}

linux_install_bittensor() {
    ohai "Cloning bittensor@master into ~/.bittensor/bittensor"
    mkdir -p ~/.bittensor/bittensor
    git clone https://github.com/opentensor/bittensor.git ~/.bittensor/bittensor/ 2> /dev/null || (cd ~/.bittensor/bittensor/ ; git fetch origin master ; git checkout master ; git pull --ff-only ; git reset --hard ; git clean -xdf)
    ohai "Installing bittensor"
    $python -m pip install -e ~/.bittensor/bittensor/
    exit_on_error $? 
}

linux_increase_ulimit(){
    ohai "Increasing ulimit to 1,000,000"
    prlimit --pid=$PPID --nofile=1000000
}

linux_install_pm2() {
    sudo apt update
    sudo apt install -y npm
    sudo npm install pm2 -g
}

linux_install_nvidia_docker() {
    ohai "Installing NVIDIA Docker support"
    cd
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
    curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
    sudo apt update
    sudo apt-get install -y nvidia-container-toolkit
    sudo apt install -y nvidia-docker2
}

linux_install_compute_subnet() {
    ohai "Cloning Compute-Subnet into ~/Compute-Subnet"
    mkdir -p ~/Compute-Subnet
    git clone https://github.com/neuralinternet/Compute-Subnet.git ~/Compute-Subnet/ 2> /dev/null || (cd ~/Compute-Subnet/ ; git pull --ff-only ; git reset --hard ; git clean -xdf)
    
    ohai "Installing Compute-Subnet dependencies"
    cd ~/Compute-Subnet
    $python -m pip install -r requirements.txt
    $python -m pip install --no-deps -r requirements-compute.txt
    $python -m pip install -e .
    sudo apt -y install ocl-icd-libopencl1 pocl-opencl-icd
    
    ohai "Starting Docker service, adding user to docker, and installing 'at' package"
    sudo groupadd docker
    sudo usermod -aG docker $USER
    sudo systemctl start docker
    sudo apt install -y at
    
    cd ~
    exit_on_error $?
}

linux_install_hashcat() {
    wget https://hashcat.net/files/hashcat-6.2.6.tar.gz
    tar xzvf hashcat-6.2.6.tar.gz
    cd hashcat-6.2.6/
    sudo make
    sudo make install
    export PATH=$PATH:/usr/local/bin/
    echo "export PATH=$PATH">>~/.bashrc
    cd ~
}

linux_install_nvidia_cuda() {
    wget https://developer.download.nvidia.com/compute/cuda/12.3.1/local_installers/cuda-repo-ubuntu2204-12-3-local_12.3.1-545.23.08-1_amd64.deb
    sudo dpkg -i cuda-repo-ubuntu2204-12-3-local_12.3.1-545.23.08-1_amd64.deb
    sudo cp /var/cuda-repo-ubuntu2204-12-3-local/cuda-*-keyring.gpg /usr/share/keyrings/
    sudo apt-get update
    sudo apt-get -y install cuda-toolkit-12-3
    sudo apt-get -y install -y cuda-drivers
    export CUDA_VERSION=cuda-12.3
    export PATH=$PATH:/usr/local/$CUDA_VERSION/bin
    export LD_LIBRARY_PATH=/usr/local/$CUDA_VERSION/lib64
    echo "">>~/.bashrc
    echo "PATH=$PATH">>~/.bashrc
    echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH">>~/.bashrc
}

linux_install_ufw() {
    sudo apt update
    sudo apt install -y ufw
    sudo ufw allow 22/tcp
    sudo ufw allow 4444
}

linux_configure_ufw() {
    echo "Please enter the port range for UFW (e.g., 2000-5000):"
    read -p "Enter port range (start-end): " port_range

    if [[ $port_range =~ ^[0-9]+-[0-9]+$ ]]; then
        start_port=$(echo $port_range | cut -d'-' -f1)
        end_port=$(echo $port_range | cut -d'-' -f2)

        if [[ $start_port -lt $end_port ]]; then
            sudo ufw allow $start_port:$end_port/tcp
            sudo ufw enable
            echo "UFW configured successfully with port range $port_range"
        else
            echo "Invalid port range. The start port should be less than the end port."
            exit 1
        fi
    else
        echo "Invalid port range format. Please use the format: start-end (e.g., 2000-5000)"
        exit 1
    fi
}

# Do install.
OS="$(uname)"
if [[ "$OS" == "Linux" ]]; then

    which -s apt
    if [[ $? == 0 ]] ; then
        abort "This linux based install requires apt. To run with other distros (centos, arch, etc), you will need to manually install the requirements"
    fi
    echo """
    
 ░▒▓███████▓▒░ ░▒▓███████▓▒░        ░▒▓███████▓▒░  ░▒▓████████▓▒░ 
░▒▓█▓▒░        ░▒▓█▓▒░░▒▓█▓▒░              ░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░ 
░▒▓█▓▒░        ░▒▓█▓▒░░▒▓█▓▒░              ░▒▓█▓▒░        ░▒▓█▓▒░ 
 ░▒▓██████▓▒░  ░▒▓█▓▒░░▒▓█▓▒░        ░▒▓██████▓▒░        ░▒▓█▓▒░  
       ░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░       ░▒▓█▓▒░              ░▒▓█▓▒░  
       ░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░       ░▒▓█▓▒░             ░▒▓█▓▒░   
░▒▓███████▓▒░  ░▒▓█▓▒░░▒▓█▓▒░       ░▒▓████████▓▒░      ░▒▓█▓▒░   
                                                                                                                                                             
                                                   - Bittensor; Mining a new element.
    """
    ohai "This script will install:"
    echo "git"
    echo "curl"
    echo "cmake"
    echo "build-essential"
    echo "python3"
    echo "python3-pip"
    echo "subtensor"
    echo "bittensor"
    echo "docker"
    echo "nvidia docker support"
    echo "pm2"
    echo "compute-subnet"
    echo "hashcat"
    echo "nvidia drivers and cuda toolkit"
    echo "ufw"

    wait_for_user
    linux_install_pre
    linux_install_subtensor
    linux_install_python
    linux_update_pip
    linux_install_bittensor
    linux_install_pm2
    linux_install_nvidia_docker
    linux_install_compute_subnet
    linux_install_hashcat
    linux_install_nvidia_cuda
    linux_install_ufw
    linux_configure_ufw

    ohai "Would you like to increase the ulimit? This will allow your miner to run for a longer time"
    wait_for_user
    linux_increase_ulimit
    echo ""
    echo ""
    echo "######################################################################"
    echo "##                                                                  ##"
    echo "##                      BITTENSOR SN27 SETUP                        ##"
    echo "##                                                                  ##"
    echo "######################################################################"
    echo ""
    echo ""

elif [[ "$OS" == "Darwin" ]]; then
    echo """
    
██████╗░██╗████████╗████████╗███████╗███╗░░██╗░██████╗░█████╗░██████╗░
██╔══██╗██║╚══██╔══╝╚══██╔══╝██╔════╝████╗░██║██╔════╝██╔══██╗██╔══██╗
██████╦╝██║░░░██║░░░░░░██║░░░█████╗░░██╔██╗██║╚█████╗░██║░░██║██████╔╝
██╔══██╗██║░░░██║░░░░░░██║░░░██╔══╝░░██║╚████║░╚═══██╗██║░░██║██╔══██╗
██████╦╝██║░░░██║░░░░░░██║░░░███████╗██║░╚███║██████╔╝╚█████╔╝██║░░██║
╚═════╝░╚═╝░░░╚═╝░░░░░░╚═╝░░░╚══════╝╚═╝░░╚══╝╚═════╝░░╚════╝░╚═╝░░╚═╝
                                                    
                                                    - Mining a new element.
    """
    ohai "This script will install:"
    echo "xcode"
    echo "homebrew"
    echo "git"
    echo "cmake"
    echo "python3"
    echo "python3-pip"
    echo "bittensor"

    wait_for_user
    mac_install_brew
    mac_install_cmake
    mac_install_python
    mac_update_pip
    mac_install_bittensor
    echo ""
    echo ""
    echo "######################################################################"
    echo "##                                                                  ##"
    echo "##                      BITTENSOR SETUP                             ##"
    echo "##                                                                  ##"
    echo "######################################################################"
else
  abort "Bittensor is only supported on macOS and Linux"
fi

# Use the shell's audible bell.
if [[ -t 1 ]]; then
printf "\a"
fi

echo ""
echo ""
ohai "Welcome. Installation complete. Please reboot your machine for the changes to take effect:"
echo "    $ sudo reboot"
echo ""
echo "- 1. Create a wallet pair"
echo "    $ btcli w new_coldkey (for holding funds)"
echo "    $ btcli w new_hotkey (for running miners)"
echo ""
echo "- 2. To run a miner on the Compute Subnetwork (SN27) you must first create a wallet pair and register to SN27. Visit ${tty_underline}https://docs.neuralinternet.ai/products/subnet-27-compute/bittensor-compute-subnet-miner-setup${tty_reset} for Instructions "
echo "    pm2 start ./neurons/miner.py --name MINER --interpreter python3 -- --netuid 27 --subtensor.network local --wallet.name COLDKEYNAME --wallet.hotkey HOTKEYNAME --axon.port XXXX --logging.debug --miner.blacklist.force_validator_permit --auto_update yes "
echo ""
ohai "Extras:"
echo ""
echo "- Check your tao balance: "
echo "    $ btcli wallet overview"
echo ""
echo "- Stake to your miners:"
echo "    $ btcli stake add"
echo "    $ btcli stake remove"
echo ""
echo "- Create/list/register wallets"
echo "    $ btcli w new_coldkey"
echo "    $ btcli w new_hotkey"
echo "    $ btcli s list or $ btcli w list"
echo "    $ btcli s register --subtensor.network finney --netuid 27"
echo ""
echo "- Use the Python API"
echo "    $ python3"
echo "    >> import bittensor"
echo ""
echo "- Join the discussion: "
echo "    ${tty_underline}https://discord.gg/3rUr6EcvbB${tty_reset}"
echo ""
ohai "Installation complete. Please reboot your machine for the changes to take effect:"
echo "    $ sudo reboot"
