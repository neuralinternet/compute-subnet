# Bittensor Subnet 27 docker for miner and validator

Based on Nvidia/cuda image to build up the miner and validator

The DooD (Docker outside Docker) technology was used due to DinD (Docker in Docker) container require more storage for space to include the docker.io service inside docker.  The docker image will build from latest hashcat and compute-subnet and include the CUDA and OPENCL for runing bittensor, pytorch and hashcat. Currently, the subtensor and bittensor latest version (6.12.4) are not included in order to save the image size.  

Host is required to have the docker.io and NVIDIA container toolkit installed and set up. Privileged mode or [Sysbox](https://github.com/nestybox/sysbox) configured with NVIDIA GPUs are required like any other DinD/DooD container with root requirement.

Rebuild Docker Image:
	- docker image build -t sn27:latest -f Dockerfile .

Run the Docker via docker compose:
	- docker compose up -d

Run the Docker via CLI:
	- docker run --gpus all -v bittensor:/root/.bittensor -v /var/run/docker.sock:/var/run/docker.sock -v /usr/bin/docker:/usr/bin/docker -p 8091:8091 -e BIND_ADDR=0.0.0.0:8091 -it --privileged sn27:latest


Configure SN27 and Run Validator or Miner:
	- configure the WANDB and backup the key
	 cd /root/Compute-Subnet/
	 echo WANDB_API_KEY="your key" > .env
	 cp .env /root/.bittensor/

	- Create wallet (change the wallet name), the bittensor wallet will save to /root/.bittensor folder.
	btcli wallet new_coldkey --wallet.name validator
	btcli wallet new_hotkey --wallet.name validator --wallet.hotkey default
	btcli wallet overview --wallet.name validator

	- Register (change the wallet name)
	btcli subnet register --netuid 27 --wallet.name validator --wallet.hotkey default

	- Run miner 
	cd /root/Compute-Subnet/
	python neurons/miner.py --netuid 27 --subtensor.network finney --wallet.name miner --wallet.hotkey default --logging.debug

	- Run Validator
	cd /root/Compute-Subnet/
	python neurons/validator.py --netuid 27 --subtensor.network finney --wallet.name validator --wallet.hotkey default --logging.debug


