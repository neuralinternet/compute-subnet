#!/bin/bash

# Start docker
# start-docker.sh
cp /root/.bittensor/.env /root/Compute-Subnet/.env

# Execute specified command
"$@"
