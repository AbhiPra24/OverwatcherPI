import time
import logging
from telegram import Bot
from telegram.constants import ParseMode
from config import config
from core.database import DatabaseManager

logger = logging.getLogger(__name__)

class ARPWatcher:
    def __init__(self, bot: Bot):
        self.bot = bot
        # Maps IP to (MAC, timestamp)
        self.ip_mac_table = {}
        
    async def process_packet(self, pkt):
        from scapy.layers.l2 import ARP
        
        # ARP reply (is-at) is op=2
        if ARP in pkt and pkt[ARP].op == 2:
            ip = pkt[ARP].psrc
            mac = pkt[ARP].hwsrc
            now = time.time()
            
            if ip in self.ip_mac_table:
                old_mac, last_seen = self.ip_mac_table[ip]
                if old_mac != mac:
                    if now - last_seen < 60:
                        msg = f"🚨 <b>ARP conflict:</b> <code>{ip}</code> claimed by both <code>{old_mac}</code> and <code>{mac}</code>."
                        logger.warning(msg)
                        try:
                            await self.bot.send_message(
                                chat_id=config.telegram_owner_id,
                                text=msg,
                                parse_mode=ParseMode.HTML
                            )
                            await DatabaseManager.log_event(
                                category="security",
                                severity="high",
                                message=f"ARP conflict: {ip} claimed by both {old_mac} and {mac}.",
                                related_id=ip
                            )
                        except Exception as e:
                            logger.error(f"Failed to send ARP alert: {e}")
                    else:
                        logger.info(f"ARP change for {ip}: {old_mac} -> {mac}")
                        
            self.ip_mac_table[ip] = (mac, now)
