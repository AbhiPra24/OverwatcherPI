import logging
import aiohttp
from datetime import datetime
from typing import Set, Tuple, Dict, Optional
from config import config

logger = logging.getLogger(__name__)

# Two sets to hold our parsed threat intel
BLOCKED_DOMAINS: Set[str] = set()
BLOCKED_IPS: Set[str] = set()
LAST_REFRESH: Optional[datetime] = None

# Maltrail-inspired feed registry
# Types: 
#   'hosts': standard hosts file format (0.0.0.0 domain.com)
#   'url_list': list of URLs (http://malicious.com/payload.exe) -> extract domain
#   'plain_ip': list of malicious IPs, one per line
FEEDS = {
    "StevenBlack (Ad/Malware)": {
        "url": "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
        "type": "hosts"
    },
    "URLhaus (Malware URLs)": {
        "url": "https://urlhaus.abuse.ch/downloads/text/",
        "type": "url_list"
    },
    "Feodo Tracker (Botnet IPs)": {
        "url": "https://feodotracker.abuse.ch/downloads/ipblocklist.txt",
        "type": "plain_ip"
    }
}

def _parse_feed(feed_type: str, content: str) -> Tuple[Set[str], Set[str]]:
    """Parse feed content based on its type into (domains, ips)."""
    domains = set()
    ips = set()
    
    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        if feed_type == "hosts":
            parts = line.split()
            if len(parts) >= 2 and parts[0] in ('0.0.0.0', '127.0.0.1'):
                domain = parts[1].lower()
                if domain not in ('0.0.0.0', '127.0.0.1', 'localhost', 'broadcasthost'):
                    domains.add(domain)
                    
        elif feed_type == "url_list":
            # e.g. http://192.168.1.1:80/payload or https://malicious.com/
            try:
                # Basic string splitting to extract domain/IP
                if "://" in line:
                    host_part = line.split("://")[1].split("/")[0]
                    # Handle ports if present
                    host = host_part.split(":")[0].lower()
                    if host:
                        # Very simple IP check
                        if all(c.isdigit() or c == '.' for c in host) and host.count('.') == 3:
                            ips.add(host)
                        else:
                            domains.add(host)
            except Exception:
                pass
                
        elif feed_type == "plain_ip":
            # e.g. 192.168.1.1
            ip = line.split()[0]
            if all(c.isdigit() or c == '.' for c in ip) and ip.count('.') == 3:
                ips.add(ip)

    return domains, ips

async def fetch_feed(session: aiohttp.ClientSession, name: str, info: Dict[str, str]) -> Tuple[str, Set[str], Set[str]]:
    try:
        async with session.get(info["url"], timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status == 200:
                text = await response.text(encoding="utf-8", errors="ignore")
                domains, ips = await asyncio.to_thread(_parse_feed, info["type"], text)
                logger.info(f"Feed '{name}': loaded {len(domains)} domains, {len(ips)} IPs.")
                return name, domains, ips
            else:
                logger.error(f"Feed '{name}': HTTP {response.status}")
    except Exception as e:
        logger.error(f"Feed '{name}': Failed to download - {e}")
    return name, set(), set()

async def load_or_refresh(force: bool = False):
    if not config.threat_intel_enabled:
        return
        
    global BLOCKED_DOMAINS, BLOCKED_IPS, LAST_REFRESH
    if BLOCKED_DOMAINS and not force:
        logger.info(f"Threat Intel already populated with {len(BLOCKED_DOMAINS)} domains and {len(BLOCKED_IPS)} IPs.")
        return

    logger.info("Downloading Threat Intel feeds...")
    new_domains = set()
    new_ips = set()
    
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_feed(session, name, info) for name, info in FEEDS.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in results:
            if isinstance(res, tuple) and len(res) == 3:
                _, d, i = res
                new_domains.update(d)
                new_ips.update(i)
                
    BLOCKED_DOMAINS = new_domains
    BLOCKED_IPS = new_ips
    LAST_REFRESH = datetime.now()
    
    logger.info(f"Threat Intel combined: {len(BLOCKED_DOMAINS)} domains, {len(BLOCKED_IPS)} IPs.")

def is_domain_blocked(domain: str) -> bool:
    return domain.lower() in BLOCKED_DOMAINS
    
def is_ip_blocked(ip: str) -> bool:
    return ip in BLOCKED_IPS

def get_stats() -> dict:
    return {
        "last_refresh": LAST_REFRESH,
        "blocked_domains_count": len(BLOCKED_DOMAINS),
        "blocked_ips_count": len(BLOCKED_IPS)
    }
