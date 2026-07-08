# syntax=docker/dockerfile:1
# OverwatcherPI — bot + sniffer image
# Both services share this image; the compose file sets the command per-service.
FROM python:3.12-slim

# System deps: nmap for host discovery, iproute2 for network tools,
# bluez for BlueZ userspace (bleak uses D-Bus passthrough from host)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    iproute2 \
    bluez \
    curl \
    libcap2-bin \
    && rm -rf /var/lib/apt/lists/*

# Grant nmap necessary capabilities so it can run as non-root
RUN setcap cap_net_raw,cap_net_admin,cap_net_bind_service+eip $(which nmap)

# Create a non-root user mimicking typical Pi UID 1000
# - bluetooth: for D-Bus / BLE access
# - video: for vcgencmd access
# - adm: for reading /var/log/auth.log
RUN groupadd -g 1000 overwatcher && \
    useradd -u 1000 -g overwatcher -G bluetooth,video,adm -s /bin/bash -m overwatcher

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY . .

USER overwatcher

# Default entrypoint: the main bot process.
# The sniffer service overrides this via compose `command:`
CMD ["python", "main.py"]
