import asyncio
import logging
import time
from typing import List, Tuple
from scapy.all import DNS, DNSQR, IP
from telegram.ext import Application

from config import config
from core.database import DatabaseManager
from core import threat_intel
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
            
        # We want queries (qr=0) to log and check domains, and responses (qr=1) to check IPs
        is_query = pkt[DNS].qr == 0
        src_ip = pkt[IP].src
        dst_ip = pkt[IP].dst
        
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
        
        
        if is_query:
            async with self._batch_lock:
                self._batch.append((timestamp, src_ip, qname, qtype_str))
                
            # Blocklist check for domains
            if config.threat_intel_enabled and threat_intel.is_domain_blocked(qname):
                key = f"threat_intel_domain:{src_ip}:{qname}"
                if await DatabaseManager.should_alert_resource(key, 2.0):  # 2 hour cooldown
                    msg = f"🚨 <b>Threat Intel Hit (Domain)</b>\n\nDevice <b>{src_ip}</b> queried known-bad domain:\n<code>{qname}</code>"
                    try:
                        await broadcast_message(self.bot, text=msg, parse_mode=ParseMode.HTML)
                        await DatabaseManager.log_event("security", "warning", f"Threat Intel Hit: {src_ip} queried {qname}")
                    except Exception as e:
                        logger.error(f"Failed to send Threat Intel alert: {e}")
        else:
            # Process DNS Response (qr=1) to check resolved IPs against BLOCKED_IPS
            if config.threat_intel_enabled and pkt[DNS].ancount > 0:
                from scapy.all import DNSRR
                for i in range(pkt[DNS].ancount):
                    rr = pkt[DNS].an[i]
                    if isinstance(rr, DNSRR) and rr.type == 1: # A record (IPv4)
                        rdata_ip = str(rr.rdata)
                        if threat_intel.is_ip_blocked(rdata_ip):
                            key = f"threat_intel_ip:{dst_ip}:{rdata_ip}"
                            if await DatabaseManager.should_alert_resource(key, 2.0):
                                msg = f"🚨 <b>Threat Intel Hit (IP)</b>\n\nDevice <b>{dst_ip}</b> resolved domain <code>{qname}</code> to malicious IP:\n<code>{rdata_ip}</code>"
                                try:
                                    await broadcast_message(self.bot, text=msg, parse_mode=ParseMode.HTML)
                                    await DatabaseManager.log_event("security", "high", f"Threat Intel Hit: {dst_ip} resolved {qname} to malicious IP {rdata_ip}")
                                except Exception as e:
                                    logger.error(f"Failed to send Threat Intel alert: {e}")
