#!/usr/bin/env python3
import sys
import os
import asyncio
import logging

# Ensure parent dir is in sys.path so we can import config/core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
from telegram import Bot
from core.dhcp_watcher import DHCPWatcher
from core.arp_watcher import ARPWatcher

logging.basicConfig(level=getattr(logging, config.log_level.upper()), format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("sniffer")

async def main():
    import scapy.all as scapy
    from scapy.layers.dhcp import DHCP
    from scapy.layers.l2 import ARP
    
    bot = Bot(config.telegram_bot_token.get_secret_value())
    dhcp_watcher = DHCPWatcher(bot)
    arp_watcher = ARPWatcher(bot)
    
    loop = asyncio.get_running_loop()
    
    def packet_callback(pkt):
        if ARP in pkt:
            asyncio.run_coroutine_threadsafe(arp_watcher.process_packet(pkt), loop)
        elif DHCP in pkt:
            asyncio.run_coroutine_threadsafe(dhcp_watcher.process_packet(pkt), loop)
            
    logger.info("Starting passive sniffer on 'arp or (udp and (port 67 or port 68))'...")
    
    try:
        # Sniff in a thread so it doesn't block asyncio loop
        await asyncio.to_thread(scapy.sniff, filter="arp or (udp and (port 67 or port 68))", prn=packet_callback, store=0)
    except Exception as e:
        logger.error(f"Sniffer crashed: {e}")
        
if __name__ == "__main__":
    asyncio.run(main())
