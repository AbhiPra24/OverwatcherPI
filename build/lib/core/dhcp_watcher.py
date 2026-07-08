import logging
from config import config
from telegram import Bot
from telegram.constants import ParseMode
from core.database import DatabaseManager

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
            subnet_mask = None
            router = None
            for opt in options:
                if isinstance(opt, tuple):
                    if opt[0] == 'message-type':
                        msg_type = opt[1]
                    elif opt[0] == 'subnet_mask':
                        subnet_mask = opt[1]
                    elif opt[0] == 'router':
                        router = opt[1]
            
            # DHCP OFFER is 2
            if msg_type == 2:
                src_ip = pkt[IP].src
                mac = pkt[Ether].src
                import ipaddress
                
                is_rogue = False
                bad_reason = ""
                
                if src_ip != self.trusted:
                    is_rogue = True
                    bad_reason = f"offer from {src_ip} (MAC <code>{mac}</code>), expected {self.trusted}"
                else:
                    try:
                        expected_mask = str(ipaddress.ip_network(config.scan_subnet, strict=False).netmask)
                        if subnet_mask and subnet_mask != expected_mask:
                            is_rogue = True
                            bad_reason = f"bad subnet mask {subnet_mask}, expected {expected_mask} (from {src_ip})"
                        elif router and router != config.gateway_ip:
                            is_rogue = True
                            bad_reason = f"bad gateway {router}, expected {config.gateway_ip} (from {src_ip})"
                    except Exception as e:
                        logger.error(f"Failed to check DHCP subnet/router: {e}")
                        
                if is_rogue:
                    msg = f"🚨 <b>Rogue DHCP server detected:</b> {bad_reason}."
                    logger.warning(msg)
                    for owner_id in config.telegram_owner_ids:
                        try:
                            await self.bot.send_message(
                                chat_id=owner_id,
                                text=msg,
                                parse_mode=ParseMode.HTML
                            )
                        except Exception as e:
                            logger.error(f"Failed to send DHCP alert to {owner_id}: {e}")
                    try:
                        await DatabaseManager.log_event(
                            category="security",
                            severity="high",
                            message=f"Rogue DHCP server detected: {bad_reason}.",
                            related_id=mac
                        )
                    except Exception as e:
                        logger.error(f"Failed to log DHCP alert: {e}")
