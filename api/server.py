import logging
from typing import List
from fastapi import FastAPI, HTTPException
import uvicorn
import asyncio
from pydantic import BaseModel

from config import config
from core.database import DatabaseManager, NetworkDevice

logger = logging.getLogger(__name__)

app = FastAPI(title="OverwatcherPI API", version="1.0.0")

class DeviceResponse(BaseModel):
    mac: str
    ip: str
    vendor: str
    hostname: str

@app.get("/api/devices", response_model=List[DeviceResponse])
async def get_active_devices():
    devices = await DatabaseManager.get_active_devices()
    return [{"mac": d.mac, "ip": d.ip, "vendor": d.vendor, "hostname": d.hostname} for d in devices]

async def start_api_server():
    # Bind to 127.0.0.1 only — the bot container runs network_mode:host so
    # 0.0.0.0 would expose port 8000 directly on the LAN interface with no
    # reverse-proxy layer.  Caddy proxies /api/* → 127.0.0.1:8000 instead.
    server_config = uvicorn.Config(app, host="127.0.0.1", port=config.api_port, log_level="warning")
    server = uvicorn.Server(server_config)
    logger.info(f"Starting FastAPI server on 127.0.0.1:{config.api_port} (Caddy-proxied)")
    await server.serve()
