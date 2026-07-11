"""One-time data migration from SQLite to Supabase (Postgres).

Run via: docker compose run --rm bot python -m scripts.migrate_to_supabase [--truncate]

Reads every row from the live SQLite file, writes it to Supabase. Unlike
PortfolioPi's equivalent script, no timestamp-string parsing is needed here —
every timestamp column in this schema is a plain REAL Unix-epoch float, which
round-trips through asyncpg as a Python float with no representation change.

Safe to rerun with --truncate (wipes destination tables first, then reloads) —
used both for the Phase 2 rehearsal and the final authoritative load right
before the Phase 3 cutover. No foreign keys exist between these tables, so
migration order doesn't matter.
"""

import argparse
import asyncio
import logging
import sqlite3

import asyncpg

from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# (table_name, columns in migration order, order-by column(s), has_id [True if
# the table has a surrogate integer id column needing its identity sequence
# fixed after load])
TABLES = [
    ("network_devices", ["mac", "ip", "vendor", "hostname", "first_seen", "last_seen", "is_active",
                          "raw_mdns_name", "raw_ssdp_server", "raw_netbios_name", "is_known",
                          "banner_grab_attempted_at", "banner_grab_attempts", "friendly_name",
                          "device_type", "owner"], "mac", False),
    ("scan_history", ["id", "scan_time", "device_count"], "id", True),
    ("dns_queries", ["id", "timestamp", "src_ip", "query_name", "query_type"], "id", True),
    ("bt_devices", ["address", "name", "rssi", "last_seen", "manufacturer_data_hex", "service_uuids",
                     "is_known", "tx_power", "rssi_history", "fingerprint"], "address", False),
    ("oui_mappings", ["mac_prefix", "vendor"], "mac_prefix", False),
    ("monitored_hosts", ["ip", "is_active"], "ip", False),
    ("device_ports", ["mac", "port", "service", "first_seen", "last_seen", "is_active"], "mac, port", False),
    ("port_history", ["mac", "port", "service", "event", "timestamp"], "timestamp", False),
    ("events", ["id", "timestamp", "category", "severity", "message", "related_id"], "id", True),
    ("jobs", ["id", "job_type", "target", "status", "requester_chat_id", "created_at", "started_at",
               "finished_at", "result_summary", "result_path", "error"], "created_at", False),
    ("ble_alert_cooldown", ["vendor_key", "last_alert_at"], "vendor_key", False),
    ("honeypot_alert_cooldown", ["src_ip", "last_alert_at"], "src_ip", False),
    ("resource_alert_cooldown", ["metric_key", "last_alert_at"], "metric_key", False),
    ("latency_samples", ["id", "timestamp", "target", "loss_pct", "jitter_ms"], "id", True),
    ("deferred_scans", ["mac", "ip", "queued_at"], "mac", False),
    ("job_heartbeats", ["job_name", "last_run_at"], "job_name", False),
    ("device_maintenance", ["mac", "until_timestamp", "reason"], "mac", False),
]


async def migrate_table(pg_conn, sqlite_conn, table, columns, order_col, has_id, truncate):
    cur = sqlite_conn.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY {order_col}")
    rows = cur.fetchall()

    if truncate:
        await pg_conn.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")

    if not rows:
        logger.info(f"{table}: 0 rows in SQLite, nothing to migrate")
        return 0

    placeholders = ", ".join(f"${i + 1}" for i in range(len(columns)))
    insert_sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    await pg_conn.executemany(insert_sql, [tuple(row) for row in rows])

    if has_id:
        await pg_conn.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)"
        )

    logger.info(f"{table}: migrated {len(rows)} rows")
    return len(rows)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--truncate", action="store_true",
        help="Truncate destination tables before loading (makes the run idempotent/rerunnable)",
    )
    args = parser.parse_args()

    dsn = config.database_url.get_secret_value()
    if not dsn:
        raise SystemExit("DATABASE_URL is not set in .env")

    sqlite_path = str(config.db_path)
    logger.info(f"Reading from SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(sqlite_path)

    logger.info("Connecting to Supabase...")
    pg_conn = await asyncpg.connect(dsn=dsn)

    try:
        total = 0
        for table, columns, order_col, has_id in TABLES:
            total += await migrate_table(pg_conn, sqlite_conn, table, columns, order_col, has_id, args.truncate)
        logger.info(f"Migration complete. {total} total row(s) migrated across {len(TABLES)} tables.")
    finally:
        sqlite_conn.close()
        await pg_conn.close()


if __name__ == "__main__":
    asyncio.run(main())
