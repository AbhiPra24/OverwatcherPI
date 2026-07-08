import asyncio
import logging
from telegram.ext import Application
from config import config
from core.database import DatabaseManager
from bot.broadcaster import broadcast_message

logger = logging.getLogger(__name__)

async def handle_honeypot_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, app: Application, port: int):
    peername = writer.get_extra_info("peername")
    src_ip = peername[0] if peername else "Unknown"
    
    logger.warning(f"Honeypot hit on port {port} from {src_ip}")
    
    if await DatabaseManager.should_alert_honeypot(src_ip, cooldown_seconds=300):
        alert_msg = f"🚨 <b>HONEYPOT TRIGGERED</b>\n\nUnauthorized connection attempt detected on port <b>{port}</b> from IP <b>{src_ip}</b>."
        await broadcast_message(app, alert_msg)
        await DatabaseManager.log_event(
            category="security",
            severity="critical",
            message=f"Honeypot port {port} hit by {src_ip}"
        )
    
    try:
        writer.write(b"\r\n")
        await writer.drain()
    except Exception:
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

async def start_honeypots(app: Application):
    for port in config.honeypot_ports:
        try:
            server = await asyncio.start_server(
                lambda r, w, p=port: handle_honeypot_connection(r, w, app, p),
                "0.0.0.0", 
                port
            )
            logger.info(f"Started honeypot listener on 0.0.0.0:{port}")
        except Exception as e:
            logger.error(f"Failed to start honeypot on port {port}: {e}")
