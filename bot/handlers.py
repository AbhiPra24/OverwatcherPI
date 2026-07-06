from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import asyncio
import speedtest

from bot.middleware import auth_required
from bot import formatters
from utils import metrics
from utils.osint import get_ip_info
from scanners import network, bluetooth
from core.database import DatabaseManager

@auth_required
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🛡 <b>OverwatcherPI</b> is online.\n"
        "Commands:\n"
        "/status - Hardware diagnostics\n"
        "/network - Scan local subnet\n"
        "/bluetooth - Scan nearby BLE devices\n"
        "/speedtest - Check internet speed\n"
        "/whitelist &lt;mac&gt; - Mark a device as safe\n"
        "/attacker &lt;ip&gt; - WHOIS OSINT lookup\n"
        "/monitor &lt;ip&gt; - Pin host for ping monitor\n"
        "/unmonitor &lt;ip&gt; - Remove host from ping monitor"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


@auth_required
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = metrics.get_system_status()
    await update.message.reply_text(formatters.format_status(status), parse_mode=ParseMode.HTML)


@auth_required
async def network_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 <i>Scanning local network...</i>", parse_mode=ParseMode.HTML)
    
    try:
        devices = await network.scan()
        new_macs, _ = await DatabaseManager.upsert_network_devices(devices)
        
        await msg.edit_text(formatters.format_network(devices, new_macs), parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f"❌ <b>Scan failed:</b> {str(e)}", parse_mode=ParseMode.HTML)


@auth_required
async def bluetooth_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔷 <i>Scanning for Bluetooth LE devices (10s)...</i>", parse_mode=ParseMode.HTML)
    
    try:
        devices = await bluetooth.scan()
        await DatabaseManager.upsert_bt_devices(devices)
        
        await msg.edit_text(formatters.format_bluetooth(devices), parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f"❌ <b>Scan failed:</b> {str(e)}", parse_mode=ParseMode.HTML)

@auth_required
async def speedtest_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🚀 <i>Running Speedtest... (this may take a minute)</i>", parse_mode=ParseMode.HTML)
    
    def run_st():
        st = speedtest.Speedtest()
        st.get_best_server()
        d = st.download()
        u = st.upload()
        p = st.results.ping
        return d, u, p
        
    try:
        d, u, p = await asyncio.to_thread(run_st)
        d_mbps = d / 1_000_000
        u_mbps = u / 1_000_000
        res = f"🚀 <b>Speedtest Results:</b>\n⬇️ Download: {d_mbps:.2f} Mbps\n⬆️ Upload: {u_mbps:.2f} Mbps\n🏓 Ping: {p:.1f} ms"
    except Exception as e:
        res = f"❌ Speedtest failed: {e}"
        
    await msg.edit_text(res, parse_mode=ParseMode.HTML)

@auth_required
async def whitelist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a MAC address: /whitelist 00:11:22:33:44:55")
        return
    mac = context.args[0].upper()
    success = await DatabaseManager.mark_known(mac)
    if success:
        await update.message.reply_text(f"✅ Whitelisted MAC: {mac}")
    else:
        await update.message.reply_text(f"⚠️ MAC {mac} not found in database.")

@auth_required
async def attacker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide an IP: /attacker 8.8.8.8")
        return
    ip = context.args[0]
    await update.message.reply_text(f"🔍 <i>Looking up OSINT for {ip}...</i>", parse_mode=ParseMode.HTML)
    info = await get_ip_info(ip)
    await update.message.reply_text(f"🌐 <b>OSINT for <code>{ip}</code>:</b>\n<pre>{info}</pre>", parse_mode=ParseMode.HTML)

@auth_required
async def monitor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide an IP or hostname: /monitor 192.168.1.1")
        return
    ip = context.args[0]
    await DatabaseManager.add_monitored_host(ip)
    await update.message.reply_text(f"✅ Now monitoring {ip} for downtime.")

@auth_required
async def unmonitor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide an IP or hostname: /unmonitor 192.168.1.1")
        return
    ip = context.args[0]
    success = await DatabaseManager.remove_monitored_host(ip)
    if success:
        await update.message.reply_text(f"✅ Stopped monitoring {ip}.")
    else:
        await update.message.reply_text(f"⚠️ {ip} was not being monitored.")
