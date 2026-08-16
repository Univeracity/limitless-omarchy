FROM ubuntu:25.10 AS runtime-base

ENV DEBIAN_FRONTEND=noninteractive

# Quickshell needs the Qt private development headers for its Wayland support.
# The optional services are disabled below so this remains a focused panel
# runtime rather than a full desktop image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        git \
        libcli11-dev \
        libdrm-dev \
        libegl1-mesa-dev \
        libgl1-mesa-dev \
        libjemalloc-dev \
        libwayland-dev \
        ninja-build \
        pkg-config \
        python3 \
        python3-pip \
        qt6-base-dev \
        qt6-base-private-dev \
        qt6-declarative-dev \
        qt6-declarative-private-dev \
        qt6-shadertools-dev \
        qt6-svg-dev \
        qt6-wayland \
        qt6-wayland-dev \
        qt6-wayland-private-dev \
        wayland-protocols \
        weston

FROM runtime-base AS quickshell

RUN git clone --depth 1 --branch v0.3.0 https://github.com/quickshell-mirror/quickshell.git /opt/quickshell-source

RUN cmake -S /opt/quickshell-source -B /opt/quickshell-build -GNinja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCRASH_HANDLER=OFF \
        -DHYPRLAND=OFF \
        -DI3=OFF \
        -DSCREENCOPY=OFF \
        -DSERVICE_MPRIS=OFF \
        -DSERVICE_PAM=OFF \
        -DSERVICE_PIPEWIRE=OFF \
        -DSERVICE_POLKIT=OFF \
        -DSERVICE_STATUS_NOTIFIER=OFF \
        -DX11=OFF

RUN cmake --build /opt/quickshell-build --parallel 2 \
    && cmake --install /opt/quickshell-build

WORKDIR /workspace
