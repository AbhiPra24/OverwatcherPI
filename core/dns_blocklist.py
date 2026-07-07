import asyncio
import logging
import aiohttp
from typing import Set

logger = logging.getLogger(__name__)

BLOCKLIST_URL = "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts"
BLOCKLIST: Set[str] = set()

def _parse_hosts_file(content: str) -> Set[str]:
    """Parse hosts file synchronously in a thread."""
    lines = content.splitlines()
    domains = set()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ('0.0.0.0', '127.0.0.1'):
            domain = parts[1].lower()
            if domain not in ('0.0.0.0', '127.0.0.1', 'localhost', 'broadcasthost'):
                domains.add(domain)
    return domains

async def load_or_refresh(force: bool = False):
    from config import config
    if not config.dns_blocklist_enabled:
        return
        
    global BLOCKLIST
    if BLOCKLIST and not force:
        logger.info(f"DNS Blocklist already populated with {len(BLOCKLIST)} entries.")
        return

    logger.info("Downloading DNS blocklist...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(BLOCKLIST_URL, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    text = await response.text(encoding="utf-8")
                    logger.info("Parsing DNS blocklist in background thread...")
                    BLOCKLIST = await asyncio.to_thread(_parse_hosts_file, text)
                    logger.info(f"Successfully cached {len(BLOCKLIST)} blocked domains.")
                else:
                    logger.error(f"Failed to download DNS blocklist, HTTP {response.status}")
    except Exception as e:
        logger.error(f"Exception during DNS blocklist download: {e}")
