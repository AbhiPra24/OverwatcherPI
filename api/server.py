import logging
from typing import List
from fastapi import FastAPI, HTTPException, Depends, Header
import uvicorn
from pydantic import BaseModel

from config import config
from core.database import DatabaseManager

logger = logging.getLogger(__name__)

app = FastAPI(title="OverwatcherPI API", version="1.0.0")

async def verify_token(x_api_token: str = Header(...)):
    if x_api_token != config.api_token:
        raise HTTPException(status_code=401, detail="Invalid API Token")


class DeviceResponse(BaseModel):
    mac: str
    ip: str
    vendor: str
    hostname: str

@app.get("/api/devices", response_model=List[DeviceResponse], dependencies=[Depends(verify_token)])
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
