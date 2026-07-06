import html
from typing import List, Set
from utils.metrics import SystemStatus
from core.database import NetworkDevice, BLEDevice, HourlyStats


def escape(text: str) -> str:
    """HTML escape to be safe for Telegram HTML parse mode."""
    return html.escape(str(text))


def format_status(status: SystemStatus) -> str:
    lines = [
        "🖥 <b>System Status (Raspberry Pi)</b>",
        "<code>─────────────────────────</code>",
        f"🌡 <b>Temperature:</b> {status.temp_celsius:.1f} °C",
        f"⚡ <b>Power/Throttling:</b> {status.throttling_status}",
        f"⏱ <b>Uptime:</b> {status.uptime_seconds / 3600:.1f} hours",
        "",
        "💾 <b>Memory:</b>",
        f"  • RAM: {status.ram_used_mb:.1f} MB / {status.ram_total_mb:.1f} MB",
        f"  • Disk: {status.disk_used_gb:.1f} GB / {status.disk_total_gb:.1f} GB ({status.disk_percent}%)",
        "",
        "⚙️ <b>CPU Core Usage:</b>"
    ]
    
    for idx, usage in enumerate(status.cpu_per_core):
        lines.append(f"  • Core {idx}: {usage}%")
        
    return "\n".join(lines)


def format_network(devices: List[NetworkDevice], new_macs: Set[str] = None) -> str:
    if new_macs is None:
        new_macs = set()
        
    lines = [
        f"🌐 <b>Network Scan</b> — {len(devices)} active devices",
        "<code>─────────────────────────</code>"
    ]
    
    for dev in sorted(devices, key=lambda d: d.ip):
        icon = "🆕" if dev.mac in new_macs or dev.is_new else "✅"
        lines.append(f"{icon} <b>{escape(dev.ip)}</b>  <code>{escape(dev.mac)}</code>")
        
        info_parts = []
        if dev.hostname:
            info_parts.append(f"<i>{escape(dev.hostname)}</i>")
        info_parts.append(escape(dev.vendor))
        
        lines.append("   " + " | ".join(info_parts))
        lines.append("")
        
    return "\n".join(lines).strip()


def format_bluetooth(devices: List[BLEDevice]) -> str:
    lines = [
        f"🔷 <b>Bluetooth / BLE Scan</b> — {len(devices)} nearby devices",
        "<code>─────────────────────────</code>"
    ]
    
    for dev in sorted(devices, key=lambda d: d.rssi, reverse=True):
        bars = "🟩" * (min(100, max(0, dev.rssi + 100)) // 20 + 1)
        lines.append(f"<b>{escape(dev.name)}</b> (<code>{escape(dev.address)}</code>)")
        lines.append(f"   RSSI: {dev.rssi} dBm {bars}")
        lines.append("")
        
    return "\n".join(lines).strip()


def format_hourly_report(stats: HourlyStats) -> str:
    lines = [
        "📊 <b>Hourly Trend Report</b>",
        "<code>─────────────────────────</code>",
        f"📡 <b>Average Network Devices:</b> {stats.avg_network_devices}",
        f"🔷 <b>Active BLE Devices:</b> {stats.ble_device_count}",
        ""
    ]
    
    if stats.new_macs:
        lines.append("🆕 <b>New Devices Appeared:</b>")
        for mac in stats.new_macs:
            lines.append(f"  • <code>{escape(mac)}</code>")
        lines.append("")
        
    if stats.gone_macs:
        lines.append("🚪 <b>Devices Dropped Off:</b>")
        for mac in stats.gone_macs:
            lines.append(f"  • <code>{escape(mac)}</code>")
            
    if not stats.new_macs and not stats.gone_macs:
        lines.append("<i>No changes in network topology this hour.</i>")
        
    return "\n".join(lines).strip()
