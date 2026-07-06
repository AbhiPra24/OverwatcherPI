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


async def fast_sweep_job(app: Application):
    """Background job to scan network/BLE, compute diffs, and notify owner immediately."""
    logger.info("Starting fast background sweep...")
    
    # 1. Run scans
    net_devices = await network.scan()
    bt_devices = await bluetooth.scan()
    
    # 2. Upsert to DB
    new_macs, gone_macs = await DatabaseManager.upsert_network_devices(net_devices)
    bt_new_macs = await DatabaseManager.upsert_bt_devices(bt_devices)
    
    # Intruder Detection
    for mac in new_macs:
        is_known = await DatabaseManager.is_known(mac)
        if not is_known:
            vendor = next((d.vendor for d in net_devices if d.mac == mac), "Unknown")
            try:
                await app.bot.send_message(
                    chat_id=config.telegram_owner_id,
                    text=f"🚨 <b>Unknown device joined the network:</b> {vendor} (MAC: <code>{mac}</code>)",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")
                
    for mac in bt_new_macs:
        is_known = await DatabaseManager.is_known(mac)
        if not is_known:
            name = next((d.name for d in bt_devices if d.address == mac), "Unknown")
            try:
                await app.bot.send_message(
                    chat_id=config.telegram_owner_id,
                    text=f"🚨 <b>Unknown Bluetooth device detected:</b> {name} (MAC: <code>{mac}</code>)",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")
    
async def hourly_report_job(app: Application):
    """Background job to send the aggregated hourly trend report."""
    if not config.hourly_report_enabled:
        return
        
    logger.info("Starting hourly trend report generation...")
    try:
        stats = await DatabaseManager.get_hourly_stats(hours=1)
        report_text = formatters.format_hourly_report(stats)
        
        await app.bot.send_message(
            chat_id=config.telegram_owner_id,
            text=report_text,
            parse_mode=ParseMode.HTML
        )
        logger.info("Hourly report sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send hourly report: {e}")

async def scheduled_speedtest_job(app: Application):
    logger.info("Running scheduled speedtest...")
    def run_st():
        import speedtest
        st = speedtest.Speedtest()
        st.get_best_server()
        d = st.download()
        return d / 1_000_000
        
    try:
        import asyncio
        d_mbps = await asyncio.to_thread(run_st)
        if d_mbps < 50.0:  # arbitrary threshold
            await app.bot.send_message(
                chat_id=config.telegram_owner_id,
                text=f"⚠️ <b>Internet Speed Alert:</b>\nDownload speed dropped to {d_mbps:.2f} Mbps",
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Scheduled speedtest failed: {e}")


def setup_scheduler(app: Application) -> AsyncIOScheduler:
    """Initialize APScheduler with jobs."""
    scheduler = AsyncIOScheduler()
    
    # Schedule fast sweep (every 5 mins)
    scheduler.add_job(
        fast_sweep_job,
        "interval",
        minutes=5,
        args=[app],
        id="fast_sweep",
        next_run_time=datetime.now() + timedelta(minutes=1)
    )
    
    # Schedule hourly report (every 1 hour)
    scheduler.add_job(
        hourly_report_job,
        "interval",
        hours=1,
        args=[app],
        id="hourly_report",
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
    
    # Schedule speedtest every 3 hours
    scheduler.add_job(
        scheduled_speedtest_job,
        "interval",
        hours=3,
        args=[app],
        id="scheduled_speedtest"
    )
    
    return scheduler
