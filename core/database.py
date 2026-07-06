import time
import logging
from dataclasses import dataclass
from typing import Optional, List, Tuple, Set

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


class BLEDevice(BaseModel):
    address: str
    name: str = "Unknown"
    rssi: int


class HourlyStats(BaseModel):
    avg_network_devices: float
    new_macs: List[str]
    gone_macs: List[str]
    ble_device_count: int


class DatabaseManager:
    """Singleton database manager handling connections and queries."""
    
    _db: Optional[aiosqlite.Connection] = None

    @classmethod
    async def get_db(cls) -> aiosqlite.Connection:
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
                is_active INTEGER DEFAULT 1
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
            CREATE TABLE IF NOT EXISTS bt_devices (
                address TEXT PRIMARY KEY,
                name TEXT,
                rssi INTEGER,
                last_seen REAL NOT NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS oui_mappings (
                mac_prefix TEXT PRIMARY KEY,
                vendor TEXT NOT NULL
            )
        """)
        
        await db.commit()
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
            INSERT INTO network_devices (mac, ip, vendor, hostname, first_seen, last_seen, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(mac) DO UPDATE SET
                ip = excluded.ip,
                vendor = excluded.vendor,
                hostname = CASE WHEN excluded.hostname != '' THEN excluded.hostname ELSE network_devices.hostname END,
                last_seen = excluded.last_seen,
                is_active = 1
        """, [(d.mac, d.ip, d.vendor, d.hostname, current_time, current_time) for d in devices])
        
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
    async def upsert_bt_devices(cls, devices: List[BLEDevice]):
        db = await cls.get_db()
        current_time = time.time()
        
        await db.executemany("""
            INSERT INTO bt_devices (address, name, rssi, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(address) DO UPDATE SET
                name = CASE WHEN excluded.name != 'Unknown' THEN excluded.name ELSE bt_devices.name END,
                rssi = excluded.rssi,
                last_seen = excluded.last_seen
        """, [(d.address, d.name, d.rssi, current_time) for d in devices])
        
        await db.commit()

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
        
        return HourlyStats(
            avg_network_devices=round(avg_count, 1),
            new_macs=new_macs,
            gone_macs=gone_macs,
            ble_device_count=bt_count
        )

    # OUI Cache Methods
    @classmethod
    async def oui_count(cls) -> int:
        db = await cls.get_db()
        cursor = await db.execute("SELECT COUNT(*) as count FROM oui_mappings")
        return (await cursor.fetchone())["count"]

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
