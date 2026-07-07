# OverwatcherPI

A fully async, modular, open-source daemon that streams telemetry to a secure Telegram Bot. It performs differential network surveillance, BLE discovery, and hourly trend analytics. Designed for Raspberry Pi 5 (8 GB RAM), Linux.

## Features
- **Network Surveillance:** Fast `nmap` based ARP sweeps of the local subnet, enhanced with `zeroconf` mDNS discovery.
- **BLE Discovery:** Async Bluetooth Low Energy scanning via `bleak`.
- **Differential Tracking:** Automatically diffs current topology against baseline and flags new devices.
- **Intruder Defense:** Runs targeted `nmap -sV` port scans on unknown devices before alerting you.
- **Ping Monitor:** Pin critical infrastructure hosts for constant 1-minute uptime checks.
- **SSH Auth Monitoring:** Actively tails `/var/log/auth.log` for brute-force attacks and successful logins.
- **System Diagnostics:** Reports Pi CPU, RAM, Disk, SoC temperature, and checks for under-voltage/throttling events.

## Hardware & OS Requirements
- Raspberry Pi (optimized for Pi 5 8GB)
- Linux OS (Raspberry Pi OS Bookworm or similar)
- Python 3.10+
- `nmap` and `samba-common-bin` installed globally (`sudo apt install nmap samba-common-bin`)

## Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/yourusername/OverwatcherPI.git
   cd OverwatcherPI
   ```

2. **Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Bluetooth Permissions (Crucial for BLE):**
   To allow the bot to query BlueZ without running as root, add your user to the bluetooth group:
   ```bash
   sudo usermod -aG bluetooth $USER
   ```
   *(You may need to log out and back in for this to take effect).*

4. **Nmap Permissions (Crucial for Network Sweeps):**
   To allow nmap to run privileged scans without root access, grant it raw socket capabilities:
   ```bash
   sudo setcap cap_net_raw,cap_net_admin,cap_net_bind_service+eip $(which nmap)
   ```

5. **Configuration:**
   ```bash
   cp .env.example .env
   # Edit .env and provide your Telegram Bot Token and your Telegram User ID
   nano .env
   ```

## Running Locally (Development)
```bash
source venv/bin/activate
python main.py
```

## Production Deployment
The recommended deployment path is `/opt/OverwatcherPI/`.

1. **Copy to /opt:**
   ```bash
   sudo cp -r /home/abhipra/Work/OverwatcherPI /opt/
   sudo chown -R your_username:your_username /opt/OverwatcherPI
   ```

2. **Enable systemd service:**
   ```bash
   sudo cp /opt/OverwatcherPI/overwatcher.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now overwatcher
   ```

## Telegram Commands
- `/status` — Get Raspberry Pi system health & throttling status
- `/network` — Trigger immediate local subnet sweep
- `/bluetooth` — Trigger immediate 10-second BLE discovery
- `/speedtest` — Run internet speed test
- `/whitelist <mac>` — Mark a device MAC as safe
- `/monitor <ip>` — Pin a critical host for 1-minute downtime checks
- `/unmonitor <ip>` — Remove a host from ping monitor

## Known Limitations
- **BLE Tracking:** iOS/Android BLE addresses rotate roughly every 15 minutes by design. Devices never paired/bonded with this Pi cannot be reliably tracked or identified long-term — that's BLE privacy working as intended, not a bug.
