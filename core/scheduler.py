import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application
from telegram.constants import ParseMode

from config import config
from core.database import DatabaseManager
from core import oui
from scanners import network, bluetooth
from bot import formatters

logger = logging.getLogger(__name__)


async def hourly_sweep_job(app: Application):
    """Background job to scan network/BLE, compute diffs, and notify owner."""
    logger.info("Starting hourly background sweep...")
    
    # 1. Run scans
    net_devices = await network.scan()
    bt_devices = await bluetooth.scan()
    
    # 2. Upsert to DB
    new_macs, gone_macs = await DatabaseManager.upsert_network_devices(net_devices)
    await DatabaseManager.upsert_bt_devices(bt_devices)
    
    # 3. If hourly reports enabled, send telemetry to owner
    if config.hourly_report_enabled:
        stats = await DatabaseManager.get_hourly_stats(hours=1)
        
        # Override new/gone with exact diff from just now
        stats.new_macs = list(new_macs)
        stats.gone_macs = list(gone_macs)
        
        report_text = formatters.format_hourly_report(stats)
        
        try:
            await app.bot.send_message(
                chat_id=config.telegram_owner_id,
                text=report_text,
                parse_mode=ParseMode.HTML
            )
            logger.info("Hourly report sent successfully.")
        except Exception as e:
            logger.error(f"Failed to send hourly report: {e}")


def setup_scheduler(app: Application) -> AsyncIOScheduler:
    """Initialize APScheduler with jobs."""
    scheduler = AsyncIOScheduler()
    
    # Schedule hourly sweep (starts 1 hour from now)
    scheduler.add_job(
        hourly_sweep_job,
        "interval",
        hours=1,
        args=[app],
        id="hourly_sweep",
        next_run_time=datetime.now() + timedelta(hours=1)
    )
    
    # Schedule OUI refresh (weekly)
    scheduler.add_job(
        oui.load_or_refresh,
        "interval",
        hours=168,
        args=[True],  # force=True
        id="oui_refresh"
    )
    
    return scheduler
