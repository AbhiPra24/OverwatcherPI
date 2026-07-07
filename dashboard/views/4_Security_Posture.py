import streamlit as st
import pandas as pd
from dashboard import db

st.title("🔒 Security Posture")

col1, col2 = st.columns(2)
with col1:
    days = st.number_input("Time Window (Days)", min_value=1, max_value=90, value=7)

with st.spinner("Analyzing security posture..."):
    posture = db.get_security_posture(days=days)

if not posture:
    st.error("Failed to load security posture data.")
    st.stop()

st.subheader("At-a-Glance Rollup")

mcol1, mcol2, mcol3, mcol4 = st.columns(4)
mcol1.metric("Unwhitelisted Active Devices", posture['unwhitelisted_active'], 
             delta="Action Needed" if posture['unwhitelisted_active'] > 0 else "All Good", 
             delta_color="inverse" if posture['unwhitelisted_active'] > 0 else "normal")

mcol2.metric("Port Drift Events", posture['port_drift_weekly'], 
             delta="New Ports Opened" if posture['port_drift_weekly'] > 0 else "Stable", 
             delta_color="inverse" if posture['port_drift_weekly'] > 0 else "normal")

mcol3.metric("Rogue Network Events", posture['rogue_network_weekly'],
             delta="ARP/DHCP Spoofing" if posture['rogue_network_weekly'] > 0 else "Clean",
             delta_color="inverse" if posture['rogue_network_weekly'] > 0 else "normal")

mcol4.metric("SSH Security Events", posture['ssh_events_weekly'],
             delta="Failed/Brute Force" if posture['ssh_events_weekly'] > 0 else "Secure",
             delta_color="inverse" if posture['ssh_events_weekly'] > 0 else "normal")

st.divider()
st.subheader(f"Recent Security Events (Last {days} Days)")

events_df = db.get_events(limit=500, category="security")
if not events_df.empty:
    def color_severity(val):
        if val in ['high', 'critical']: return 'color: red'
        if val == 'warning': return 'color: orange'
        if val == 'info': return 'color: green'
        return 'color: inherit'
        
    styled_df = events_df[['datetime', 'severity', 'message', 'related_id']].style.map(color_severity, subset=['severity'])
    st.dataframe(styled_df, width="stretch", hide_index=True)
else:
    st.success(f"No security events found in the last {days} days. Your network is quiet!")
