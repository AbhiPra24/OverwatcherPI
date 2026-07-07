import asyncio
import socket
import logging

logger = logging.getLogger(__name__)

async def discover(timeout: float = 3.0) -> dict:
    """
    Run an SSDP M-SEARCH and return a mapping of IP -> server string.
    """
    results = {}
    
    # SSDP multicast address and port
    SSDP_ADDR = "239.255.255.250"
    SSDP_PORT = 1900
    
    msearch_query = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
        "MAN: \"ssdp:discover\"\r\n"
        "MX: 1\r\n"
        "ST: ssdp:all\r\n"
        "\r\n"
    )
    
    class SSDPProtocol(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr):
            ip = addr[0]
            try:
                text = data.decode('utf-8', errors='ignore')
                for line in text.splitlines():
                    if line.upper().startswith("SERVER:"):
                        server_val = line[7:].strip()
                        if ip not in results or len(server_val) > len(results.get(ip, "")):
                            results[ip] = server_val
            except Exception:
                pass
                
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: SSDPProtocol(),
        family=socket.AF_INET
    )
    
    try:
        # Send multicast
        transport.sendto(msearch_query.encode(), (SSDP_ADDR, SSDP_PORT))
        await asyncio.sleep(timeout)
    except Exception as e:
        logger.error(f"SSDP discovery failed: {e}")
    finally:
        transport.close()
        
    return results
