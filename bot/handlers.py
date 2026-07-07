from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import asyncio
import speedtest
import re

from bot.middleware import auth_required
from bot import formatters
from utils import metrics
from utils.osint import get_ip_info
from scanners import network, bluetooth
from core.database import DatabaseManager
from core.scan_limits import SCAN_LOCK
import time

def check_cooldown(context: ContextTypes.DEFAULT_TYPE, command_name: str, cooldown_s: int = 30) -> float:
    now = time.time()
    last_run = context.user_data.get(f"last_{command_name}", 0)
    if now - last_run < cooldown_s:
        return cooldown_s - (now - last_run)
    context.user_data[f"last_{command_name}"] = now
    return 0.0

@auth_required
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🛡 <b>OverwatcherPI</b> is online.\n"
        "Commands:\n"
        "/status - Hardware diagnostics\n"
        "/network - Scan local subnet\n"
        "/bluetooth - Scan nearby BLE devices\n"
        "/speedtest - Check internet speed\n"
        "/traceroute &lt;host&gt; - Run traceroute to host\n"
        "/whitelist &lt;mac&gt; - Mark a device as safe\n"
        "/attacker &lt;ip&gt; - WHOIS OSINT lookup\n"
        "/monitor &lt;ip&gt; - Pin host for ping monitor\n"
        "/unmonitor &lt;ip&gt; - Remove host from ping monitor\n"
        "/dns &lt;ip&gt; - View recent DNS queries for host\n"
        "/name &lt;mac&gt; &lt;name&gt; - Assign friendly name to device"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


@auth_required
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = metrics.get_system_status()
    await update.message.reply_text(formatters.format_status(status), parse_mode=ParseMode.HTML)


@auth_required
async def network_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cd = check_cooldown(context, "network")
    if cd > 0:
        await update.message.reply_text(f"⏳ Please wait {int(cd)}s before using /network again.")
        return
        
    if SCAN_LOCK.locked():
        await update.message.reply_text("⏳ A scan is already running, try again shortly.")
        return
        
    msg = await update.message.reply_text("🔍 <i>Scanning local network...</i>", parse_mode=ParseMode.HTML)
    
    try:
        async with SCAN_LOCK:
            devices = await network.scan()
        new_macs, _ = await DatabaseManager.upsert_network_devices(devices)
        
        text = formatters.format_network(devices, new_macs)
        text = formatters.truncate_for_telegram(text)
        
        keyboard = []
        for dev in devices:
            if dev.mac in new_macs or not await DatabaseManager.is_known(dev.mac):
                keyboard.append([
                    InlineKeyboardButton(f"Whitelist {dev.ip}", callback_data=f"whitelist:{dev.mac}"),
                    InlineKeyboardButton(f"OSINT {dev.ip}", callback_data=f"attacker:{dev.ip}")
                ])
        
        reply_markup = InlineKeyboardMarkup(keyboard[:50]) if keyboard else None
        await msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    except Exception as e:
        await msg.edit_text(f"❌ <b>Scan failed:</b> {str(e)}", parse_mode=ParseMode.HTML)


@auth_required
async def bluetooth_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cd = check_cooldown(context, "bluetooth")
    if cd > 0:
        await update.message.reply_text(f"⏳ Please wait {int(cd)}s before using /bluetooth again.")
        return
        
    if SCAN_LOCK.locked():
        await update.message.reply_text("⏳ A scan is already running, try again shortly.")
        return
        
    msg = await update.message.reply_text("🔷 <i>Scanning for Bluetooth LE devices (10s)...</i>", parse_mode=ParseMode.HTML)
    
    try:
        async with SCAN_LOCK:
            devices = await bluetooth.scan()
        await DatabaseManager.upsert_bt_devices(devices)
        
        text = formatters.format_bluetooth(devices)
        text = formatters.truncate_for_telegram(text)
        
        await msg.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f"❌ <b>Scan failed:</b> {str(e)}", parse_mode=ParseMode.HTML)

