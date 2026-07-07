import time
import json
import logging
from dataclasses import dataclass
from typing import Optional, List, Tuple, Set

import asyncio
import aiosqlite
from pydantic import BaseModel

from config import config

logger = logging.getLogger(__name__)


class NetworkDevice(BaseModel):
    ip: str
    mac: str
    vendor: str = "Unknown"
    hostname: str = ""
    is_new: bool = False
    raw_mdns_name: Optional[str] = None
    raw_ssdp_server: Optional[str] = None
    raw_netbios_name: Optional[str] = None


class BLEDevice(BaseModel):
    address: str
    name: str = "Unknown"
    rssi: int
    manufacturer_data_hex: Optional[str] = None
    service_uuids: Optional[str] = None
    tx_power: Optional[int] = None
    rssi_history: str = "[]"
    proximity: str = "Unknown"
    fingerprint: Optional[str] = None


class HourlyStats(BaseModel):
    avg_network_devices: float
    new_macs: List[str]
    gone_macs: List[str]
    ble_device_count: int
    unwhitelisted_count: int = 0


class DatabaseManager:
    """Singleton database manager handling connections and queries."""
    
    _db: Optional[aiosqlite.Connection] = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_db(cls) -> aiosqlite.Connection:
        if cls._db is None:
            async with cls._lock:
                if cls._db is None:
                    # Ensure directory exists
                    config.db_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    cls._db = await aiosqlite.connect(config.db_path)
                    cls._db.row_factory = aiosqlite.Row
                    
                    # Apply production pragmas (especially WAL mode for concurrent readers/writers)
                    await cls._db.execute("PRAGMA journal_mode=WAL;")
                    await cls._db.execute("PRAGMA synchronous=NORMAL;")
                    await cls._db.execute("PRAGMA foreign_keys=ON;")
                    await cls._db.execute("PRAGMA cache_size=-65536;")
                    await cls._db.commit()
                    
                    await cls._init_tables(cls._db)
            
        return cls._db

    @classmethod
    async def close(cls):
        if cls._db is not None:
            await cls._db.close()
            cls._db = None

    @staticmethod
    async def _init_tables(db: aiosqlite.Connection):
        """Create tables if they don't exist."""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS network_devices (
                mac TEXT PRIMARY KEY,
                ip TEXT,
                vendor TEXT,
                hostname TEXT,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                is_active INTEGER DEFAULT 1,
                raw_mdns_name TEXT,
                raw_ssdp_server TEXT,
                raw_netbios_name TEXT
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_time REAL NOT NULL,
                device_count INTEGER NOT NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dns_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                src_ip TEXT NOT NULL,
                query_name TEXT NOT NULL,
                query_type TEXT
            )
        """)
        
        await db.execute("CREATE INDEX IF NOT EXISTS idx_dns_queries_src_ts ON dns_queries(src_ip, timestamp)")
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bt_devices (
                address TEXT PRIMARY KEY,
                name TEXT,
                rssi INTEGER,
                last_seen REAL NOT NULL,
                manufacturer_data_hex TEXT,
                service_uuids TEXT
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS oui_mappings (
                mac_prefix TEXT PRIMARY KEY,
                vendor TEXT NOT NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS monitored_hosts (
                ip TEXT PRIMARY KEY,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS device_ports (
                mac TEXT,
                port INTEGER,
                service TEXT,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                is_active INTEGER DEFAULT 1,
                PRIMARY KEY (mac, port)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS port_history (
                mac TEXT,
                port INTEGER,
                service TEXT,
                event TEXT,
                timestamp REAL
            )
        """)
        
        await db.execute("CREATE INDEX IF NOT EXISTS idx_port_history_mac ON port_history(mac)")
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                related_id TEXT
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ble_alert_cooldown (
                vendor_key TEXT PRIMARY KEY,
                last_alert_at REAL NOT NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS honeypot_alert_cooldown (
                src_ip TEXT PRIMARY KEY,
                last_alert_at REAL NOT NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS resource_alert_cooldown (
                metric_key TEXT PRIMARY KEY,
                last_alert_at REAL NOT NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS latency_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                target TEXT NOT NULL,
                loss_pct REAL,
                jitter_ms REAL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS deferred_scans (
                mac TEXT PRIMARY KEY,
                ip TEXT NOT NULL,
                queued_at REAL NOT NULL
            )
        """)
        
        await db.commit()
        
        # Add is_known column if it doesn't exist (schema migration)
        cursor = await db.execute("PRAGMA table_info(network_devices)")
        cols = [row["name"] for row in await cursor.fetchall()]
        if "is_known" not in cols:
            await db.execute("ALTER TABLE network_devices ADD COLUMN is_known INTEGER DEFAULT 0")
        if "raw_mdns_name" not in cols:
            await db.execute("ALTER TABLE network_devices ADD COLUMN raw_mdns_name TEXT")
            await db.execute("ALTER TABLE network_devices ADD COLUMN raw_ssdp_server TEXT")
            await db.execute("ALTER TABLE network_devices ADD COLUMN raw_netbios_name TEXT")
        if "banner_grab_attempted_at" not in cols:
            await db.execute("ALTER TABLE network_devices ADD COLUMN banner_grab_attempted_at REAL")
            await db.execute("ALTER TABLE network_devices ADD COLUMN banner_grab_attempts INTEGER DEFAULT 0")
            
        await db.execute("""
            CREATE TABLE IF NOT EXISTS job_heartbeats (
                job_name TEXT PRIMARY KEY,
                last_run_at REAL
            )
        """)
            
        cursor = await db.execute("PRAGMA table_info(bt_devices)")
        cols = [row["name"] for row in await cursor.fetchall()]
        if "is_known" not in cols:
            await db.execute("ALTER TABLE bt_devices ADD COLUMN is_known INTEGER DEFAULT 0")
        if "manufacturer_data_hex" not in cols:
            await db.execute("ALTER TABLE bt_devices ADD COLUMN manufacturer_data_hex TEXT")
            await db.execute("ALTER TABLE bt_devices ADD COLUMN service_uuids TEXT")
        if "tx_power" not in cols:
            await db.execute("ALTER TABLE bt_devices ADD COLUMN tx_power INTEGER")
            await db.execute("ALTER TABLE bt_devices ADD COLUMN rssi_history TEXT DEFAULT '[]'")
        if "fingerprint" not in cols:
            await db.execute("ALTER TABLE bt_devices ADD COLUMN fingerprint TEXT")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_bt_devices_fingerprint ON bt_devices(fingerprint)")
            
        logger.info("Database tables initialized.")

    @classmethod
    async def upsert_network_devices(cls, devices: List[NetworkDevice]) -> Tuple[Set[str], Set[str]]:
        """
        Upsert a batch of devices.
        Returns a tuple: (set of newly discovered MACs, set of MACs that went offline).
        """
        db = await cls.get_db()
        current_time = time.time()
        current_macs = {d.mac for d in devices}
        
        # Determine newly discovered MACs
        cursor = await db.execute("SELECT mac FROM network_devices")
        known_macs = {row["mac"] for row in await cursor.fetchall()}
        new_macs = current_macs - known_macs
        
        # Upsert devices
        await db.executemany("""
            INSERT INTO network_devices (mac, ip, vendor, hostname, first_seen, last_seen, is_active, raw_mdns_name, raw_ssdp_server, raw_netbios_name)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(mac) DO UPDATE SET
                ip = excluded.ip,
                vendor = excluded.vendor,
                hostname = CASE WHEN excluded.hostname != '' THEN excluded.hostname ELSE network_devices.hostname END,
                last_seen = excluded.last_seen,
                is_active = 1,
                raw_mdns_name = CASE WHEN excluded.raw_mdns_name IS NOT NULL THEN excluded.raw_mdns_name ELSE network_devices.raw_mdns_name END,
                raw_ssdp_server = CASE WHEN excluded.raw_ssdp_server IS NOT NULL THEN excluded.raw_ssdp_server ELSE network_devices.raw_ssdp_server END,
                raw_netbios_name = CASE WHEN excluded.raw_netbios_name IS NOT NULL THEN excluded.raw_netbios_name ELSE network_devices.raw_netbios_name END
        """, [(d.mac, d.ip, d.vendor, d.hostname, current_time, current_time, d.raw_mdns_name, d.raw_ssdp_server, d.raw_netbios_name) for d in devices])
        
        # Mark missing devices as inactive
        if current_macs:
            placeholders = ",".join("?" * len(current_macs))
            query = f"SELECT mac FROM network_devices WHERE is_active = 1 AND mac NOT IN ({placeholders})"
            cursor = await db.execute(query, list(current_macs))
            gone_macs = {row["mac"] for row in await cursor.fetchall()}
            
            await db.execute(f"UPDATE network_devices SET is_active = 0 WHERE mac NOT IN ({placeholders})", list(current_macs))
        else:
            # Everything is gone
            cursor = await db.execute("SELECT mac FROM network_devices WHERE is_active = 1")
            gone_macs = {row["mac"] for row in await cursor.fetchall()}
            await db.execute("UPDATE network_devices SET is_active = 0")

        # Record scan history
        await db.execute(
            "INSERT INTO scan_history (scan_time, device_count) VALUES (?, ?)", 
            (current_time, len(devices))
        )
        
        await db.commit()
        
        for d in devices:
            if d.mac in new_macs:
                d.is_new = True
                
        return new_macs, gone_macs

    @classmethod
    async def get_active_devices(cls) -> List[NetworkDevice]:
        """Get all currently active devices."""
        db = await cls.get_db()
        cursor = await db.execute("""
            SELECT mac, ip, vendor, hostname 
            FROM network_devices 
            WHERE is_active = 1
            ORDER BY ip
        """)
        rows = await cursor.fetchall()
        return [NetworkDevice(mac=r["mac"], ip=r["ip"], vendor=r["vendor"], hostname=r["hostname"]) for r in rows]

    @classmethod
    async def upsert_bt_devices(cls, devices: List[BLEDevice]) -> Set[str]:
        db = await cls.get_db()
        current_time = time.time()
        current_macs = {d.address for d in devices}
        
        cursor = await db.execute("SELECT address FROM bt_devices")
        known_macs = {row["address"] for row in await cursor.fetchall()}
        new_macs = current_macs - known_macs
        
        existing_histories = {}
        if current_macs:
            placeholders = ",".join("?" * len(current_macs))
            cursor = await db.execute(f"SELECT address, rssi_history FROM bt_devices WHERE address IN ({placeholders})", list(current_macs))
            for row in await cursor.fetchall():
                try:
                    existing_histories[row["address"]] = json.loads(row["rssi_history"] or "[]")
                except json.JSONDecodeError:
                    existing_histories[row["address"]] = []

        upsert_data = []
        for d in devices:
            hist = existing_histories.get(d.address, [])
            hist.append(d.rssi)
            hist = hist[-5:]  # Keep last 5 samples
            d.rssi_history = json.dumps(hist)
            upsert_data.append((d.address, d.name, d.rssi, current_time, d.manufacturer_data_hex, d.service_uuids, d.tx_power, d.rssi_history, d.fingerprint))

        await db.executemany("""
            INSERT INTO bt_devices (address, name, rssi, last_seen, manufacturer_data_hex, service_uuids, tx_power, rssi_history, fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(address) DO UPDATE SET
                name = CASE WHEN excluded.name != 'Unknown' AND excluded.name != '' THEN excluded.name ELSE bt_devices.name END,
                rssi = excluded.rssi,
                last_seen = excluded.last_seen,
                manufacturer_data_hex = CASE WHEN excluded.manufacturer_data_hex IS NOT NULL THEN excluded.manufacturer_data_hex ELSE bt_devices.manufacturer_data_hex END,
                service_uuids = CASE WHEN excluded.service_uuids IS NOT NULL THEN excluded.service_uuids ELSE bt_devices.service_uuids END,
                tx_power = excluded.tx_power,
                rssi_history = excluded.rssi_history,
                fingerprint = CASE WHEN excluded.fingerprint IS NOT NULL THEN excluded.fingerprint ELSE bt_devices.fingerprint END
        """, upsert_data)
        
        await db.commit()
        return new_macs

    @classmethod
    async def mark_known(cls, mac: str) -> bool:
        db = await cls.get_db()
        cur1 = await db.execute("UPDATE network_devices SET is_known = 1 WHERE mac = ?", (mac,))
        cur2 = await db.execute("UPDATE bt_devices SET is_known = 1 WHERE address = ?", (mac,))
        await db.commit()
        return cur1.rowcount > 0 or cur2.rowcount > 0
        
    @classmethod
    async def is_known(cls, mac: str) -> bool:
        db = await cls.get_db()
        cur1 = await db.execute("SELECT is_known FROM network_devices WHERE mac = ?", (mac,))
        row1 = await cur1.fetchone()
        if row1 and row1["is_known"] == 1:
            return True
            
        cur2 = await db.execute("SELECT is_known FROM bt_devices WHERE address = ?", (mac,))
        row2 = await cur2.fetchone()
        if row2 and row2["is_known"] == 1:
            return True
            
        return False

    @classmethod
    async def was_fingerprint_seen_recently(cls, fingerprint: str, hours: float = 24.0) -> bool:
        if not fingerprint:
            return False
        db = await cls.get_db()
        cutoff = time.time() - (hours * 3600)
        cursor = await db.execute("SELECT 1 FROM bt_devices WHERE fingerprint = ? AND last_seen >= ? LIMIT 1", (fingerprint, cutoff))
        return await cursor.fetchone() is not None

    @classmethod
    async def get_hourly_stats(cls, hours: int = 1) -> HourlyStats:
        """Compute network statistics over the last `hours` window."""
        db = await cls.get_db()
        cutoff_time = time.time() - (hours * 3600)
        
        # Avg devices over the period
        cursor = await db.execute(
            "SELECT AVG(device_count) as avg_count FROM scan_history WHERE scan_time >= ?", 
            (cutoff_time,)
        )
        row = await cursor.fetchone()
        avg_count = row["avg_count"] if row and row["avg_count"] is not None else 0.0
        
        # New devices in this window (first_seen in the window)
        cursor = await db.execute(
            "SELECT mac FROM network_devices WHERE first_seen >= ?", 
            (cutoff_time,)
        )
        new_macs = [r["mac"] for r in await cursor.fetchall()]
        
        # Gone devices (inactive, and last seen in the window but not currently active)
        cursor = await db.execute(
            "SELECT mac FROM network_devices WHERE is_active = 0 AND last_seen >= ?", 
            (cutoff_time,)
        )
        gone_macs = [r["mac"] for r in await cursor.fetchall()]
        
        # BT devices seen in window
        cursor = await db.execute(
            "SELECT COUNT(address) as count FROM bt_devices WHERE last_seen >= ?",
            (cutoff_time,)
        )
        bt_count = (await cursor.fetchone())["count"]
        
        # Active unwhitelisted devices
        cursor = await db.execute("SELECT COUNT(*) as count FROM network_devices WHERE is_active = 1 AND is_known = 0")
        unwhitelisted_count = (await cursor.fetchone())["count"]
        
        return HourlyStats(
            avg_network_devices=round(avg_count, 1),
            new_macs=new_macs,
            gone_macs=gone_macs,
            ble_device_count=bt_count,
            unwhitelisted_count=unwhitelisted_count
        )

    # OUI Cache Methods
    @classmethod
    async def oui_count(cls) -> int:
        db = await cls.get_db()
        cursor = await db.execute("SELECT COUNT(*) as count FROM oui_mappings")
        return (await cursor.fetchone())["count"]

    @classmethod
    async def add_monitored_host(cls, ip: str) -> bool:
        db = await cls.get_db()
        await db.execute("INSERT OR REPLACE INTO monitored_hosts (ip, is_active) VALUES (?, 1)", (ip,))
        await db.commit()
        return True

    @classmethod
    async def remove_monitored_host(cls, ip: str) -> bool:
        db = await cls.get_db()
        cur = await db.execute("UPDATE monitored_hosts SET is_active = 0 WHERE ip = ?", (ip,))
        await db.commit()
        return cur.rowcount > 0

    @classmethod
    async def get_monitored_hosts(cls) -> List[str]:
        db = await cls.get_db()
        cur = await db.execute("SELECT ip FROM monitored_hosts WHERE is_active = 1")
        return [r["ip"] for r in await cur.fetchall()]

    @classmethod
    async def bulk_insert_oui(cls, mappings: List[Tuple[str, str]]):
        db = await cls.get_db()
        await db.executemany(
            "INSERT OR REPLACE INTO oui_mappings (mac_prefix, vendor) VALUES (?, ?)", 
            mappings
        )
        await db.commit()

    @classmethod
    async def lookup_oui(cls, mac_prefix: str) -> Optional[str]:
        db = await cls.get_db()
        cursor = await db.execute(
            "SELECT vendor FROM oui_mappings WHERE mac_prefix = ?", 
            (mac_prefix,)
        )
        row = await cursor.fetchone()
        return row["vendor"] if row else None

    @classmethod
    async def get_device_ports(cls, mac: str) -> List[dict]:
        db = await cls.get_db()
        cursor = await db.execute("SELECT port, service, is_active FROM device_ports WHERE mac = ?", (mac,))
        return [dict(row) for row in await cursor.fetchall()]

    @classmethod
    async def upsert_device_ports(cls, mac: str, ports: List[dict]) -> List[dict]:
        """
        ports: list of dicts with 'port' and 'service'
        Returns a list of NEW ports that appeared.
        """
        db = await cls.get_db()
        current_time = time.time()
        
        cursor = await db.execute("SELECT port, service, is_active FROM device_ports WHERE mac = ?", (mac,))
        existing_ports = {row["port"]: row for row in await cursor.fetchall()}
        
        new_ports = []
        upsert_data = []
        history_inserts = []
        
        for p in ports:
            port = p["port"]
            service = p["service"]
            upsert_data.append((mac, port, service, current_time, current_time))
            if port not in existing_ports or existing_ports[port]["is_active"] == 0:
                new_ports.append(p)
                history_inserts.append((mac, port, service, "opened", current_time))
                
        if upsert_data:
            await db.executemany("""
                INSERT INTO device_ports (mac, port, service, first_seen, last_seen, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(mac, port) DO UPDATE SET
                    service = excluded.service,
                    last_seen = excluded.last_seen,
                    is_active = 1
            """, upsert_data)
            
        current_port_nums = {p["port"] for p in ports}
        gone_ports = [p for p in existing_ports if existing_ports[p]["is_active"] == 1 and p not in current_port_nums]
        if gone_ports:
            placeholders = ",".join("?" * len(gone_ports))
            await db.execute(f"UPDATE device_ports SET is_active = 0 WHERE mac = ? AND port IN ({placeholders})", [mac] + gone_ports)
            for gp in gone_ports:
                history_inserts.append((mac, gp, existing_ports[gp]["service"], "closed", current_time))
                
        if history_inserts:
            await db.executemany("INSERT INTO port_history (mac, port, service, event, timestamp) VALUES (?, ?, ?, ?, ?)", history_inserts)
            
        await db.commit()
        return new_ports

    @classmethod
    async def log_event(cls, category: str, severity: str, message: str, related_id: Optional[str] = None):
        """Log an event/alert to the database for the dashboard."""
        db = await cls.get_db()
        await db.execute(
            "INSERT INTO events (timestamp, category, severity, message, related_id) VALUES (?, ?, ?, ?, ?)",
            (time.time(), category, severity, message, related_id)
        )
        await db.commit()

    @classmethod
    async def get_devices_needing_banner_grab(cls) -> List[NetworkDevice]:
        db = await cls.get_db()
        current_time = time.time()
        
        query = """
            SELECT mac, ip, vendor, hostname, banner_grab_attempted_at, banner_grab_attempts
            FROM network_devices 
            WHERE is_active = 1 
            AND vendor = 'Unknown' 
            AND hostname = ''
        """
        cursor = await db.execute(query)
        rows = await cursor.fetchall()
        
        devices = []
        for r in rows:
            attempts = r["banner_grab_attempts"] or 0
            last_attempt = r["banner_grab_attempted_at"]
            
            if last_attempt is None:
                devices.append(NetworkDevice(mac=r["mac"], ip=r["ip"], vendor=r["vendor"], hostname=r["hostname"]))
                continue
                
            cooldown_hours = min(168, 2 ** attempts)
            if current_time - last_attempt >= cooldown_hours * 3600:
                devices.append(NetworkDevice(mac=r["mac"], ip=r["ip"], vendor=r["vendor"], hostname=r["hostname"]))
                
        return devices

    @classmethod
    async def record_banner_grab_attempt(cls, mac: str, resolved: bool, hostname: str = ""):
        db = await cls.get_db()
        current_time = time.time()
        
        if resolved and hostname:
            await db.execute("""
                UPDATE network_devices 
                SET banner_grab_attempted_at = ?, 
                    banner_grab_attempts = banner_grab_attempts + 1,
                    hostname = ?
                WHERE mac = ?
            """, (current_time, hostname, mac))
        else:
            await db.execute("""
                UPDATE network_devices 
                SET banner_grab_attempted_at = ?, 
                    banner_grab_attempts = banner_grab_attempts + 1
                WHERE mac = ?
            """, (current_time, mac))
            
        await db.commit()

    @classmethod
    async def should_alert_ble_vendor(cls, vendor_key: str, cooldown_hours: float) -> bool:
        db = await cls.get_db()
        current_time = time.time()
        
        cursor = await db.execute("SELECT last_alert_at FROM ble_alert_cooldown WHERE vendor_key = ?", (vendor_key,))
        row = await cursor.fetchone()
        
        if row is None or (current_time - row["last_alert_at"]) >= (cooldown_hours * 3600):
            await db.execute(
                "INSERT INTO ble_alert_cooldown (vendor_key, last_alert_at) VALUES (?, ?) ON CONFLICT(vendor_key) DO UPDATE SET last_alert_at = excluded.last_alert_at",
                (vendor_key, current_time)
            )
            await db.commit()
            return True
            
        return False

    @classmethod
    async def should_alert_honeypot(cls, src_ip: str, cooldown_seconds: float) -> bool:
        db = await cls.get_db()
        current_time = time.time()
        
        cursor = await db.execute("SELECT last_alert_at FROM honeypot_alert_cooldown WHERE src_ip = ?", (src_ip,))
        row = await cursor.fetchone()
        
        if row is None or (current_time - row["last_alert_at"]) >= cooldown_seconds:
            await db.execute(
                "INSERT INTO honeypot_alert_cooldown (src_ip, last_alert_at) VALUES (?, ?) ON CONFLICT(src_ip) DO UPDATE SET last_alert_at = excluded.last_alert_at",
                (src_ip, current_time)
            )
            await db.commit()
            return True
            
        return False

    @classmethod
    async def should_alert_resource(cls, metric_key: str, cooldown_hours: float) -> bool:
        db = await cls.get_db()
        current_time = time.time()
        
        cursor = await db.execute("SELECT last_alert_at FROM resource_alert_cooldown WHERE metric_key = ?", (metric_key,))
        row = await cursor.fetchone()
        
        if row is None or (current_time - row["last_alert_at"]) >= (cooldown_hours * 3600):
            await db.execute(
                "INSERT INTO resource_alert_cooldown (metric_key, last_alert_at) VALUES (?, ?) ON CONFLICT(metric_key) DO UPDATE SET last_alert_at = excluded.last_alert_at",
                (metric_key, current_time)
            )
            await db.commit()
            return True
            
        return False

    @classmethod
    async def queue_deferred_scan(cls, mac: str, ip: str):
        import time
        db = await cls.get_db()
        await db.execute("INSERT OR REPLACE INTO deferred_scans (mac, ip, queued_at) VALUES (?, ?, ?)", (mac, ip, time.time()))
        await db.commit()

    @classmethod
    async def get_due_deferred_scans(cls) -> List[Tuple[str, str]]:
        db = await cls.get_db()
        cursor = await db.execute("SELECT mac, ip FROM deferred_scans")
        rows = await cursor.fetchall()
        return [(r["mac"], r["ip"]) for r in rows]

    @classmethod
    async def remove_deferred_scan(cls, mac: str):
        db = await cls.get_db()
        await db.execute("DELETE FROM deferred_scans WHERE mac = ?", (mac,))
        await db.commit()

    @classmethod
    async def log_latency_sample(cls, target: str, loss_pct: float, jitter_ms: float):
        db = await cls.get_db()
        await db.execute(
            "INSERT INTO latency_samples (timestamp, target, loss_pct, jitter_ms) VALUES (?, ?, ?, ?)",
            (time.time(), target, loss_pct, jitter_ms)
        )
        await db.commit()

    @classmethod
    async def cache_oui_entry(cls, prefix: str, vendor: str):
        await cls.bulk_insert_oui([(prefix, vendor)])

    @classmethod
    async def update_device_vendor(cls, mac: str, vendor: str):
        db = await cls.get_db()
        await db.execute("UPDATE network_devices SET vendor = ? WHERE mac = ?", (vendor, mac))
        await db.commit()

    @classmethod
    async def record_scan_heartbeat(cls, job_name: str):
        import time
        db = await cls.get_db()
        await db.execute(
            "INSERT INTO job_heartbeats (job_name, last_run_at) VALUES (?, ?) ON CONFLICT(job_name) DO UPDATE SET last_run_at=excluded.last_run_at",
            (job_name, time.time())
        )
        await db.commit()

    @classmethod
    async def insert_dns_queries(cls, queries: List[Tuple[float, str, str, str]]):
        """Batch insert DNS queries (timestamp, src_ip, query_name, query_type)."""
        db = await cls.get_db()
        await db.executemany(
            "INSERT INTO dns_queries (timestamp, src_ip, query_name, query_type) VALUES (?, ?, ?, ?)",
            queries
        )
        await db.commit()

    @classmethod
    async def get_recent_dns_queries(cls, ip: str, limit: int = 50) -> List[dict]:
        db = await cls.get_db()
        cursor = await db.execute("""
            SELECT query_name, MAX(timestamp) as last_seen, query_type
            FROM dns_queries
            WHERE src_ip = ?
            GROUP BY query_name
            ORDER BY last_seen DESC
            LIMIT ?
        """, (ip, limit))
        return [dict(row) for row in await cursor.fetchall()]
