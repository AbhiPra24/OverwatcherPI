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
from bot.broadcaster import broadcast_message
import asyncio

logger = logging.getLogger(__name__)


async def fast_sweep_job(app: Application):
    """Background job to scan network/BLE, compute diffs, and notify owner immediately."""
    logger.info("Starting fast background sweep...")
    
    from core.scan_limits import SCAN_LOCK
    if SCAN_LOCK.locked():
        logger.warning("Fast sweep skipped: scan already running.")
        return
        
    # 1. Run scans with crash safety
    try:
        async with SCAN_LOCK:
            net_devices = await network.scan()
            bt_devices = await bluetooth.scan()
    except Exception as e:
        logger.error(f"Sweep failed: {e}")
        try:
            await broadcast_message(
                app,
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
                    from core.scan_limits import get_network_load
                    current_hour = datetime.now().hour
                    is_quiet = config.quiet_hours_start <= current_hour < config.quiet_hours_end
                    if config.quiet_hours_start > config.quiet_hours_end:
                        is_quiet = current_hour >= config.quiet_hours_start or current_hour < config.quiet_hours_end
                        
                    load = get_network_load(app)
                    
                    if not is_quiet and load > config.network_jitter_threshold_ms:
                        logger.info(f"High network load ({load:.1f}ms jitter). Deferring full scan for {d.ip}.")
                        await DatabaseManager.queue_deferred_scan(d.mac, d.ip)
                        cmd = ["nmap", "-sn", d.ip]
                        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                        await asyncio.wait_for(process.communicate(), timeout=30.0)
                        open_ports.append("Scan deferred (high network load)")
                    else:
                        cmd = ["nmap", "-F", "-T4", "--open", d.ip]
                        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
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
                    await broadcast_message(
                        app,
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
            device = next((d for d in bt_devices if d.address == mac), None)
            name = device.name if device else "Unknown"
            try:
                await DatabaseManager.log_event(
                    category="bluetooth",
                    severity="warning",
                    message=f"Unknown Bluetooth device detected: {name}",
                    related_id=mac
                )
                
                should_alert = True
                if device and device.fingerprint:
                    if await DatabaseManager.was_fingerprint_seen_recently(device.fingerprint, hours=24.0):
                        logger.info(f"Suppressed BLE alert for {mac} ({name}) due to fingerprint recency match.")
                        should_alert = False
                        
                if should_alert and name and name != "Unknown":
                    should_alert = await DatabaseManager.should_alert_ble_vendor(name, config.ble_alert_cooldown_hours)
                    
                if should_alert:
                    await broadcast_message(
                        app,
                        text=f"🚨 <b>Unknown Bluetooth device detected:</b> {name} (MAC: <code>{mac}</code>)",
                        parse_mode=ParseMode.HTML
                    )
            except Exception as e:
                logger.error(f"Failed to process BLE alert: {e}")
                
    await DatabaseManager.record_scan_heartbeat("fast_sweep")
    
async def hourly_report_job(app: Application):
    """Background job to send the aggregated hourly trend report."""
    if not config.hourly_report_enabled:
        return
        
    logger.info("Starting hourly trend report generation...")
    try:
        stats = await DatabaseManager.get_hourly_stats(hours=1)
        latency_stats = app.bot_data.get("latency_stats")
        report_text = formatters.format_hourly_report(stats, latency_stats)
        
        await broadcast_message(
            app,
            text=report_text,
            parse_mode=ParseMode.HTML,
            disable_notification=True
        )
        logger.info("Hourly report sent successfully.")
        await DatabaseManager.record_scan_heartbeat("hourly_report")
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
            await broadcast_message(
                app,
                text=f"⚠️ <b>Internet Speed Alert:</b>\nDownload speed dropped to {d_mbps:.2f} Mbps",
                parse_mode=ParseMode.HTML
            )
        await DatabaseManager.record_scan_heartbeat("speedtest")
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
                    await broadcast_message(
                        app,
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
                    await broadcast_message(
                        app,
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
    await DatabaseManager.record_scan_heartbeat("ping_sweep")

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
    
    # Persist to database for dashboard trends
    await DatabaseManager.log_latency_sample("gateway", gw_stats.get("loss_percent", 100.0), gw_stats.get("jitter_ms", 0.0))
    await DatabaseManager.log_latency_sample("wan", wan_stats.get("loss_percent", 100.0), wan_stats.get("jitter_ms", 0.0))
    await DatabaseManager.record_scan_heartbeat("latency_quality")

_down_services = set()
async def service_watchdog_job(app: Application):
    from utils.metrics import get_service_status
    from bot.broadcaster import broadcast_message
    from telegram.constants import ParseMode
    import asyncio
    
    for svc in config.watched_services:
        status = await asyncio.to_thread(get_service_status, svc)
        is_active = status == "active"
        
        if not is_active:
            if svc not in _down_services:
                _down_services.add(svc)
                try:
                    await broadcast_message(
                        app,
                        text=f"🚨 <b>Service Down:</b> <code>{svc}</code> is now <b>{status}</b>!",
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass
        else:
            if svc in _down_services:
                _down_services.remove(svc)
                try:
                    await broadcast_message(
                        app,
                        text=f"✅ <b>Service Recovered:</b> <code>{svc}</code> is back online.",
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass

async def resource_health_job(app: Application):
    """Proactively monitor resource usage."""
    from utils.metrics import get_system_status
    from bot.broadcaster import broadcast_message
    from telegram.constants import ParseMode
    
    status = get_system_status()
    alerts = []
    
    # Check Temp
    if status.temp_celsius >= config.dashboard_temp_crit_c:
        if await DatabaseManager.should_alert_resource("temp_crit", config.resource_alert_cooldown_hours):
            alerts.append(f"🚨 <b>CRITICAL Temp:</b> {status.temp_celsius:.1f}°C")
    elif status.temp_celsius >= config.dashboard_temp_warn_c:
        if await DatabaseManager.should_alert_resource("temp_warn", config.resource_alert_cooldown_hours):
            alerts.append(f"⚠️ <b>Warning Temp:</b> {status.temp_celsius:.1f}°C")
            
    # Check CPU
    max_cpu = max(status.cpu_per_core) if status.cpu_per_core else 0
    if max_cpu >= config.cpu_warn_percent:
        if await DatabaseManager.should_alert_resource("cpu_warn", config.resource_alert_cooldown_hours):
            alerts.append(f"⚠️ <b>High CPU Usage:</b> {max_cpu:.1f}%")
            
    # Check RAM
    ram_pct = (status.ram_used_mb / status.ram_total_mb * 100) if status.ram_total_mb else 0
    if ram_pct >= config.ram_warn_percent:
        if await DatabaseManager.should_alert_resource("ram_warn", config.resource_alert_cooldown_hours):
            alerts.append(f"⚠️ <b>High RAM Usage:</b> {ram_pct:.1f}%")
            
    # Check Disk
    if status.disk_percent >= config.disk_warn_percent:
        if await DatabaseManager.should_alert_resource("disk_warn", config.resource_alert_cooldown_hours):
            alerts.append(f"⚠️ <b>High Disk Usage:</b> {status.disk_percent:.1f}%")
            
    # Check Throttling
    if "⚠️" in status.throttling_status and "occurred" in status.throttling_status.lower():
        if await DatabaseManager.should_alert_resource("throttling_occurred", config.resource_alert_cooldown_hours):
            alerts.append(f"⚠️ <b>System Throttling Occurred:</b> {status.throttling_status}")
    elif "⚠️" in status.throttling_status:
        if await DatabaseManager.should_alert_resource("throttling_active", config.resource_alert_cooldown_hours):
            alerts.append(f"🚨 <b>Active System Throttling:</b> {status.throttling_status}")

    if alerts:
        msg = "🔧 <b>System Resource Alert</b>\n" + "\n".join(alerts)
        try:
            await broadcast_message(app, text=msg, parse_mode=ParseMode.HTML)
        except Exception:
            pass

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
    
    # Schedule DB Retention Job (Daily at 3 AM)
    scheduler.add_job(
        db_retention_job,
        "cron",
        hour=3,
        args=[app],
        id="db_retention"
    )
    
    # Schedule Service Watchdog
    scheduler.add_job(
        service_watchdog_job,
        "interval",
        minutes=5,
        args=[app],
        id="service_watchdog"
    )
    
    # Schedule Resource Health Job
    scheduler.add_job(
        resource_health_job,
        "interval",
        minutes=5,
        args=[app],
        id="resource_health"
    )
    
    # Schedule Deferred Scan Job
    scheduler.add_job(
        deferred_scan_job,
        "interval",
        hours=1,
        args=[app],
        id="deferred_scan"
    )
    
    return scheduler

async def deferred_scan_job(app: Application):
    logger.info("Running deferred scan job...")
    current_hour = datetime.now().hour
    is_quiet = config.quiet_hours_start <= current_hour < config.quiet_hours_end
    if config.quiet_hours_start > config.quiet_hours_end:
        is_quiet = current_hour >= config.quiet_hours_start or current_hour < config.quiet_hours_end
        
    if not is_quiet:
        return
        
    scans = await DatabaseManager.get_due_deferred_scans()
    for mac, ip in scans:
        logger.info(f"Running deferred scan for {ip}...")
        open_ports = []
        try:
            cmd = ["nmap", "-sV", "-T3", "--open", ip]
            process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300.0)
            if process.returncode == 0:
                for line in stdout.decode('utf-8').splitlines():
                    if "/tcp" in line and "open" in line:
                        parts = line.split()
                        port = parts[0].split('/')[0]
                        service = parts[2] if len(parts) > 2 else "unknown"
                        open_ports.append(f"{port} ({service})")
            
            ports_str = ", ".join(open_ports) if open_ports else "None found"
            
            await broadcast_message(
                app,
                text=f"🚨 <b>Deferred Scan Results for:</b> <code>{mac}</code>\n"
                     f"📡 IP: {ip}\n"
                     f"🔓 Open Ports: {ports_str}",
                parse_mode=ParseMode.HTML
            )
            await DatabaseManager.remove_deferred_scan(mac)
        except Exception as e:
            logger.error(f"Deferred scan failed for {ip}: {e}")

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
                    await broadcast_message(
                        app,
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
                    
    await DatabaseManager.record_scan_heartbeat("port_drift")

async def identification_enrichment_job(app: Application):
    """Background job to run deep banner grabs on unknown devices with backoff."""
    logger.info("Starting identification enrichment job...")
    devices = await DatabaseManager.get_devices_needing_banner_grab()
    
    if not devices:
        return
    for d in devices:
        resolved = False
        hostname = ""
        
        # 1. Try Live OUI Lookup First
        if config.macvendors_api_enabled:
            clean_mac = d.mac.replace(":", "").replace("-", "").upper()
            if len(clean_mac) >= 6:
                prefix = clean_mac[:6]
                vendor = await oui.live_lookup_vendor(prefix)
                if vendor:
                    # Cache it and update the device directly
                    await DatabaseManager.cache_oui_entry(prefix, vendor)
                    await DatabaseManager.update_device_vendor(d.mac, vendor)
                    
                    # Log attempt but skip the heavier banner grab
                    await DatabaseManager.record_banner_grab_attempt(d.mac, True, "")
                    logger.info(f"Resolved unknown device {d.mac} via live OUI API to {vendor}")
                    await asyncio.sleep(0.5)
                    continue
            await asyncio.sleep(0.5)
                    
        # 2. Fall back to Banner Grab
        hostname = await network.grab_banner(d.ip)
        resolved = bool(hostname)
        await DatabaseManager.record_banner_grab_attempt(d.mac, resolved, hostname)
        if resolved:
            logger.info(f"Resolved unknown device {d.mac} to {hostname}")
            
    await DatabaseManager.record_scan_heartbeat("identification_enrichment")

async def db_retention_job(app: Application):
    """Daily job to prune old rows from unbounded tables (scan_history, events)."""
    if config.db_retention_days <= 0:
        return
        
    logger.info(f"Running DB retention job (keeping last {config.db_retention_days} days)...")
    try:
        db = await DatabaseManager.get_db()
        cutoff = datetime.now().timestamp() - (config.db_retention_days * 86400)
        
        await db.execute("DELETE FROM scan_history WHERE scan_time < ?", (cutoff,))
        await db.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))
        await db.commit()
        logger.info("DB retention job completed.")
        await DatabaseManager.record_scan_heartbeat("db_retention")
    except Exception as e:
        logger.error(f"DB retention job failed: {e}")
