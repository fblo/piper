# syntax=docker/dockerfile:1.4

# === STAGE 1: Builder (Builds espeak-ng AND piper-tts wheels) ===
FROM quay.io/centos/centos:stream10 AS builder

# 1. Install Build Dependencies
RUN dnf -y update && \
    dnf install -y --setopt=install_weak_deps=False \
        git \
        cmake \
        gcc-c++ \
        make \
        autoconf \
        automake \
        libtool \
        pkgconfig \
        which \
        python3-devel \
        python3-pip \
    && dnf clean all

# 2. Build and Install espeak-ng from source
# (This provides the -devel headers for the pip install)
WORKDIR /build
RUN GIT_SSL_NO_VERIFY=true git clone --depth 1 --branch main https://forgejo.hostics.fr/fblo/espeak-ng
WORKDIR /build/espeak-ng
RUN ls -la && \
    ./autogen.sh && \
    ./configure --prefix=/usr && \
    make && \
    make install

# 3. Clone Piper
WORKDIR /build
RUN git clone https://github.com/OHF-Voice/piper1-gpl.git
WORKDIR /build/piper1-gpl

# 4. ⚡️ THE FIX: Build all Python dependencies into wheels
# We create a wheelhouse for piper AND all its C++ dependencies
RUN mkdir -p /build/wheelhouse
RUN pip3 wheel . -w /build/wheelhouse


# === STAGE 2: Monolithic Runtime (CentOS Stream 10 Base) ===
FROM quay.io/centos/centos:stream10

# 1. Install System Dependencies (Runtime only)
RUN dnf -y update && \
    # We need EPEL to find the espeak-ng runtime
    dnf install -y epel-release && \
    dnf install -y --setopt=install_weak_deps=False \
        python3-pip \
        python3-devel \
        python3-setuptools \
        gcc \
        gcc-c++ \
        make \
        espeak-ng \
        redhat-rpm-config \
    && dnf clean all

# 2. Install Python Dependencies from requirements.txt
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 3. ⚡️ THE FIX: Install Piper from the local wheelhouse
# This is fast, robust, and requires no path guessing.
COPY --from=builder /build/wheelhouse /tmp/wheelhouse
RUN pip3 install --no-index --find-links=/tmp/wheelhouse numpy==1.26.4
RUN pip3 install --no-index --find-links=/tmp/wheelhouse --force-reinstall piper-tts
RUN pip3 install --no-index --find-links=/tmp/wheelhouse /tmp/wheelhouse/*.whl
RUN pip3 install --force-reinstall numpy==1.26.4
RUN rm -rf /tmp/wheelhouse

# 4. Update the dynamic linker cache
RUN ldconfig

# 5. Define the Voice Mount Point (for external models)
ENV VOICE_DIR="/opt/voices"
RUN mkdir -p ${VOICE_DIR}

# 5.5. Create voices configuration file generator scripts
COPY generate_voices_config.py /app/generate_voices_config.py
COPY generate_voices_iv2us.py /app/generate_voices_iv2us.py

# 6. Copy the application code and startup script
COPY main2.py .
COPY start2.sh .
RUN chmod +x /app/start2.sh

# 6.5. Generate voices configuration files on startup
RUN python3 /app/generate_voices_config.py && \
    python3 /app/generate_voices_iv2us.py

# 7. Define the Execution Environment
EXPOSE 5051
CMD ["/app/start2.sh"]
