import streamlit as st
import pandas as pd
from dashboard import db

st.title("📈 Long-Term Trends")

days = st.selectbox("Time Range", [7, 30, 90], format_func=lambda x: f"Last {x} Days")

st.markdown("### Network Device Topology")
with st.spinner("Fetching scan history..."):
    hist_df = db.get_scan_history(days=days)
    
if not hist_df.empty:
    st.line_chart(hist_df[['device_count']], use_container_width=True)
else:
    st.info(f"No scan history available for the last {days} days.")

st.divider()

st.markdown("### Network Quality & Latency")
with st.spinner("Fetching latency history..."):
    lat_df = db.get_latency_history(hours=days * 24)

if not lat_df.empty:
    # Separate dataframes by target
    gw_df = lat_df[lat_df['target'] == 'gateway'].set_index('datetime')
    wan_df = lat_df[lat_df['target'] == 'wan'].set_index('datetime')
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Packet Loss (%)")
        loss_data = pd.DataFrame()
        if not gw_df.empty:
            loss_data['Gateway'] = gw_df['loss_pct']
        if not wan_df.empty:
            loss_data['WAN (1.1.1.1)'] = wan_df['loss_pct']
            
        if not loss_data.empty:
            st.line_chart(loss_data, use_container_width=True)
        else:
            st.info("No packet loss data available.")
            
    with col2:
        st.markdown("#### Jitter (ms)")
        jitter_data = pd.DataFrame()
        if not gw_df.empty:
            jitter_data['Gateway'] = gw_df['jitter_ms']
        if not wan_df.empty:
            jitter_data['WAN (1.1.1.1)'] = wan_df['jitter_ms']
            
        if not jitter_data.empty:
            st.line_chart(jitter_data, use_container_width=True)
        else:
            st.info("No jitter data available.")
else:
    st.info(f"No latency metrics have been recorded for the last {days} days. (This feature was just enabled recently).")
