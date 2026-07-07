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
            
        if dev.vendor == "Private (randomized)":
            info_parts.append(f"🎭 {escape(dev.vendor)}")
        elif dev.vendor == "Unknown":
            info_parts.append(f"❓ {escape(dev.vendor)}")
        else:
            info_parts.append(escape(dev.vendor))
        
        lines.append("   " + " | ".join(info_parts))
        lines.append("")
        
    return "\n".join(lines).strip()


def format_bluetooth(devices: List[BLEDevice]) -> str:
    lines = [
        f"🔷 <b>Bluetooth / BLE Scan</b> — {len(devices)} nearby devices",
        "<code>─────────────────────────</code>"
    ]
    
    import json
    from core.ble_proximity import smooth_rssi, estimate_proximity
    
    for dev in sorted(devices, key=lambda d: d.rssi, reverse=True):
        bars = "🟩" * (min(100, max(0, dev.rssi + 100)) // 20 + 1)
        
        hist = []
        try:
            hist = json.loads(dev.rssi_history)
        except Exception:
            hist = [dev.rssi]
            
        smoothed = smooth_rssi(hist)
        prox_tier = estimate_proximity(smoothed, dev.tx_power)
        
        lines.append(f"<b>{escape(dev.name)}</b> (<code>{escape(dev.address)}</code>)")
        lines.append(f"   RSSI: {dev.rssi} dBm {bars} — [{prox_tier}]")
        lines.append("")
        
    return "\n".join(lines).strip()


def format_hourly_report(stats: HourlyStats, latency_stats: dict = None) -> str:
    lines = [
        "📊 <b>Hourly Trend Report</b>",
        "<code>─────────────────────────</code>",
        f"📡 <b>Average Network Devices:</b> {stats.avg_network_devices}",
        f"🔷 <b>Active BLE Devices:</b> {stats.ble_device_count}",
        ""
    ]
    
    if latency_stats:
        gw = latency_stats.get("gateway", {})
        wan = latency_stats.get("wan", {})
        if gw and wan:
            lines.append("📶 <b>Network Quality:</b>")
            lines.append(f"  • Gateway: {gw.get('loss_percent', 100):.1f}% loss, {gw.get('jitter_ms', 0):.2f}ms jitter")
            lines.append(f"  • WAN: {wan.get('loss_percent', 100):.1f}% loss, {wan.get('jitter_ms', 0):.2f}ms jitter")
            lines.append("")
    
    if stats.unwhitelisted_count > 0:
        lines.append(f"⚠️ <b>{stats.unwhitelisted_count} device(s) still unwhitelisted!</b>")
        lines.append("")
        
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
