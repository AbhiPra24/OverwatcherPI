import asyncio
import logging
import time
from typing import List, Tuple
from scapy.all import DNS, DNSQR, IP
from telegram.ext import Application

from config import config
from core.database import DatabaseManager
from core import dns_blocklist
from bot.broadcaster import broadcast_message
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

class DNSWatcher:
    def __init__(self, bot: Application):
        self.bot = bot
        self._batch: List[Tuple[float, str, str, str]] = []
        self._batch_lock = asyncio.Lock()
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def _periodic_flush(self):
        while True:
            await asyncio.sleep(10)
            async with self._batch_lock:
                if self._batch:
                    try:
                        await DatabaseManager.insert_dns_queries(self._batch)
                        self._batch.clear()
                    except Exception as e:
                        logger.error(f"Failed to flush DNS queries: {e}")

    async def process_packet(self, pkt):
        if not pkt.haslayer(DNS) or not pkt.haslayer(DNSQR) or not pkt.haslayer(IP):
            return
            
        # Only process DNS queries (qr == 0)
        if pkt[DNS].qr != 0:
            return
            
        src_ip = pkt[IP].src
        
        # Scapy decodes qname as bytes, e.g., b'www.google.com.'
        qname_bytes = pkt[DNSQR].qname
        if not qname_bytes:
            return
            
        try:
            qname = qname_bytes.decode('utf-8').lower()
            if qname.endswith('.'):
                qname = qname[:-1]
        except Exception:
            return
            
        qtype = pkt[DNSQR].qtype
        # qtype is an int, could map to A, AAAA, etc, but storing as str/int is fine
        qtype_str = str(qtype)
        if qtype == 1:
            qtype_str = "A"
        elif qtype == 28:
            qtype_str = "AAAA"
        elif qtype == 5:
            qtype_str = "CNAME"
            
        timestamp = time.time()
        
        async with self._batch_lock:
            self._batch.append((timestamp, src_ip, qname, qtype_str))
            
        # Blocklist check
        if config.dns_blocklist_enabled and qname in dns_blocklist.BLOCKLIST:
            await self._check_and_alert(src_ip, qname)

    async def _check_and_alert(self, src_ip: str, domain: str):
        key = f"dns_blocklist:{src_ip}:{domain}"
        if await DatabaseManager.should_alert_resource(key, 2.0):  # 2 hour cooldown
            msg = f"🚨 <b>DNS Blocklist Hit</b>\n\nDevice <b>{src_ip}</b> queried known-bad domain:\n<code>{domain}</code>"
            try:
                await broadcast_message(self.bot, text=msg, parse_mode=ParseMode.HTML)
                await DatabaseManager.log_event("security", "warning", f"DNS Blocklist Hit: {src_ip} queried {domain}")
            except Exception as e:
                logger.error(f"Failed to send DNS alert: {e}")
