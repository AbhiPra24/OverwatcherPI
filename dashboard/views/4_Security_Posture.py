import streamlit as st
import pandas as pd
from dashboard import db
from core import threat_intel

st.title("🔒 Security Posture")

col1, col2 = st.columns(2)
with col1:
    days = st.number_input("Time Window (Days)", min_value=1, max_value=90, value=7)

@st.fragment(run_every="60s")
def render_posture():
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
    st.subheader("Threat Intel Feeds Status")
    try:
        stats = threat_intel.get_stats()
        tcol1, tcol2, tcol3 = st.columns(3)
        tcol1.metric("Blocked Domains", stats.get("blocked_domains_count", 0))
        tcol2.metric("Blocked IPs", stats.get("blocked_ips_count", 0))
        last_refresh = stats.get("last_refresh")
        tcol3.metric("Last Refresh", last_refresh.strftime("%Y-%m-%d %H:%M:%S") if last_refresh else "Never")
    except AttributeError:
        st.info("Threat Intel stats are currently being updated by the backend.")
    except Exception as e:
        st.error(f"Error loading Threat Intel stats: {e}")

    st.divider()
    st.subheader(f"Recent Security & Scan Events (Last {days} Days)")

    # Fetch events without category filter to ensure we get both security and scan events
    events_df = db.get_events(limit=1000)
    
    if not events_df.empty:
        scan_events_df = events_df[
            events_df['message'].str.contains('Scan Detected', na=False, case=False) |
            (events_df['category'] == 'security')
        ]
        
        if not scan_events_df.empty:
            def color_severity(val):
                if val in ['high', 'critical']: return 'color: red'
                if val == 'warning': return 'color: orange'
                if val == 'info': return 'color: green'
                return 'color: inherit'
                
            styled_df = scan_events_df[['datetime', 'category', 'severity', 'message', 'related_id']].style.map(color_severity, subset=['severity'])
            st.dataframe(styled_df, width="stretch", hide_index=True)
        else:
            st.success(f"No security or scan events found in the last {days} days. Your network is quiet!")
    else:
        st.success(f"No security or scan events found in the last {days} days. Your network is quiet!")

render_posture()
