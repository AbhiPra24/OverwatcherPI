import sqlite3
import pandas as pd
from pathlib import Path
import time

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "netmon.db"

def get_connection():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

def get_active_network_devices() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query("SELECT * FROM network_devices WHERE is_active = 1", conn)

def get_all_network_devices() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query("SELECT * FROM network_devices", conn)

def get_active_bt_devices() -> pd.DataFrame:
    active_cutoff = time.time() - 3600 # 1 hour
    with get_connection() as conn:
        return pd.read_sql_query(f"SELECT * FROM bt_devices WHERE last_seen >= {active_cutoff}", conn)

def get_all_bt_devices() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query("SELECT * FROM bt_devices", conn)

def get_scan_history(days: int = 7) -> pd.DataFrame:
    cutoff = time.time() - (days * 86400)
    with get_connection() as conn:
        df = pd.read_sql_query(f"SELECT scan_time, device_count FROM scan_history WHERE scan_time >= {cutoff} ORDER BY scan_time ASC", conn)
        if not df.empty:
            df['datetime'] = pd.to_datetime(df['scan_time'], unit='s')
            df.set_index('datetime', inplace=True)
        return df

def get_events(limit: int = 200, category: str = None) -> pd.DataFrame:
    with get_connection() as conn:
        query = "SELECT timestamp, category, severity, message, related_id FROM events"
        params = []
        if category and category != "All":
            query += " WHERE category = ?"
            params.append(category)
        query += f" ORDER BY timestamp DESC LIMIT {limit}"
        df = pd.read_sql_query(query, conn, params=params)
        if not df.empty:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        return df
