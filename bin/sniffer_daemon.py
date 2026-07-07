#!/usr/bin/env python3
import sys
import os
import asyncio

# Ensure parent dir is in sys.path so we can import config/core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
from telegram import Bot
from core.dhcp_watcher import DHCPWatcher
from core.arp_watcher import ARPWatcher
from core.dns_watcher import DNSWatcher
from core import dns_blocklist

from core.logging_setup import configure_logging
import logging
configure_logging("sniffer")
logger = logging.getLogger("sniffer")

async def main():
    import scapy.all as scapy
    from scapy.layers.dhcp import DHCP
    from scapy.layers.l2 import ARP
    
    if not config.sniffer_interface:
        logger.error("SNIFFER_INTERFACE not set — scapy would auto-select an interface, which may be your WiFi adapter and can affect WiFi stability on some chipsets. Set SNIFFER_INTERFACE explicitly in .env.")
        sys.exit(1)
        
    bot = Bot(config.telegram_bot_token.get_secret_value())
    dhcp_watcher = DHCPWatcher(bot)
    arp_watcher = ARPWatcher(bot)
    dns_watcher = DNSWatcher(bot)
    
    # Load DNS blocklist if enabled
    await dns_blocklist.load_or_refresh()
    
    loop = asyncio.get_running_loop()
    
    def packet_callback(pkt):
        if ARP in pkt:
            asyncio.run_coroutine_threadsafe(arp_watcher.process_packet(pkt), loop)
        elif DHCP in pkt:
            asyncio.run_coroutine_threadsafe(dhcp_watcher.process_packet(pkt), loop)
        elif pkt.haslayer(scapy.DNS):
            asyncio.run_coroutine_threadsafe(dns_watcher.process_packet(pkt), loop)
            
    logger.info(f"Starting passive sniffer on interface '{config.sniffer_interface}' with filter 'arp or (udp and (port 67 or port 68 or port 53))'...")
    
    try:
        # Sniff in a thread so it doesn't block asyncio loop
        await asyncio.to_thread(scapy.sniff, iface=config.sniffer_interface, filter="arp or (udp and (port 67 or port 68 or port 53))", prn=packet_callback, store=0)
    except Exception as e:
        logger.error(f"Sniffer crashed: {e}")
        
if __name__ == "__main__":
    asyncio.run(main())
