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
        from zeroconf import ZeroconfServiceTypes
        zc = Zeroconf()
        dynamic_types = list(ZeroconfServiceTypes.find(zc=zc, timeout=1.5))
        fixed_types = [
            '_googlecast._tcp.local.', '_apple-mobdev2._tcp.local.', 
            '_hap._tcp.local.', '_http._tcp.local.', '_smb._tcp.local.', 
            '_printer._tcp.local.', '_ipp._tcp.local.', '_spotify-connect._tcp.local.', 
            '_airplay._tcp.local.', '_raop._tcp.local.', '_sleep-proxy._udp.local.',
            '_companion-link._tcp.local.', '_homekit._tcp.local.', '_services._dns-sd._udp.local.'
        ]
        all_types = list(set(dynamic_types + fixed_types))
        
        browser = ServiceBrowser(zc, all_types, Listener())
        import time
        time.sleep(2)
        zc.close()
    except Exception as e:
        logger.error(f"Zeroconf failed: {e}")
        
    return ip_names


async def _resolve_netbios(ip: str) -> str:
    """Resolve NetBIOS name using nmblookup."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "nmblookup", "-A", ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            lines = stdout.decode('utf-8', errors='ignore').splitlines()
            for line in lines:
                if '<00>' in line and 'UNIQUE' in line and 'ACTIVE' in line:
                    parts = line.split('<00>')
                    if parts:
                        return parts[0].strip()
    except Exception as e:
        logger.debug(f"NetBIOS lookup failed for {ip}: {e}")
    return ""


async def scan() -> List[NetworkDevice]:
    """Run an async nmap scan and enrich the results."""
    logger.info(f"Starting network scan on {config.scan_subnet}...")
    
    mdns_task = asyncio.create_task(asyncio.to_thread(_get_mdns_names))
    from scanners import ssdp
    ssdp_task = asyncio.create_task(ssdp.discover(timeout=3.0))
    
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
    ssdp_results = await ssdp_task
    
    results = []
    
    for raw in raw_devices:
        ip = raw["ip"]
        vendor = await oui.get_vendor(raw["mac"])
        if vendor == "Unknown" and raw["nmap_vendor"] != "Unknown":
            vendor = raw["nmap_vendor"]
            
        mdns_name = mdns_results.get(ip)
        ssdp_server = ssdp_results.get(ip)
        netbios_name = await _resolve_netbios(ip)
        
        hostname = mdns_name
        if not hostname:
            hostname = netbios_name
        if not hostname:
            hostname = await _resolve_hostname(ip)
            
        results.append({
            "ip": ip,
            "mac": raw["mac"],
            "vendor": vendor,
            "hostname": hostname,
            "raw_mdns_name": mdns_name,
            "raw_ssdp_server": ssdp_server,
            "raw_netbios_name": netbios_name
        })

    for res in results:
        if res["vendor"] == "Unknown" and not res["hostname"]:
            try:
                ip = res["ip"]
                b_proc = await asyncio.create_subprocess_exec(
                    "nmap", "-sV", "--script", "http-title,snmp-info", ip,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                try:
                    b_stdout, _ = await asyncio.wait_for(b_proc.communicate(), timeout=15.0)
                    if b_proc.returncode == 0:
                        out = b_stdout.decode('utf-8', errors='ignore')
                        for line in out.splitlines():
                            if "http-title:" in line:
                                title = line.split("http-title:", 1)[1].strip()
                                res["hostname"] = title
                                break
                            if "snmp-info:" in line:
                                info = line.split("snmp-info:", 1)[1].strip()
                                res["hostname"] = info
                                break
                except asyncio.TimeoutError:
                    b_proc.kill()
            except Exception as e:
                logger.debug(f"Banner grab failed for {res['ip']}: {e}")

    final_results = []
    for res in results:
        final_results.append(NetworkDevice(
            ip=res["ip"],
            mac=res["mac"],
            vendor=res["vendor"],
            hostname=res["hostname"] or "",
            raw_mdns_name=res["raw_mdns_name"],
            raw_ssdp_server=res["raw_ssdp_server"],
            raw_netbios_name=res["raw_netbios_name"]
        ))
        
    logger.info(f"Scan complete. Found {len(final_results)} active devices.")
    return final_results
