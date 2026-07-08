# OverwatcherPI - Project Rules & Context

Welcome to the OverwatcherPI project! This file serves as the core initialization context for Google Antigravity (AGY) sessions.

## Project Overview
OverwatcherPI is a home network security and intelligence platform designed to run on a Raspberry Pi (or similar Linux host) using Docker. It scans the local network (ARP/Nmap) and Bluetooth Low Energy (BLE) environments to detect new devices, track presence, and alert the user via a Telegram Bot. It also features a Streamlit-based dashboard for visualizing data.

## Technology Stack
- **Language:** Python 3.12
- **Bot Framework:** python-telegram-bot (v20+)
- **API / Web:** FastAPI (Caddy reverse proxy)
- **Dashboard:** Streamlit
- **Database:** SQLite (async via `aiosqlite`)
- **Scanners:** `nmap`, `scapy`, `bleak` (Bluetooth), `speedtest-cli`, `traceroute`, `sherlock-project`
- **Containerization:** Docker & Docker Compose

## Architecture & Directory Structure
- `main.py`: The main entrypoint. Starts FastAPI, APScheduler, and the Telegram bot.
- `bot/`: Contains the Telegram bot logic. `app.py` registers commands, `handlers.py` contains the business logic for each slash command, and `formatters.py` handles markdown message formatting.
- `core/`: Core services. Includes `database.py` (SQLite operations), `scheduler.py` (APScheduler background tasks), `job_queue.py` (long-running subprocess queue), and `threat_intel.py`.
- `scanners/`: Scanning modules (`network.py` for IP/MAC discovery, `bluetooth.py` for BLE discovery).
- `dashboard/`: Streamlit dashboard views.
- `utils/`: Helper functions like `metrics.py` (system health) and `osint.py` (IP lookups).
- `logs/` and `data/`: Persistent Docker volumes for application logs and the SQLite database (`overwatcher.db`).

## Docker Setup & Capabilities
- **Networking:** Must use `network_mode: "host"` to perform accurate ARP scans and capture raw packets.
- **Capabilities:** The container requires `cap_add: [NET_RAW, NET_ADMIN]` for `nmap` and `scapy`.
- **Bluetooth:** The host's D-Bus is mounted (`/var/run/dbus:/var/run/dbus`) to allow `bleak` to access the BlueZ adapter from within the container.
- **Entrypoint:** The `overwatcher-bot` container runs as a non-root user (`overwatcher`) but has `setcap` configured for necessary binaries.

## Common Developer Commands
- **Rebuild and Start:** `docker compose up -d --build`
- **View Logs:** `docker compose logs -f bot` or `tail -f logs/overwatcher.log`
- **Access Container:** `docker exec -it overwatcher-bot bash`
- **Apply DB Migrations:** Handled automatically on startup in `core/database.py`.

## AGY Guidelines for this Project
1. **Async Python:** This project heavily relies on `asyncio`. Ensure database calls (`aiosqlite`), API requests (`aiohttp`), and Telegram bot handlers are properly awaited.
2. **Docker Isolation:** Remember that the app runs inside a Docker container. Any new system dependencies (like `traceroute` or `nmap`) must be explicitly added to the `Dockerfile`.
3. **Bot Handlers:** When adding new Telegram commands, always:
   - Implement the handler in `bot/handlers.py` with the `@auth_required` decorator.
   - Register the command in `bot/app.py`.
   - Add it to the `/help` string in `handlers.py`.
4. **Long-running Tasks:** Do not block the main Telegram event loop. For tasks taking longer than 1-2 seconds (like `nmap_full` or `sherlock`), use the `JobQueue.add_job()` framework to run them asynchronously.
