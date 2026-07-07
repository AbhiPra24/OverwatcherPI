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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default entrypoint: the main bot process.
# The sniffer service overrides this via compose `command:`
CMD ["python", "main.py"]
