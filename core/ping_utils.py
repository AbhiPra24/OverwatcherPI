import asyncio
import re

async def ping_host(ip: str, count: int = 4) -> dict:
    """
    Ping a host and return statistics.
    Returns dict with: loss_percent, avg_ms, jitter_ms.
    If unreachable, loss_percent=100.
    """
    cmd = ["ping", "-c", str(count), "-q", ip]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    out = stdout.decode('utf-8', errors='ignore')
    
    loss_percent = 100.0
    avg_ms = 0.0
    jitter_ms = 0.0
    
    # "4 packets transmitted, 4 received, 0% packet loss, time 3004ms"
    loss_match = re.search(r'(\d+)% packet loss', out)
    if loss_match:
        loss_percent = float(loss_match.group(1))
        
    # "rtt min/avg/max/mdev = 1.102/1.305/1.554/0.170 ms"
    rtt_match = re.search(r'= ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms', out)
    if rtt_match:
        avg_ms = float(rtt_match.group(2))
        jitter_ms = float(rtt_match.group(4))
        
    return {
        "loss_percent": loss_percent,
        "avg_ms": avg_ms,
        "jitter_ms": jitter_ms
    }
