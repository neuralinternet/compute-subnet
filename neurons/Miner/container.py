# The MIT License (MIT)
# Copyright © 2023 GitPhantomman

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
# Step 1: Import necessary libraries and modules

import docker
import paramiko
import os
import string
import secrets
import bittensor as bt

image_name = "ssh-image" #Docker image name
container_name = "ssh-container" #Docker container name
volume_name = "ssh-volume" #Docker volumne name
volume_path = '/tmp' #Path inside the container where the volume will be mounted
ssh_port = 4444  # Port to map SSH service on the host

# Initialize Docker client
client = docker.from_env()
containers = client.containers.list(all=True)

# Kill the currently running container
def kill_container():
    try:
        running_container = None
        for container in containers:
            if container_name in container.name:
                running_container = container
                break
        if running_container:
            running_container.stop()
            running_container.remove()
            bt.logging.info("Container was killed successfully")
            return True
        else:
            bt.logging.info("Unable to find container")
            return False
    except Exception as e:
        bt.logging.info(f"Error killing container {e}")
        return False
    

# Run a new docker container with the given docker_name, image_name and device information
def run_container(cpu_usage, ram_usage, volume_usage, gpu_usage):
    try:
        # Configuration
        password = password_generator(10)
        cpu_assignment = cpu_usage['assignment'] #eg : 0-1
        ram_limit = ram_usage['capacity'] # eg : 1g
        volume_size = volume_usage['capacity'] # eg : 1073741824 ( 1GB )
        gpu_capabilities = gpu_usage['capabilities'] # eg : all,capabilities=utility

        # Step 1: Build the Docker image with an SSH server
        dockerfile_content = '''
        FROM ubuntu
        RUN apt-get update && apt-get install -y openssh-server
        RUN mkdir -p /run/sshd  # Create the /run/sshd directory
        RUN echo 'root:''' + password + '''' | chpasswd
        RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
        RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
        RUN sed -i 's/#ListenAddress 0.0.0.0/ListenAddress 0.0.0.0/' /etc/ssh/sshd_config
        CMD ["/usr/sbin/sshd", "-D"]
        '''
        dockerfile_path = "/tmp/dockerfile"
        with open(dockerfile_path, "w") as dockerfile:
            dockerfile.write(dockerfile_content)

        # Build the Docker image
        client.images.build(path=os.path.dirname(dockerfile_path), dockerfile=os.path.basename(dockerfile_path), tag=image_name)

        # Create the Docker volume with the specified size
        #client.volumes.create(volume_name, driver = 'local', driver_opts={'size': volume_size})

        # Step 2: Run the Docker container
        container = client.containers.run(
            image=image_name,
            name=container_name,
            detach=True,
            cpuset_cpus=cpu_assignment,
            mem_limit=ram_limit,
            #volumes={volume_name: {'bind': volume_path, 'mode': 'rw'}},
            #gpus=gpu_capabilities,
            environment = ["NVIDIA_VISIBLE_DEVICES=all"],
            ports={22: ssh_port}
        )
        
        # Check the status to determine if the container ran successfully

        if container.status == "created":
            bt.logging.info("Container was created successfully")
            return {'status' : True, 'username' : 'root', 'password' : password}
        else:
            bt.logging.info(f"Container falied with status : {container.status}")
            return {'status' : False}
    except Exception as e:
        bt.logging.info(f"Error running container {e}")
        return {'status' : False}

# Randomly generate password for given length
def password_generator(length):
    alphabet = string.ascii_letters + string.digits  # You can customize this as needed
    random_str = ''.join(secrets.choice(alphabet) for _ in range(length))
    return random_str