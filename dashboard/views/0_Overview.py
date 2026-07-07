import streamlit as st
import pandas as pd
from dashboard import db
from utils import metrics
from datetime import datetime
import time
from config import config

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
    
    if "Normal" not in health.throttling_status and "Not available" not in health.throttling_status:
        st.warning(f"System Throttling Status: {health.throttling_status}")
        
    st.subheader("Pipeline Health")
    with st.spinner("Fetching job heartbeats..."):
        jobs_df = db.get_job_heartbeats()
    if not jobs_df.empty:
        cols = st.columns(4)
        now = time.time()
        for idx, row in jobs_df.iterrows():
            col = cols[idx % 4]
            job_name = row['job_name']
            last_run = row['last_run_at']
            mins_ago = (now - last_run) / 60
            
            warn_threshold = 15
            if "fast_sweep" in job_name:
                warn_threshold = config.sweep_interval_minutes * 2
            elif "hourly" in job_name:
                warn_threshold = 120
            elif "speedtest" in job_name:
                warn_threshold = config.speedtest_interval_hours * 60 * 2
            elif "telegram_delivery" in job_name:
                warn_threshold = 180 # 3 hours (expecting at least hourly reports or periodic sweeps)
                
            icon = "✅" if mins_ago < warn_threshold else "⚠️"
            col.metric(f"{icon} {job_name}", f"{mins_ago:.1f}m ago")
            
    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

live_overview()
