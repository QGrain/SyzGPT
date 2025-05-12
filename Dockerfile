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
# Setup SyzGPT-generator (create python virtual env and install requirements)
RUN git clone https://github.com/QGrain/SyzGPT.git /root/SyzGPT && \
    pip install virtualenvwrapper && \
    mkdir /root/.virtualenvs && \
    echo "export WORKON_HOME=/root/.virtualenvs" >> /root/.bashrc && \
    echo "export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3" >> /root/.bashrc && \
    echo "source $(which virtualenvwrapper.sh)" >> /root/.bashrc && \
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
    make -j$(($(nproc)/2)) && \
    mkdir -p cfgdir benchdir workdir/v6-1 && \
    cp /root/SyzGPT/fuzzer/*.cfg /root/fuzzers/SyzGPT-fuzzer/cfgdir/ && \
    curl https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.6.12.tar.xz | tar -C /root/kernels -xJ && \
    cd /root/kernels/linux-6.6.12 && cp /root/SyzGPT/fuzzer/syzbot-6.6.config .config && \
    source $(which virtualenvwrapper.sh) && workon syzgpt && \
    syzqemuctl init --images-home=/root/images --wait 2>&1 && \
    syzqemuctl create image-1 && syzqemuctl create image-2

# User should compile the kernel manually with make CC=gcc olddefconfig && make CC=gcc -j$(($(nproc)/2))
# Check details in Setup step 5 in /root/SyzGPT/fuzzer/README.md


WORKDIR /root