import os
import time
import pandas as pd
import psycopg2
import psycopg2.pool
import streamlit as st
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL")

@st.cache_resource
def get_connection_pool():
    return psycopg2.pool.ThreadedConnectionPool(1, 5, dsn=DATABASE_URL)

@contextmanager
def get_connection():
    pool = get_connection_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)

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
                return pd.read_sql_query("SELECT * FROM network_devices WHERE last_seen >= %s", conn, params=(cutoff,))
            return pd.read_sql_query("SELECT * FROM network_devices", conn)
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_active_bt_devices() -> pd.DataFrame:
    try:
        active_cutoff = time.time() - 3600 # 1 hour
        with get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM bt_devices WHERE last_seen >= %s", conn, params=(active_cutoff,))
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_all_bt_devices(days: int = 90) -> pd.DataFrame:
    try:
        with get_connection() as conn:
            if days > 0:
                cutoff = time.time() - (days * 86400)
                return pd.read_sql_query("SELECT * FROM bt_devices WHERE last_seen >= %s", conn, params=(cutoff,))
            return pd.read_sql_query("SELECT * FROM bt_devices", conn)
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_scan_history(days: int = 7) -> pd.DataFrame:
    try:
        cutoff = time.time() - (days * 86400)
        with get_connection() as conn:
            df = pd.read_sql_query("SELECT scan_time, device_count FROM scan_history WHERE scan_time >= %s ORDER BY scan_time ASC", conn, params=(cutoff,))
            if not df.empty:
                df['datetime'] = pd.to_datetime(df['scan_time'], unit='s')
                df.set_index('datetime', inplace=True)
            return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_events(limit: int = 200, category: str = None, grouped: bool = False) -> pd.DataFrame:
    try:
        with get_connection() as conn:
            params = []
            if grouped:
                query = """
                    SELECT category, MAX(severity) as severity, message, related_id,
                           MIN(timestamp) as first_seen, MAX(timestamp) as last_seen, COUNT(*) as count
                    FROM events
                """
                if category and category != "All":
                    query += " WHERE category = %s"
                    params.append(category)
                query += " GROUP BY category, message, related_id ORDER BY last_seen DESC LIMIT %s"
                params.append(limit)
            else:
                query = "SELECT timestamp, category, severity, message, related_id FROM events"
                if category and category != "All":
                    query += " WHERE category = %s"
                    params.append(category)
                query += " ORDER BY timestamp DESC LIMIT %s"
                params.append(limit)

            df = pd.read_sql_query(query, conn, params=params)

            if not df.empty:
                if grouped:
                    df['first_seen'] = pd.to_datetime(df['first_seen'], unit='s')
                    df['last_seen'] = pd.to_datetime(df['last_seen'], unit='s')
                else:
                    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_latency_history(hours: int = 24) -> pd.DataFrame:
    try:
        cutoff = time.time() - (hours * 3600)
        with get_connection() as conn:
            df = pd.read_sql_query("SELECT timestamp, target, loss_pct, jitter_ms FROM latency_samples WHERE timestamp >= %s ORDER BY timestamp ASC", conn, params=(cutoff,))
            if not df.empty:
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

def get_job_heartbeats() -> pd.DataFrame:
    """Fetch pipeline job heartbeats."""
    with get_connection() as conn:
        try:
            return pd.read_sql_query("SELECT * FROM job_heartbeats", conn)
        except Exception as e:
            return pd.DataFrame(columns=["job_name", "last_run_at"])

@st.cache_data(ttl=30)
def get_device_ports(mac: str) -> pd.DataFrame:
    try:
        with get_connection() as conn:
            df = pd.read_sql_query("SELECT port, service, first_seen, last_seen, is_active FROM device_ports WHERE mac = %s", conn, params=(mac,))
            if not df.empty:
                df['first_seen'] = pd.to_datetime(df['first_seen'], unit='s')
                df['last_seen'] = pd.to_datetime(df['last_seen'], unit='s')
            return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_device_events(mac: str) -> pd.DataFrame:
    try:
        with get_connection() as conn:
            df = pd.read_sql_query("SELECT timestamp, category, severity, message FROM events WHERE related_id = %s ORDER BY timestamp DESC", conn, params=(mac,))
            if not df.empty:
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_device_port_history(mac: str) -> pd.DataFrame:
    try:
        with get_connection() as conn:
            df = pd.read_sql_query("SELECT port, service, event, timestamp FROM port_history WHERE mac = %s ORDER BY timestamp DESC", conn, params=(mac,))
            if not df.empty:
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_device_dns_queries(ip: str, limit: int = 100) -> pd.DataFrame:
    try:
        with get_connection() as conn:
            df = pd.read_sql_query(
                "SELECT timestamp, query_name, query_type FROM dns_queries WHERE src_ip = %s ORDER BY timestamp DESC LIMIT %s",
                conn, params=(ip, limit)
            )
            if not df.empty:
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_security_posture(days: int = 7) -> dict:
    import time
    try:
        cutoff = time.time() - (days * 86400)
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as count FROM network_devices WHERE is_active = 1 AND is_known = 0")
            unwhitelisted = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) as count FROM events WHERE category = 'network' AND message LIKE 'Port Drift Alert%%' AND timestamp >= %s", (cutoff,))
            port_drift = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) as count FROM events WHERE category = 'security' AND (message LIKE '%%DHCP%%' OR message LIKE '%%ARP%%') AND timestamp >= %s", (cutoff,))
            rogue_network = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) as count FROM events WHERE category = 'security' AND message LIKE '%%SSH%%' AND timestamp >= %s", (cutoff,))
            ssh_events = cur.fetchone()[0]

            return {
                "unwhitelisted_active": unwhitelisted,
                "port_drift_weekly": port_drift,
                "rogue_network_weekly": rogue_network,
                "ssh_events_weekly": ssh_events
            }
    except Exception as e:
        st.error(f"Database error: {e}")
        return {}

def get_device_maintenance(mac: str) -> dict:
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT until_timestamp, reason FROM device_maintenance WHERE mac = %s", (mac,))
            row = cur.fetchone()
            if row and row[0] > time.time():
                return {"until_timestamp": row[0], "reason": row[1]}
    except Exception:
        pass
    return {}
