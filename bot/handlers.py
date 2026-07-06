from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.middleware import auth_required
from bot import formatters
from utils import metrics
from scanners import network, bluetooth
from core.database import DatabaseManager

@auth_required
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🛡 <b>OverwatcherPI</b> is online.\n"
        "Commands:\n"
        "/status - Hardware diagnostics\n"
        "/network - Scan local subnet\n"
        "/bluetooth - Scan nearby BLE devices"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


@auth_required
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = metrics.get_system_status()
    await update.message.reply_text(formatters.format_status(status), parse_mode=ParseMode.HTML)


@auth_required
async def network_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 <i>Scanning local network...</i>", parse_mode=ParseMode.HTML)
    
    devices = await network.scan()
    new_macs, _ = await DatabaseManager.upsert_network_devices(devices)
    
    await msg.edit_text(formatters.format_network(devices, new_macs), parse_mode=ParseMode.HTML)


@auth_required
async def bluetooth_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔷 <i>Scanning for Bluetooth LE devices (10s)...</i>", parse_mode=ParseMode.HTML)
    
    devices = await bluetooth.scan()
    await DatabaseManager.upsert_bt_devices(devices)
    
    await msg.edit_text(formatters.format_bluetooth(devices), parse_mode=ParseMode.HTML)
