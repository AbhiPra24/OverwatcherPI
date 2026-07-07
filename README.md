# OverwatcherPI

A fully async, modular, open-source daemon that streams telemetry to a secure Telegram Bot. It performs differential network surveillance, BLE discovery, and hourly trend analytics. Designed for Raspberry Pi 5 (8 GB RAM), Linux.

## Features
- **Network Surveillance:** Fast `nmap` based ARP sweeps of the local subnet, enhanced with `zeroconf` mDNS discovery.
- **BLE Discovery:** Async Bluetooth Low Energy scanning via `bleak`.
- **Differential Tracking:** Automatically diffs current topology against baseline and flags new devices.
- **Intruder Defense:** Runs targeted `nmap -sV` port scans on unknown devices before alerting you.
- **Port Drift Tracking:** Scans known devices daily to detect and alert on newly opened ports.
- **Ping Monitor:** Pin critical infrastructure hosts for constant 1-minute uptime checks.
- **Latency & Quality Monitoring:** Continuously tracks gateway and WAN ping jitter and loss.
- **SSH Auth Monitoring:** Actively tails `/var/log/auth.log` for brute-force attacks and successful logins.
- **Passive Sniffer:** Separate unprivileged daemon tracking rogue DHCP servers and ARP spoofing conflicts.
- **Web Dashboard:** Read-only Streamlit dashboard for historical topology, device search, and event logging over your LAN.
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

6. **Dashboard Setup:**
   The Streamlit dashboard requires a separate virtual environment to avoid dependency conflicts:
   ```bash
   python3 -m venv dashboard/venv
   source dashboard/venv/bin/activate
   pip install -r dashboard/requirements-dashboard.txt
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

2. **Enable Main Service:**
   ```bash
   sudo cp /opt/OverwatcherPI/overwatcher.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now overwatcher
   ```

3. **Enable Passive Sniffer Service (Optional):**
   ```bash
   sudo ln -s /opt/OverwatcherPI/overwatcher-sniffer.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now overwatcher-sniffer
   ```

4. **Enable Dashboard Service:**
   *(Make sure you run Step 6 of Installation first, and set a `DASHBOARD_PASSWORD` in `.env`)*
   ```bash
   sudo cp /opt/OverwatcherPI/overwatcher-dashboard.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now overwatcher-dashboard
   ```
   The dashboard will run on port `8109` and will auto-restart on crashes.

## Telegram Commands
- `/status` — Get Raspberry Pi system health & throttling status
- `/network` — Trigger immediate local subnet sweep
- `/bluetooth` — Trigger immediate 10-second BLE discovery
- `/speedtest` — Run internet speed test
- `/traceroute <host>` — Run an on-demand traceroute
- `/attacker <ip>` — Run WHOIS OSINT lookup on an IP
- `/whitelist <mac>` — Mark a device MAC as safe
- `/monitor <ip>` — Pin a critical host for 1-minute downtime checks
- `/unmonitor <ip>` — Remove a host from ping monitor

## Known Limitations
- **BLE Tracking:** iOS/Android BLE addresses rotate roughly every 15 minutes by design. Devices never paired/bonded with this Pi cannot be reliably tracked or identified long-term — that's BLE privacy working as intended, not a bug.
- **Passive Sniffer:** On a switched (non-hub) network, the passive sniffer can only reliably see broadcast ARP/DHCP traffic and unicast traffic addressed directly to/from the Pi itself. Additionally, if the Pi is WiFi-only, running the passive sniffer continuously on the WiFi interface can affect stability on some chipsets (like the Pi's onboard Broadcom WiFi). To mitigate this, point `SNIFFER_INTERFACE` at a wired interface if one exists, or leave it blank to disable the feature entirely.
