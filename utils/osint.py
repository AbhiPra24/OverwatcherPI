import aiohttp
import logging

logger = logging.getLogger(__name__)

async def get_ip_info(ip: str) -> str:
    """Fetch Geo/ASN/Org info for an IP using ip-api.com"""
    if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
        return "Local Network"
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://ipinfo.io/{ip}/json", timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    country = data.get("country", "")
                    city = data.get("city", "")
                    org = data.get("org", "")
                    return f"Location: {city}, {country}\nOrg/ASN: {org}"
    except Exception as e:
        logger.error(f"IP OSINT lookup failed for {ip}: {e}")
        
    return "No OSINT data available"
