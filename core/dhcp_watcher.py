import logging
from config import config
from telegram import Bot
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

class DHCPWatcher:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.trusted = config.trusted_dhcp_server
        
    async def process_packet(self, pkt):
        from scapy.layers.dhcp import DHCP
        from scapy.layers.inet import IP
        from scapy.layers.l2 import Ether
        
        if not self.trusted:
            return
            
        if DHCP in pkt and pkt[DHCP].options:
            options = pkt[DHCP].options
            msg_type = None
            for opt in options:
                if isinstance(opt, tuple) and opt[0] == 'message-type':
                    msg_type = opt[1]
                    break
            
            # DHCP OFFER is 2
            if msg_type == 2:
                src_ip = pkt[IP].src
                mac = pkt[Ether].src
                
                if src_ip != self.trusted:
                    msg = f"🚨 <b>Rogue DHCP server detected:</b> offer from {src_ip} (MAC <code>{mac}</code>), expected {self.trusted}."
                    logger.warning(msg)
                    try:
                        await self.bot.send_message(
                            chat_id=config.telegram_owner_id,
                            text=msg,
                            parse_mode=ParseMode.HTML
                        )
                    except Exception as e:
                        logger.error(f"Failed to send DHCP alert: {e}")
