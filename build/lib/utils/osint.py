import aiohttp
import logging
import asyncio
import time

logger = logging.getLogger(__name__)

_IP_CACHE = {}
CACHE_TTL = 86400

async def get_ip_info(ip: str) -> str:
    """Fetch Geo/ASN/Org info for an IP using ip-api.com"""
    if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
        return "Local Network"
        
    now = time.time()
    if ip in _IP_CACHE:
        val, ts = _IP_CACHE[ip]
        if now - ts < CACHE_TTL:
            return val
            
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://ip-api.com/json/{ip}", timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    country = data.get("country", "")
                    city = data.get("city", "")
                    org = data.get("org", "")
                    res = f"Location: {city}, {country}\nOrg/ASN: {org}"
                    _IP_CACHE[ip] = (res, now)
                    return res
    except Exception as e:
        logger.error(f"IP OSINT lookup failed for {ip}: {e}")
        
    return "No OSINT data available"

def get_ip_info_sync(ip: str) -> str:
    """Synchronous wrapper for Streamlit views."""
    if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
        return "Local Network"
        
    now = time.time()
    if ip in _IP_CACHE:
        val, ts = _IP_CACHE[ip]
        if now - ts < CACHE_TTL:
            return val
            
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(get_ip_info(ip))
    except Exception as e:
        logger.error(f"IP OSINT sync lookup failed for {ip}: {e}")
        return "No OSINT data available"