@auth_required
async def speedtest_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cd = check_cooldown(context, "speedtest", cooldown_s=60)
    if cd > 0:
        await update.message.reply_text(f"⏳ Please wait {int(cd)}s before using /speedtest again.")
        return
        
    msg = await update.message.reply_text("🚀 <i>Running Speedtest (takes ~30s)...</i>", parse_mode=ParseMode.HTML)
    
    def run_st():
        st = speedtest.Speedtest()
        # get_best_server() sometimes picks a geographically distant server
        # that times out, returning ping=1,800,000 ms (its internal 30-min
        # timeout). Instead: load all servers, sort by distance, probe the
        # 5 closest, and pick the one with the lowest real latency.
        st.get_servers()
        st.get_best_server(st.get_servers())
        server = st.get_best_server()
        ping = server.get("latency", 0)
        # Sanity check: if latency is absurdly high (>5000 ms), the server
        # timed out — try the closest server by distance instead.
        if ping > 5000:
            servers_by_dist = sorted(
                [s for sublist in st.servers.values() for s in sublist],
                key=lambda s: s.get("d", 999999)
            )
            for candidate in servers_by_dist[:10]:
                try:
                    candidate_ping = st.get_best_server([candidate]).get("latency", 99999)
                    if candidate_ping < ping:
                        ping = candidate_ping
                        break
                except Exception:
                    continue
        
        d = st.download()
        u = st.upload()
        server_info = st.results.server
        return d, u, ping, server_info
        
    try:
        d, u, p, server = await asyncio.to_thread(run_st)
        d_mbps = d / 1_000_000
        u_mbps = u / 1_000_000
        ping_str = f"{p:.1f} ms" if p < 5000 else "N/A (server timeout)"
        res = (
            f"🚀 <b>Speedtest Results:</b>\n"
            f"⬇️ Download: {d_mbps:.2f} Mbps\n"
            f"⬆️ Upload: {u_mbps:.2f} Mbps\n"
            f"🏓 Ping: {ping_str}\n"
            f"🌐 Server: {server.get('sponsor','?')} — {server.get('name','?')}, {server.get('country','?')}"
        )
    except Exception as e:
        res = f"❌ Speedtest failed: {e}"
        
    await msg.edit_text(res, parse_mode=ParseMode.HTML)

@auth_required
async def whitelist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a MAC address: /whitelist 00:11:22:33:44:55")
        return
    mac = context.args[0].upper()
    if not re.match(r"^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$", mac):
        await update.message.reply_text("❌ That doesn't look like a valid MAC address.")
        return
        
    success = await DatabaseManager.mark_known(mac)
    if success:
        await update.message.reply_text(f"✅ Whitelisted MAC: {mac}")
    else:
        await update.message.reply_text(f"⚠️ MAC {mac} not found in database.")

@auth_required
async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /name <mac> <friendly name>")
        return
    mac = context.args[0].upper()
    if not re.match(r"^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$", mac):
        await update.message.reply_text("❌ That doesn't look like a valid MAC address.")
        return
        
    name = " ".join(context.args[1:])
    success = await DatabaseManager.set_device_name(mac, name)
    if success:
        await update.message.reply_text(f"✅ Set name for {mac} to '{name}'")
    else:
        await update.message.reply_text(f"⚠️ MAC {mac} not found in database.")

@auth_required
async def attacker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide an IP: /attacker 8.8.8.8")
        return
    ip = context.args[0]
    if not re.match(r"^[a-zA-Z0-9.-]+$", ip):
        await update.message.reply_text("❌ That doesn't look like a valid IP address.")
        return
        
    await update.message.reply_text(f"🔍 <i>Looking up OSINT for {ip}...</i>", parse_mode=ParseMode.HTML)
    info = await get_ip_info(ip)
    await update.message.reply_text(f"🌐 <b>OSINT for <code>{ip}</code>:</b>\n<pre>{formatters.escape(info)}</pre>", parse_mode=ParseMode.HTML)

@auth_required
async def monitor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide an IP or hostname: /monitor 192.168.1.1")
        return
    ip = context.args[0]
    if not re.match(r"^[a-zA-Z0-9.-]+$", ip):
        await update.message.reply_text("❌ That doesn't look like a valid IP or hostname.")
        return
        
    await DatabaseManager.add_monitored_host(ip)
    await update.message.reply_text(f"✅ Now monitoring {ip} for downtime.")

@auth_required
async def unmonitor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide an IP or hostname: /unmonitor 192.168.1.1")
        return
    ip = context.args[0]
    if not re.match(r"^[a-zA-Z0-9.-]+$", ip):
        await update.message.reply_text("❌ That doesn't look like a valid IP or hostname.")
        return
        
    success = await DatabaseManager.remove_monitored_host(ip)
    if success:
        await update.message.reply_text(f"✅ Stopped monitoring {ip}.")
    else:
        await update.message.reply_text(f"⚠️ {ip} was not being monitored.")

