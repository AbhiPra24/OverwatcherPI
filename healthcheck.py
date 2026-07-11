import asyncio
import os
import sys
import time

import asyncpg


async def check():
    conn = await asyncpg.connect(dsn=os.environ["DATABASE_URL"])
    try:
        rows = await conn.fetch(
            "SELECT last_run_at FROM job_heartbeats WHERE job_name IN ('fast_sweep', 'service_watchdog', 'resource_health')"
        )
    finally:
        await conn.close()
    now = time.time()
    ok = len(rows) == 3 and all((now - r["last_run_at"]) < 900 for r in rows)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(check())
