# OverwatcherPI — Docker Deployment Guide

## Architecture

| Service | Network Mode | Why |
|---------|-------------|-----|
| `bot` | `host` | nmap ARP discovery + BlueZ/D-Bus BLE access |
| `sniffer` | `host` | Must see real LAN ARP/DHCP broadcast traffic |
| `dashboard` | default bridge | Published to `127.0.0.1:8501` only, reached via Caddy on host network |
| `caddy` | `host` | Single public entry point on port 8109 |

### API endpoint (`/api/*`)

The FastAPI server (`uvicorn`) inside `overwatcher-bot` binds **`127.0.0.1:8000` only** — not `0.0.0.0`.  
Because `bot` uses `network_mode: host`, `127.0.0.1` is the Pi's loopback — it is **not directly reachable from the LAN**.  
External access goes through Caddy: `http://<pi-ip>:8109/api/devices` (protected by the same basicauth layer as the dashboard) + Bearer token.

> **Never change the uvicorn bind to `0.0.0.0`** without also adding firewall rules — doing so would expose the API directly on the LAN with only the Bearer token as protection.

### Container Privileges Justification

OverwatcherPI requires several container privileges to perform network and hardware monitoring. We operate on a principle of least privilege, mapping only what is absolutely necessary:

- **`network_mode: host`**: Required by the `bot` for nmap/ARP host discovery (needs to inject and read raw frames on the host's subnet) and by the `sniffer` to see real LAN ARP/DHCP broadcast traffic (bridged networking isolates this traffic).
- **`cap_add: NET_RAW, NET_ADMIN`**: Required by both the `bot` (for raw packet injection during ARP/ping sweeps via nmap) and the `sniffer` (for Scapy passive sniffing via raw sockets).
- **`apparmor: unconfined` & DBus mounts (`/var/run/dbus`)**: Required for BLE discovery. Even with the host's `/var/run/dbus` socket mapped in, Docker's default AppArmor profile aggressively restricts D-Bus communications. When `bleak` sends an `AddMatch` method call to the host's BlueZ daemon, AppArmor blocks it without `unconfined`.
- **`vcio` device & `vcgencmd` access**: The `bot` maps `/dev/vcio` and `/usr/bin/vcgencmd:ro` to monitor Raspberry Pi hardware health (CPU throttling, SoC temperature, voltage issues).

**Mitigations:**
- The `bot` Dockerfile drops root privileges and runs as a dedicated non-root user (`overwatcher`, uid 1000). 
- Capabilities like `NET_RAW` allow packet sniffing, but the application limits this strictly to internal tooling. 

> **Security Note:** Since your `.env` contains sensitive tokens and passwords, it must be locked down on the host. Run `chmod 600 .env` to prevent unauthorized local read access.

## Pre-flight Checklist

1. Install Docker + Docker Compose plugin:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER && newgrp docker
   ```

2. Ensure `SNIFFER_INTERFACE` is set in `.env` to your LAN interface (e.g. `eth0`).

3. Regenerate the Caddy password hash for Docker:
   ```bash
   docker run --rm caddy:2-alpine caddy hash-password
   ```
   Update `dashboard/Caddyfile` with the new hash.

## Migration from systemd

```bash
# 1. Backup data
cp -r data/ data.bak/ && cp -r logs/ logs.bak/ && cp .env .env.bak

# 2. Stop and disable the old systemd stack
sudo ./overwatcher.sh stop
sudo systemctl disable overwatcher overwatcher-sniffer overwatcher-dashboard overwatcher-caddy

# 3. Build and start containers
docker compose build
docker compose up -d

# 4. Monitor startup
docker compose logs -f
```

## Verifying Parity

After startup, confirm:
- [ ] Boot notification arrives in Telegram
- [ ] `/status` returns real data
- [ ] `/network` shows ~same device count as pre-migration
- [ ] `/bluetooth` shows BLE devices (D-Bus passthrough validation)
- [ ] Dashboard loads at `http://<pi-ip>:8109/` with Caddy credentials
- [ ] `docker compose ps` shows all 4 services as `healthy`

> **BLE Risk**: D-Bus passthrough (`/var/run/dbus:/var/run/dbus`) is the
> highest-risk item in this migration. If BLE scanning stops working,
> run the bot temporarily outside Docker (`python main.py` in a tmux/screen)
> while keeping the sniffer/dashboard/caddy containerised — a partial
> migration is better than a broken BLE feature.

## Useful Commands

```bash
docker compose logs -f bot          # Follow bot logs
docker compose logs -f sniffer      # Follow sniffer logs
docker compose restart bot          # Restart single service
docker compose down && docker compose up -d   # Full restart
docker compose exec bot python -c "from core.database import DatabaseManager; import asyncio; print(asyncio.run(DatabaseManager.get_active_devices()))"
```

## Rollback

If something goes wrong:
```bash
docker compose down
sudo systemctl enable --now overwatcher overwatcher-sniffer overwatcher-dashboard overwatcher-caddy
```

## Restore from Backup

OverwatcherPI creates automated daily DB backups in `data/backups/`. To restore a backup:

```bash
# 1. Stop the bot so it drops the database lock
docker compose stop bot

# 2. Rename the current database (just in case)
mv data/netmon.db data/netmon.db.corrupt

# 3. Copy the chosen backup into place
cp data/backups/netmon-YYYYMMDD.db data/netmon.db

# 4. Start the bot again
docker compose start bot
```
