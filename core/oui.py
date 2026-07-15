import asyncio
import csv
import logging
from typing import List, Tuple
import aiohttp
from core.database import DatabaseManager

logger = logging.getLogger(__name__)

OUI_URL = "https://standards-oui.ieee.org/oui/oui.csv"


def _parse_oui_csv(content: str) -> List[Tuple[str, str]]:
    """Parse CSV content synchronously. To be run in a thread."""
    lines = content.splitlines()
    reader = csv.reader(lines)
    mappings = []
    
    # Header: Registry,Assignment,Organization Name,Organization Address
    # Example: MA-L,A4C138,"Apple, Inc.",...
    for idx, row in enumerate(reader):
        if idx == 0 or len(row) < 3:
            continue
            
        assignment = row[1].strip().upper()
        if len(assignment) == 6:
            org_name = row[2].strip()
            mappings.append((assignment, org_name))
            
    return mappings


async def load_or_refresh(force: bool = False):
    """Ensure OUI database is populated, download if empty or forced."""
    count = await DatabaseManager.oui_count()
    if count > 0 and not force:
        logger.info(f"OUI cache already populated with {count} entries.")
        return

    logger.info("Downloading IEEE OUI database...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(OUI_URL, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    text = await response.text(encoding="utf-8")
                    
                    # Offload parsing to a thread so we don't block the async loop
                    logger.info("Parsing OUI database in background thread...")
                    mappings = await asyncio.to_thread(_parse_oui_csv, text)
                    
                    await DatabaseManager.bulk_insert_oui(mappings)
                    logger.info(f"Successfully cached {len(mappings)} OUI entries.")
                else:
                    logger.error(f"Failed to download OUI db, HTTP {response.status}")
    except Exception as e:
        logger.error(f"Exception during OUI download: {e}")


def is_locally_administered(mac: str) -> bool:
    """Check if bit 0x02 is set on the first octet (randomized/private MAC)."""
    clean_mac = mac.replace(":", "").replace("-", "").strip()
    if len(clean_mac) >= 2:
        try:
            first_octet = int(clean_mac[:2], 16)
            return bool(first_octet & 0x02)
        except ValueError:
            pass
    return False


async def get_vendor(mac: str) -> str:
    """Lookup a MAC address in the OUI cache."""
    if is_locally_administered(mac):
        return "Private (randomized)"
        
    # Normalize MAC (e.g., 'C0:2E:1D:6E:F4:10' -> 'C02E1D')
    clean_mac = mac.replace(":", "").replace("-", "").upper()
    if len(clean_mac) >= 6:
        prefix = clean_mac[:6]
        vendor = await DatabaseManager.lookup_oui(prefix)
        return vendor if vendor else "Unknown"
    return "Unknown"

_consecutive_failures = 0
_circuit_open_until = 0.0

async def live_lookup_vendor(prefix: str):
    """Live fallback to api.macvendors.com for unknown network prefixes."""
    global _consecutive_failures, _circuit_open_until
    import time
    
    if time.time() < _circuit_open_until:
        return None
        
    url = f"https://api.macvendors.com/{prefix}"
    try:
        from config import config
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=config.macvendors_api_timeout)) as response:
                if response.status == 200:
                    _consecutive_failures = 0
                    text = await response.text(encoding="utf-8")
                    return text.strip()
                elif response.status == 404:
                    # Not an API outage, just not found
                    _consecutive_failures = 0
                    return None
                else:
                    _consecutive_failures += 1
                    if _consecutive_failures >= 3:
                        _circuit_open_until = time.time() + 300
                        logger.warning("macvendors.com API failed 3 times; opening circuit breaker for 5 minutes.")
                    elif response.status == 429:
                        logger.warning(f"macvendors.com rate limited on prefix {prefix}")
                    else:
                        logger.debug(f"macvendors.com returned HTTP {response.status} for {prefix}")
                    return None
    except asyncio.TimeoutError:
        _consecutive_failures += 1
        if _consecutive_failures >= 3:
            _circuit_open_until = time.time() + 300
            logger.warning("macvendors.com API timeout 3 times; opening circuit breaker for 5 minutes.")
        logger.debug(f"Timeout querying macvendors.com for {prefix}")
        return None
    except Exception as e:
        _consecutive_failures += 1
        if _consecutive_failures >= 3:
            _circuit_open_until = time.time() + 300
            logger.warning("macvendors.com API failed 3 times; opening circuit breaker for 5 minutes.")
        logger.debug(f"Exception querying macvendors.com for {prefix}: {e}")
        return None