@auth_required
async def dns_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide an IP: /dns 192.168.1.100")
        return
        
    target = context.args[0]
    if not re.match(r"^[a-zA-Z0-9.:-]+$", target):
        await update.message.reply_text("❌ Invalid IP or MAC address format.")
        return
        
    if re.match(r"^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$", target.upper()):
        db = await DatabaseManager.get_db()
        cursor = await db.execute("SELECT ip FROM network_devices WHERE mac = ?", (target.upper(),))
        row = await cursor.fetchone()
        if row and row["ip"]:
            target = row["ip"]
        else:
            await update.message.reply_text(f"❌ Unknown MAC address: {target}")
            return
        
    msg = await update.message.reply_text(f"🔍 <i>Fetching recent DNS queries for {target}...</i>", parse_mode=ParseMode.HTML)
    
    try:
        queries = await DatabaseManager.get_recent_dns_queries(target, limit=20)
        if not queries:
            await msg.edit_text(f"<i>No DNS queries found for {target} in the retention window.</i>", parse_mode=ParseMode.HTML)
            return
            
        lines = []
        for q in queries:
            qtype = q.get("query_type", "A")
            qname = formatters.escape(q["query_name"])
            lines.append(f"• [{qtype}] {qname}")
            
        out = "\n".join(lines)
        await msg.edit_text(f"📡 <b>Recent DNS for <code>{target}</code>:</b>\n<pre>{out}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f"❌ Failed to fetch DNS logs: {e}")

@auth_required
async def traceroute_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide an IP or hostname: /traceroute 1.1.1.1")
        return
    host = context.args[0]
    if not re.match(r"^[a-zA-Z0-9.-]+$", host):
        await update.message.reply_text("❌ That doesn't look like a valid IP or hostname.")
        return
    
    msg = await update.message.reply_text(f"🚀 <i>Running traceroute to {formatters.escape(host)}...</i>", parse_mode=ParseMode.HTML)
    
    try:
        proc = await asyncio.create_subprocess_exec(
            "traceroute", host,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        output = stdout.decode('utf-8', errors='ignore')[:3800]
        if not output.strip():
            output = stderr.decode('utf-8', errors='ignore')[:3800]
            
        await msg.edit_text(f"<b>Traceroute to {formatters.escape(host)}:</b>\n<pre>{formatters.escape(output)}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f"❌ Traceroute failed: {e}")

@auth_required
async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith("whitelist:"):
        mac = data.split(":", 1)[1]
        success = await DatabaseManager.mark_known(mac)
        if success:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"✅ Whitelisted MAC: {mac}")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⚠️ MAC {mac} not found in database.")
            
    elif data.startswith("attacker:"):
        ip = data.split(":", 1)[1]
        msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🔍 <i>Looking up OSINT for {ip}...</i>", parse_mode=ParseMode.HTML)
        info = await get_ip_info(ip)
        await msg.edit_text(f"🌐 <b>OSINT for <code>{ip}</code>:</b>\n<pre>{formatters.escape(info)}</pre>", parse_mode=ParseMode.HTML)

import tempfile
import os
import csv

@auth_required
async def export_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📦 <i>Generating export...</i>", parse_mode=ParseMode.HTML)
    try:
        db = await DatabaseManager.get_db()
        cursor = await db.execute("SELECT * FROM network_devices")
        rows = await cursor.fetchall()
        
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, 'w', newline='', encoding='utf-8') as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                for row in rows:
                    writer.writerow(dict(row))
        
        await update.message.reply_document(document=open(path, 'rb'), filename="network_devices.csv")
        os.remove(path)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Export failed: {e}")

@auth_required
async def logs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /logs <service> [lines]\nValid services: overwatcher, overwatcher-sniffer, overwatcher-dashboard")
        return
        
    service = context.args[0]
    allowed = ["overwatcher", "overwatcher-sniffer", "overwatcher-dashboard"]
    if service not in allowed:
        await update.message.reply_text(f"❌ Invalid service. Allowed: {', '.join(allowed)}")
        return
        
    lines = "50"
    if len(context.args) > 1 and context.args[1].isdigit():
        lines = context.args[1]
        
    msg = await update.message.reply_text(f"📋 <i>Fetching logs for {service}...</i>", parse_mode=ParseMode.HTML)
    try:
        proc = await asyncio.create_subprocess_exec(
            "journalctl", "-u", service, "-n", lines, "--no-pager",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        
        output = stdout.decode('utf-8', errors='ignore')
        if not output.strip():
            await msg.edit_text(f"<i>No logs found for {service}.</i>", parse_mode=ParseMode.HTML)
            return
            
        if len(output) > 3800:
            fd, path = tempfile.mkstemp(suffix=".log")
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(output)
            await update.message.reply_document(document=open(path, 'rb'), filename=f"{service}.log")
            os.remove(path)
            await msg.delete()
        else:
            await msg.edit_text(f"<b>Logs for {service}</b>:\n<pre>{formatters.escape(output)}</pre>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f"❌ Failed to fetch logs: {e}")
