import logging
from typing import List
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
import asyncio
from pydantic import BaseModel

from config import config
from core.database import DatabaseManager, NetworkDevice

logger = logging.getLogger(__name__)

app = FastAPI(title="OverwatcherPI API", version="1.0.0")
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != config.api_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

class DeviceResponse(BaseModel):
    mac: str
    ip: str
    vendor: str
    hostname: str

@app.get("/api/devices", response_model=List[DeviceResponse])
async def get_active_devices(token: str = Depends(verify_token)):
    devices = await DatabaseManager.get_active_devices()
    return [{"mac": d.mac, "ip": d.ip, "vendor": d.vendor, "hostname": d.hostname} for d in devices]

async def start_api_server():
    server_config = uvicorn.Config(app, host="0.0.0.0", port=config.api_port, log_level="warning")
    server = uvicorn.Server(server_config)
    logger.info(f"Starting FastAPI server on port {config.api_port}")
    await server.serve()
