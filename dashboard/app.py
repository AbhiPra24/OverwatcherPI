import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
from dashboard import db
from utils import metrics

st.set_page_config(page_title="OverwatcherPI Dashboard", layout="wide")

st.title("🛡 OverwatcherPI Live Overview")

@st.fragment(run_every="30s")
def live_overview():
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Network")
        net_df = db.get_active_network_devices()
        st.metric("Active Network Devices", len(net_df))
        if not net_df.empty:
            st.dataframe(net_df[['ip', 'mac', 'vendor', 'hostname', 'is_known']], width="stretch")
            
    with col2:
        st.subheader("Bluetooth")
        bt_df = db.get_active_bt_devices()
        st.metric("Active Bluetooth Devices (Last 1hr)", len(bt_df))
        if not bt_df.empty:
            st.dataframe(bt_df[['address', 'name', 'rssi']], width="stretch")

    st.subheader("System Health")
    health = metrics.get_system_status()
    h_col1, h_col2, h_col3, h_col4 = st.columns(4)
    cpu_percent = sum(health.cpu_per_core) / len(health.cpu_per_core) if health.cpu_per_core else 0
    mem_percent = (health.ram_used_mb / health.ram_total_mb * 100) if health.ram_total_mb else 0
    
    h_col1.metric("CPU Usage", f"{cpu_percent:.1f}%")
    h_col2.metric("CPU Temp", f"{health.temp_celsius:.1f}°C")
    h_col3.metric("Memory", f"{mem_percent:.1f}%")
    h_col4.metric("Disk", f"{health.disk_percent:.1f}%")
    
    if "Normal" not in health.throttling_status:
        st.warning(f"System Throttling Status: {health.throttling_status}")

live_overview()

st.subheader("Scan History (Last 7 Days)")
hist_df = db.get_scan_history(days=7)
if not hist_df.empty:
    st.line_chart(hist_df[['device_count']])
else:
    st.info("No scan history available yet.")
