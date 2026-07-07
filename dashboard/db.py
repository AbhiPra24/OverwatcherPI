import sqlite3
import pandas as pd
import time
import streamlit as st
import sys
from pathlib import Path

# Import config from the main app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import config

DB_PATH = config.db_path

def get_connection():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

@st.cache_data(ttl=30)
def get_active_network_devices() -> pd.DataFrame:
    try:
        with get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM network_devices WHERE is_active = 1", conn)
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_all_network_devices(days: int = 90) -> pd.DataFrame:
    try:
        with get_connection() as conn:
            if days > 0:
                cutoff = time.time() - (days * 86400)
                return pd.read_sql_query("SELECT * FROM network_devices WHERE last_seen >= ?", conn, params=(cutoff,))
            return pd.read_sql_query("SELECT * FROM network_devices", conn)
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_active_bt_devices() -> pd.DataFrame:
    try:
        active_cutoff = time.time() - 3600 # 1 hour
        with get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM bt_devices WHERE last_seen >= ?", conn, params=(active_cutoff,))
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_all_bt_devices(days: int = 90) -> pd.DataFrame:
    try:
        with get_connection() as conn:
            if days > 0:
                cutoff = time.time() - (days * 86400)
                return pd.read_sql_query("SELECT * FROM bt_devices WHERE last_seen >= ?", conn, params=(cutoff,))
            return pd.read_sql_query("SELECT * FROM bt_devices", conn)
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_scan_history(days: int = 7) -> pd.DataFrame:
    try:
        cutoff = time.time() - (days * 86400)
        with get_connection() as conn:
            df = pd.read_sql_query("SELECT scan_time, device_count FROM scan_history WHERE scan_time >= ? ORDER BY scan_time ASC", conn, params=(cutoff,))
            if not df.empty:
                df['datetime'] = pd.to_datetime(df['scan_time'], unit='s')
                df.set_index('datetime', inplace=True)
            return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_events(limit: int = 200, category: str = None) -> pd.DataFrame:
    try:
        with get_connection() as conn:
            query = "SELECT timestamp, category, severity, message, related_id FROM events"
            params = []
            if category and category != "All":
                query += " WHERE category = ?"
                params.append(category)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            df = pd.read_sql_query(query, conn, params=params)
            if not df.empty:
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()
