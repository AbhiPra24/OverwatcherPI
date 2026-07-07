import asyncio
from config import config

NMAP_SEMAPHORE = asyncio.Semaphore(config.max_concurrent_scans)
SCAN_LOCK = asyncio.Lock()

def get_network_load(app) -> float:
    """Return max jitter from recent latency quality stats."""
    if "latency_stats" in app.bot_data:
        wan = app.bot_data["latency_stats"].get("wan", {})
        gw = app.bot_data["latency_stats"].get("gateway", {})
        return max(wan.get("jitter_ms", 0.0), gw.get("jitter_ms", 0.0))
    return 0.0
