import time
import logging
from collections import defaultdict
from typing import Dict, Set

from telegram.ext import Application
from telegram.constants import ParseMode

from core.database import DatabaseManager
from bot.broadcaster import broadcast_message

logger = logging.getLogger(__name__)

class ScanDetector:
    def __init__(self, bot: Application, loop):
        self.bot = bot
        self.loop = loop
        # src_ip -> { (dst_ip, dst_port) }
        self.recent_syns: Dict[str, Set[str]] = defaultdict(set)
        # src_ip -> list of timestamps
        self.syn_timestamps: Dict[str, list] = defaultdict(list)
        
        self.window_seconds = 10.0
        self.threshold = 50  # 50 unique connection attempts in 10s
        self.last_cleanup = time.time()
        
    def process_syn(self, src_ip: str, dst_ip: str, dport: int):
        now = time.time()
        
        # Periodically clean up old data to prevent memory leaks
        if now - self.last_cleanup > self.window_seconds:
            self._cleanup(now)
            self.last_cleanup = now
            
        target = f"{dst_ip}:{dport}"
        self.recent_syns[src_ip].add(target)
        self.syn_timestamps[src_ip].append(now)
        
        # Check if threshold exceeded
        if len(self.recent_syns[src_ip]) >= self.threshold:
            # Verify they are actually within the window
            recent_count = sum(1 for t in self.syn_timestamps[src_ip] if now - t <= self.window_seconds)
            if recent_count >= self.threshold:
                self._trigger_alert(src_ip, len(self.recent_syns[src_ip]))
                # Clear to avoid alert spam
                self.recent_syns[src_ip].clear()
                self.syn_timestamps[src_ip].clear()
                
    def _cleanup(self, now: float):
        for src in list(self.syn_timestamps.keys()):
            # Filter timestamps
            self.syn_timestamps[src] = [t for t in self.syn_timestamps[src] if now - t <= self.window_seconds]
            if not self.syn_timestamps[src]:
                del self.syn_timestamps[src]
                if src in self.recent_syns:
                    del self.recent_syns[src]

    def _trigger_alert(self, src_ip: str, count: int):
        import asyncio
        async def _alert():
            key = f"scan_alert:{src_ip}"
            if await DatabaseManager.should_alert_resource(key, 1.0):  # 1 hour cooldown for same attacker
                msg = f"🚨 <b>Internal Port Scan Detected</b>\n\nDevice <b>{src_ip}</b> made {count} unique connection attempts within {int(self.window_seconds)} seconds."
                try:
                    await broadcast_message(self.bot, text=msg, parse_mode=ParseMode.HTML)
                    await DatabaseManager.log_event("security", "high", f"Port scan detected from {src_ip} ({count} attempts)")
                except Exception as e:
                    logger.error(f"Failed to send scan alert: {e}")
                    
        # Fire and forget
        asyncio.run_coroutine_threadsafe(_alert(), self.loop)
