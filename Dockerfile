# The image of syzgpt:full
# This Dockerfile builds the image for kernel fuzzing based on qgrain/kernel-fuzz:2004_base

# FROM qgrain/kernel-fuzz:2004_base
FROM kernel-fuzz:2004_base


ARG http_proxy
ARG https_proxy
ARG no_proxy

ENV GOROOT=/root/software/go \
    GOPATH=/root/software/gopath \
    PATH=/root/software/go/bin:$PATH \
    LC_CTYPE=C.UTF-8


SHELL ["/bin/bash", "-c"]
# Setup SyzGPT-generator (virtualenvwrapper should exist and install requirements)
RUN git clone https://github.com/QGrain/SyzGPT.git /root/SyzGPT && \
    source $(which virtualenvwrapper.sh) && \
    mkvirtualenv syzgpt && \
    workon syzgpt && \
    pip install -r /root/SyzGPT/requirements.txt && \
    cp /root/SyzGPT/config.py /root/SyzGPT/private_config.py

# User should edit API_KEY in /root/SyzGPT/private_config.py


# Setup SyzGPT-fuzzer
RUN cd /root/fuzzers && git clone https://github.com/google/syzkaller.git SyzGPT-fuzzer && \
    cd /root/fuzzers/SyzGPT-fuzzer && git checkout f1b6b00 && \
    patch -p1 < /root/SyzGPT/fuzzer/SyzGPT-fuzzer_for_f1b6b00.patch && \
    mkdir -p cfgdir benchdir workdir/v6-1 && \
    cp /root/SyzGPT/fuzzer/*.cfg /root/fuzzers/SyzGPT-fuzzer/cfgdir/ && \
    cp -r /root/fuzzers/SyzGPT-fuzzer /root/fuzzers/SyzGPT-KernelGPT-fuzzer && \
    cd /root/fuzzers/SyzGPT-fuzzer && make -j$(($(nproc)/2))

# Setup SyzGPT-KernelGPT-fuzzer
RUN cd /root/fuzzers/SyzGPT-KernelGPT-fuzzer && \
    cp /root/SyzGPT/experiments/KernelGPT/sys-linux-specifications/* sys/linux/ && \
    make -j$(($(nproc)/2))

# Download linux-6.6.12 and set syzbot.config
RUN curl https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.6.12.tar.xz | tar -C /root/kernels -xJ && \
    cd /root/kernels/linux-6.6.12 && \
    cp /root/SyzGPT/fuzzer/syzbot-6.6.config .config

# 1. User should compile the kernel manually with make CC=gcc olddefconfig && make CC=gcc -j$(($(nproc)/2))
# Check details in Setup step 5 in /root/SyzGPT/fuzzer/README.md
# 2. User should build the image in a privileged container with syzqemuctl init --images-home=/root/images
# And syzqemuctl create image-1 && syzqemuctl create image-2


WORKDIR /root