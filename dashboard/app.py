import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
from dashboard import db
from utils import metrics
from auth import check_password
from datetime import datetime
from config import config

st.set_page_config(page_title="OverwatcherPI Dashboard", layout="wide")

if not check_password():
    st.stop()

st.title("🛡 OverwatcherPI Live Overview")

@st.fragment(run_every="30s")
def live_overview():
    col1, col2 = st.columns(2)
    
    def format_vendor(v):
        if not v or v == "Unknown":
            return "❓ Unknown"
        elif str(v).startswith("Private"):
            return f"🎭 {v}"
        else:
            return f"✅ {v}"
            
    with col1:
        st.subheader("Network")
        with st.spinner("Fetching active network devices..."):
            net_df = db.get_active_network_devices()
        st.metric("Active Network Devices", len(net_df))
        if not net_df.empty:
            net_df['vendor_badge'] = net_df['vendor'].apply(format_vendor)
            st.dataframe(net_df[['ip', 'mac', 'vendor_badge', 'hostname', 'is_known']], width="stretch")
            
    with col2:
        st.subheader("Bluetooth")
        with st.spinner("Fetching active bluetooth devices..."):
            bt_df = db.get_active_bt_devices()
        st.metric("Active Bluetooth Devices (Last 1hr)", len(bt_df))
        if not bt_df.empty:
            bt_df['name_badge'] = bt_df['name'].apply(format_vendor)
            st.dataframe(bt_df[['address', 'name_badge', 'rssi']], width="stretch")

    st.subheader("System Health")
    with st.spinner("Fetching system health..."):
        health = metrics.get_system_status()
    h_col1, h_col2, h_col3, h_col4 = st.columns(4)
    cpu_percent = sum(health.cpu_per_core) / len(health.cpu_per_core) if health.cpu_per_core else 0
    mem_percent = (health.ram_used_mb / health.ram_total_mb * 100) if health.ram_total_mb else 0
    
    h_col1.metric("CPU Usage", f"{cpu_percent:.1f}%")
    
    if health.temp_celsius >= config.dashboard_temp_crit_c:
        temp_delta = "-Crit"
        temp_color = "inverse"
    elif health.temp_celsius >= config.dashboard_temp_warn_c:
        temp_delta = "-Warn"
        temp_color = "inverse"
    else:
        temp_delta = "Normal"
        temp_color = "normal"
        
    h_col2.metric("CPU Temp", f"{health.temp_celsius:.1f}°C", delta=temp_delta, delta_color=temp_color)
    h_col3.metric("Memory", f"{mem_percent:.1f}%")
    h_col4.metric("Disk", f"{health.disk_percent:.1f}%")
    
    if "Normal" not in health.throttling_status:
        st.warning(f"System Throttling Status: {health.throttling_status}")
        
    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

live_overview()

st.subheader("Scan History (Last 7 Days)")
with st.spinner("Fetching scan history..."):
    hist_df = db.get_scan_history(days=7)
if not hist_df.empty:
    st.line_chart(hist_df[['device_count']])
else:
    st.info("No scan history available yet.")
