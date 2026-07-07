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
import asyncio

logger = logging.getLogger(__name__)


async def fast_sweep_job(app: Application):
    """Background job to scan network/BLE, compute diffs, and notify owner immediately."""
    logger.info("Starting fast background sweep...")
    
    # 1. Run scans with crash safety
    try:
        net_devices = await network.scan()
        bt_devices = await bluetooth.scan()
    except Exception as e:
        logger.error(f"Sweep failed: {e}")
        try:
            await app.bot.send_message(
                chat_id=config.telegram_owner_id,
                text=f"⚠️ <b>Network Sweep Failed:</b> {e}",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        return
    
    # 2. Upsert to DB
    new_macs, gone_macs = await DatabaseManager.upsert_network_devices(net_devices)
    bt_new_macs = await DatabaseManager.upsert_bt_devices(bt_devices)
    
    # Intruder Detection - check ALL currently active unknown devices, not just newly appeared ones
    active_net = await DatabaseManager.get_active_devices()
    for d in active_net:
        if d.mac in new_macs: # Only alert when they first appear to avoid spam
            is_known = await DatabaseManager.is_known(d.mac)
            if not is_known:
                # Targeted Scan
                open_ports = []
                try:
                    cmd = ["nmap", "-sV", "-p-", "-T4", "--open", d.ip]
                    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                    stdout, stderr = await process.communicate()
                    if process.returncode == 0:
                        for line in stdout.decode('utf-8').splitlines():
                            if "/tcp" in line and "open" in line:
                                parts = line.split()
                                port = parts[0].split('/')[0]
                                service = parts[2] if len(parts) > 2 else "unknown"
                                open_ports.append(f"{port} ({service})")
                except Exception as e:
                    logger.error(f"Targeted scan failed: {e}")
                
                ports_str = ", ".join(open_ports) if open_ports else "None found"
                try:
                    await app.bot.send_message(
                        chat_id=config.telegram_owner_id,
                        text=f"🚨 <b>Unknown device joined the network:</b> {d.vendor} (MAC: <code>{d.mac}</code>)\n"
                             f"📡 IP: {d.ip}\n"
                             f"🔓 Open Ports: {ports_str}",
                        parse_mode=ParseMode.HTML
                    )
                    await DatabaseManager.log_event(
                        category="network",
                        severity="warning",
                        message=f"Unknown device joined the network: {d.vendor} (IP: {d.ip}, Ports: {ports_str})",
                        related_id=d.mac
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
                await DatabaseManager.log_event(
                    category="bluetooth",
                    severity="warning",
                    message=f"Unknown Bluetooth device detected: {name}",
                    related_id=mac
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
        latency_stats = app.bot_data.get("latency_stats")
        report_text = formatters.format_hourly_report(stats, latency_stats)
        
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
        d_mbps = await asyncio.to_thread(run_st)
        if d_mbps < 50.0:  # arbitrary threshold
            await app.bot.send_message(
                chat_id=config.telegram_owner_id,
                text=f"⚠️ <b>Internet Speed Alert:</b>\nDownload speed dropped to {d_mbps:.2f} Mbps",
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Scheduled speedtest failed: {e}")


_down_hosts = set()
async def ping_sweep_job(app: Application):
    hosts = await DatabaseManager.get_monitored_hosts()
    if not hosts:
        return
        
    from core.ping_utils import ping_host
    for ip in hosts:
        stats = await ping_host(ip, count=1)
        
        if stats["loss_percent"] == 100.0:
            if ip not in _down_hosts:
                _down_hosts.add(ip)
                try:
                    await app.bot.send_message(
                        chat_id=config.telegram_owner_id,
                        text=f"⚠️ <b>Critical Host Offline:</b> <code>{ip}</code> is not responding to ping!",
                        parse_mode=ParseMode.HTML
                    )
                    await DatabaseManager.log_event(
                        category="network",
                        severity="high",
                        message=f"Critical Host Offline: {ip} is not responding to ping!",
                        related_id=ip
                    )
                except Exception:
                    pass
        else:
            if ip in _down_hosts:
                _down_hosts.remove(ip)
                try:
                    await app.bot.send_message(
                        chat_id=config.telegram_owner_id,
                        text=f"✅ <b>Host Recovered:</b> <code>{ip}</code> is back online.",
                        parse_mode=ParseMode.HTML
                    )
                    await DatabaseManager.log_event(
                        category="network",
                        severity="info",
                        message=f"Host Recovered: {ip} is back online.",
                        related_id=ip
                    )
                except Exception:
                    pass

async def latency_quality_job(app: Application):
    """Ping gateway and external host to check quality."""
    from core.ping_utils import ping_host
    logger.info("Running latency quality job...")
    
    gw_stats = await ping_host(config.gateway_ip, count=4)
    wan_stats = await ping_host("1.1.1.1", count=4)
    
    if "latency_stats" not in app.bot_data:
        app.bot_data["latency_stats"] = {}
        
    app.bot_data["latency_stats"]["gateway"] = gw_stats
    app.bot_data["latency_stats"]["wan"] = wan_stats

def setup_scheduler(app: Application) -> AsyncIOScheduler:
    """Initialize APScheduler with jobs."""
    scheduler = AsyncIOScheduler()
    
    # Schedule fast sweep
    scheduler.add_job(
        fast_sweep_job,
        "interval",
        minutes=config.sweep_interval_minutes,
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
    
    # Schedule speedtest
    scheduler.add_job(
        scheduled_speedtest_job,
        "interval",
        hours=config.speedtest_interval_hours,
        args=[app],
        id="scheduled_speedtest"
    )

    # Schedule Ping Monitor (every 1 minute)
    scheduler.add_job(
        ping_sweep_job,
        "interval",
        minutes=1,
        args=[app],
        id="ping_sweep"
    )
    
    # Schedule Latency Quality Job (every 15 min)
    scheduler.add_job(
        latency_quality_job,
        "interval",
        minutes=15,
        args=[app],
        id="latency_quality"
    )
    
    # Schedule Port Drift Job (Daily at 2 AM)
    scheduler.add_job(
        port_drift_job,
        "cron",
        hour=2,
        args=[app],
        id="port_drift"
    )
    
    # Schedule Identification Enrichment (Every 2 hours)
    scheduler.add_job(
        identification_enrichment_job,
        "interval",
        hours=2,
        args=[app],
        id="identification_enrichment"
    )
    
    return scheduler

async def port_drift_job(app: Application):
    """Daily job to track open ports on known active devices."""
    logger.info("Starting port drift job...")
    active_net = await DatabaseManager.get_active_devices()
    
    # Basic daily staggering: hash(mac) % 7 == current weekday
    # This means ~1/7th of devices are scanned per day.
    today_bucket = datetime.now().weekday()
    
    devices_to_scan = [
        d for d in active_net 
        if hash(d.mac) % 7 == today_bucket
    ]
    
    if not devices_to_scan:
        return
        
    logger.info(f"Port drift job: Scanning {len(devices_to_scan)} devices in today's bucket.")
    
    for d in devices_to_scan:
        ports = await network.scan_ports(d.ip)
        new_ports = await DatabaseManager.upsert_device_ports(d.mac, ports)
        
        if new_ports:
            is_known = await DatabaseManager.is_known(d.mac)
            if is_known:
                # Alert only if it's a known device that opened a new port
                ports_str = ", ".join([f"{p['port']} ({p['service']})" for p in new_ports])
                try:
                    await app.bot.send_message(
                        chat_id=config.telegram_owner_id,
                        text=f"🚨 <b>Port Drift Alert:</b> <code>{d.mac}</code> ({d.hostname or d.vendor}) just opened new port(s): {ports_str} — wasn't open last scan.",
                        parse_mode=ParseMode.HTML
                    )
                    await DatabaseManager.log_event(
                        category="network",
                        severity="warning",
                        message=f"Port Drift Alert: {d.hostname or d.vendor} opened new port(s): {ports_str}",
                        related_id=d.mac
                    )
                except Exception as e:
                    logger.error(f"Failed to send port drift alert for {d.mac}: {e}")

async def identification_enrichment_job(app: Application):
    """Background job to run deep banner grabs on unknown devices with backoff."""
    logger.info("Starting identification enrichment job...")
    devices = await DatabaseManager.get_devices_needing_banner_grab()
    
    if not devices:
        return
        
    for d in devices:
        hostname = await network.grab_banner(d.ip)
        resolved = bool(hostname)
        await DatabaseManager.record_banner_grab_attempt(d.mac, resolved, hostname)
        if resolved:
            logger.info(f"Resolved unknown device {d.mac} to {hostname}")
