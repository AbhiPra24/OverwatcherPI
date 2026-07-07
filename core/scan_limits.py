import asyncio
from config import config

NMAP_SEMAPHORE = asyncio.Semaphore(config.max_concurrent_scans)
