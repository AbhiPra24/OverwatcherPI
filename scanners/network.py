import asyncio
import xml.etree.ElementTree as ET
import logging
from typing import List
import socket

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
    except socket.herror:
        return ""


async def scan() -> List[NetworkDevice]:
    """Run an async nmap scan and enrich the results."""
    logger.info(f"Starting network scan on {config.scan_subnet}...")
    
    cmd = ["nmap", "--privileged", "-sn", "-oX", "-", config.scan_subnet]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        logger.error(f"nmap failed with code {process.returncode}: {stderr.decode()}")
        return []
        
    xml_output = stdout.decode('utf-8')
    raw_devices = await asyncio.to_thread(_parse_nmap_xml, xml_output)
    
    results = []
    for raw in raw_devices:
        # Resolve vendor via local OUI cache for more accurate/current results than nmap's static list
        vendor = await oui.get_vendor(raw["mac"])
        if vendor == "Unknown" and raw["nmap_vendor"] != "Unknown":
            vendor = raw["nmap_vendor"]
            
        hostname = await _resolve_hostname(raw["ip"])
        
        results.append(NetworkDevice(
            ip=raw["ip"],
            mac=raw["mac"],
            vendor=vendor,
            hostname=hostname
        ))
        
    logger.info(f"Scan complete. Found {len(results)} active devices.")
    return results
