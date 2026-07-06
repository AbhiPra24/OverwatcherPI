import asyncio
import xml.etree.ElementTree as ET
import logging
from typing import List
import socket
from zeroconf import Zeroconf, ServiceBrowser

from config import config
from core.database import NetworkDevice
from core import oui

logger = logging.getLogger(__name__)


def _parse_nmap_xml(xml_content: str) -> List[dict]:
    """Parse Nmap XML output synchronously."""
    devices = []
    try:
        root = ET.fromstring(xml_content)
        for host in root.findall('host'):
            state = host.find('status')
            if state is None or state.get('state') != 'up':
                continue
            
            ip = None
            mac = None
            vendor = "Unknown"
            
            for address in host.findall('address'):
                addr_type = address.get('addrtype')
                if addr_type == 'ipv4':
                    ip = address.get('addr')
                elif addr_type == 'mac':
                    mac = address.get('addr')
                    # nmap sometimes provides a vendor attribute if it matches its internal mac-prefixes
                    if address.get('vendor'):
                        vendor = address.get('vendor')
                        
            if ip and mac:
                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "nmap_vendor": vendor
                })
    except ET.ParseError as e:
        logger.error(f"Failed to parse nmap XML: {e}")
        
    return devices


async def _resolve_hostname(ip: str) -> str:
    """Resolve hostname for an IP address without blocking the loop."""
    try:
        name, _, _ = await asyncio.to_thread(socket.gethostbyaddr, ip)
        return name
    except Exception:
        return ""


def _get_mdns_names() -> dict:
    """Run a brief mDNS scan and return IP -> name mapping."""
    ip_names = {}
    
    class Listener:
        def remove_service(self, zc, type, name): pass
        def update_service(self, zc, type, name): pass
        def add_service(self, zc, type_, name):
            try:
                info = zc.get_service_info(type_, name)
                if info and info.parsed_addresses():
                    ip = info.parsed_addresses()[0]
                    clean_name = name.split('.')[0]
                    ip_names[ip] = clean_name
            except Exception:
                pass

    try:
        zc = Zeroconf()
        types = [
            '_googlecast._tcp.local.', '_apple-mobdev2._tcp.local.', 
            '_hap._tcp.local.', '_http._tcp.local.', '_smb._tcp.local.', 
            '_printer._tcp.local.', '_ipp._tcp.local.', '_spotify-connect._tcp.local.', 
            '_airplay._tcp.local.', '_raop._tcp.local.', '_sleep-proxy._udp.local.',
            '_companion-link._tcp.local.', '_homekit._tcp.local.', '_services._dns-sd._udp.local.'
        ]
        browser = ServiceBrowser(zc, types, Listener())
        import time
        time.sleep(3)
        zc.close()
    except Exception as e:
        logger.error(f"Zeroconf failed: {e}")
        
    return ip_names


async def scan() -> List[NetworkDevice]:
    """Run an async nmap scan and enrich the results."""
    logger.info(f"Starting network scan on {config.scan_subnet}...")
    
    mdns_task = asyncio.create_task(asyncio.to_thread(_get_mdns_names))
    
    cmd = ["nmap", "--privileged", "-sn", "-oX", "-", config.scan_subnet]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        err_msg = stderr.decode()
        logger.error(f"nmap failed with code {process.returncode}: {err_msg}")
        if "privilege" in err_msg.lower() or "root" in err_msg.lower() or process.returncode == 1:
            raise RuntimeError(f"Nmap permission denied. Ensure setcap cap_net_raw,cap_net_admin,cap_net_bind_service+eip is configured on $(which nmap). Error: {err_msg.strip()}")
        raise RuntimeError(f"Nmap scan failed: {err_msg.strip()}")
        
    xml_output = stdout.decode('utf-8')
    raw_devices = await asyncio.to_thread(_parse_nmap_xml, xml_output)
    mdns_results = await mdns_task
    
    results = []
    for raw in raw_devices:
        # Resolve vendor via local OUI cache for more accurate/current results than nmap's static list
        vendor = await oui.get_vendor(raw["mac"])
        if vendor == "Unknown" and raw["nmap_vendor"] != "Unknown":
            vendor = raw["nmap_vendor"]
            
        hostname = mdns_results.get(raw["ip"])
        if not hostname:
            hostname = await _resolve_hostname(raw["ip"])
        
        results.append(NetworkDevice(
            ip=raw["ip"],
            mac=raw["mac"],
            vendor=vendor,
            hostname=hostname
        ))
        
    logger.info(f"Scan complete. Found {len(results)} active devices.")
    return results
