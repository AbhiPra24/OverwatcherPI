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
            st.dataframe(net_df[['ip', 'mac', 'vendor', 'hostname', 'is_known']], use_container_width=True)
            
    with col2:
        st.subheader("Bluetooth")
        bt_df = db.get_active_bt_devices()
        st.metric("Active Bluetooth Devices (Last 1hr)", len(bt_df))
        if not bt_df.empty:
            st.dataframe(bt_df[['address', 'name', 'rssi']], use_container_width=True)

    st.subheader("System Health")
    health = metrics.get_system_status()
    h_col1, h_col2, h_col3, h_col4 = st.columns(4)
    h_col1.metric("CPU Usage", f"{health.get('cpu_percent', 0)}%")
    h_col2.metric("CPU Temp", f"{health.get('cpu_temp', 0)}°C")
    h_col3.metric("Memory", f"{health.get('memory_percent', 0)}%")
    h_col4.metric("Disk", f"{health.get('disk_percent', 0)}%")
    
    throttling = metrics.get_throttling_status()
    if throttling and throttling.get('throttled_now', False):
        st.warning("System is currently thermal throttling!")

live_overview()

st.subheader("Scan History (Last 7 Days)")
hist_df = db.get_scan_history(days=7)
if not hist_df.empty:
    st.line_chart(hist_df[['device_count', 'known_devices', 'unknown_devices']])
else:
    st.info("No scan history available yet.")
