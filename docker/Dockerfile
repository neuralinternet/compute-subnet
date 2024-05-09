ARG CUDA_VERSION="12.4.1"
ARG CUDA_VERSION_LOC="cuda-12.4"
ARG OS="ubuntu22.04"
ARG BUILD_BRANCH="main"

ARG CUDA_BUILDER_IMAGE="${CUDA_VERSION}-devel-${OS}"
ARG CUDA_RUNTIME_IMAGE="${CUDA_VERSION}-runtime-${OS}"
ARG CUDA_BASE_IMAGE="${CUDA_VERSION}-base-${OS}"

FROM nvidia/cuda:${CUDA_RUNTIME_IMAGE} as build

# We need to set the host to 0.0.0.0 to allow outside access
ENV HOST 0.0.0.0
ENV CUDA_DOCKER_ARCH=all
ENV HOME=/root

WORKDIR /root

RUN apt-get update && apt-get upgrade -y \
    && apt-get install --no-install-recommends --no-install-suggests -y \
    git python3 python3-pip python3-venv \
    build-essential wget curl \
    ocl-icd-opencl-dev opencl-headers clinfo \
    libclblast-dev libopenblas-dev \
    libnvrtc-builtins11.5 libnvrtc11.2 \
    && mkdir -p /etc/OpenCL/vendors && echo "libnvidia-opencl.so.1" > /etc/OpenCL/vendors/nvidia.icd && \
    rm -rf /var/lib/apt/list/*

RUN pip3 install -U pip && pip3 install -U wheel && pip3 install -U setuptools && pip install nvidia-cuda-nvrtc-cu12

# install hashcat
RUN git clone https://github.com/hashcat/hashcat.git && \
    cd hashcat && \
    make install -j4 && \
    cd ..

# install SN27
RUN git clone https://github.com/neuralinternet/Compute-Subnet.git && \
    cd Compute-Subnet && \
    git checkout ${BUILD_BRANCH} && \
    python3 -m pip install --no-cache-dir -r requirements.txt && \
    python3 -m pip install --no-cache-dir -e . && \
    cd ..


FROM nvidia/cuda:${CUDA_BASE_IMAGE} as base

RUN apt-get update && apt-get upgrade -y \
    && apt-get install --no-install-recommends --no-install-suggests -y \
    make git python3 python3-pip python3-venv \
    ocl-icd-opencl-dev opencl-headers clinfo \
    libclblast-dev libopenblas-dev \
    libnvrtc-builtins11.5 libnvrtc11.2 \
    && mkdir -p /etc/OpenCL/vendors && echo "libnvidia-opencl.so.1" > /etc/OpenCL/vendors/nvidia.icd && \
    rm -rf /var/lib/apt/list/*

# We need to set the host to 0.0.0.0 to allow outside access
ENV HOME=/root
ENV HOST 0.0.0.0
ENV CUDA_DOCKER_ARCH=all

ENV PATH=$PATH:/usr/local/${CUDA_VERSION_LOC}/bin
ENV LD_LIBRARY_PATH=/usr/local/${CUDA_VERSION_LOC}/lib64;/lib/x86_64-linux-gnu;$LD_LIBRARY_PATH

WORKDIR /root

COPY --from=build /root /root

RUN cd hashcat && make install -j4 && cd ..

COPY --from=build /usr/local/lib/python3.10/dist-packages/ /usr/local/lib/python3.10/dist-packages/

RUN pip3 install -U eth_utils

COPY entrypoint.sh btcli /usr/local/bin/

RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/btcli

EXPOSE 8091

ENTRYPOINT ["entrypoint.sh"]

CMD ["/bin/bash"]