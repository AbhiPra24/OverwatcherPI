import streamlit as st
import pandas as pd
from dashboard import db

st.title("🔍 Device Detail")

mac = st.session_state.get("selected_device_mac")

if not mac:
    st.info("No device selected. Please select a device from the Device History page.")
    if st.button("Go to Device History"):
        st.switch_page("views/1_Device_History.py")
    st.stop()

st.subheader(f"Details for MAC: {mac}")

# Fetch data
net_df = db.get_all_network_devices(days=0)
bt_df = db.get_all_bt_devices(days=0)

net_device = net_df[net_df['mac'] == mac] if not net_df.empty else pd.DataFrame()
bt_device = bt_df[bt_df['address'] == mac] if not bt_df.empty else pd.DataFrame()

col1, col2 = st.columns(2)

maintenance_info = db.get_device_maintenance(mac)
if maintenance_info:
    st.warning(f"🔇 **Device is in Maintenance Mode** until {pd.to_datetime(maintenance_info['until_timestamp'], unit='s')}. Reason: {maintenance_info['reason']}")

with col1:
    st.markdown("### Network Info")
    if not net_device.empty:
        d = net_device.iloc[0]
        st.write(f"**IP:** {d['ip']}")
        st.write(f"**Friendly Name:** {d.get('friendly_name', 'N/A')}")
        st.write(f"**Vendor:** {d['vendor']}")
        st.write(f"**Hostname:** {d['hostname']}")
        st.write(f"**First Seen:** {pd.to_datetime(d['first_seen'], unit='s')}")
        st.write(f"**Last Seen:** {pd.to_datetime(d['last_seen'], unit='s')}")
        st.write(f"**Is Active:** {'Yes' if d['is_active'] else 'No'}")
        st.write(f"**Is Known (Whitelisted):** {'Yes' if d['is_known'] else 'No'}")
    else:
        st.info("No network record found for this MAC.")

with col2:
    st.markdown("### Bluetooth Info")
    if not bt_device.empty:
        d = bt_device.iloc[0]
        st.write(f"**Name:** {d['name']}")
        st.write(f"**Last RSSI:** {d['rssi']} dBm")
        st.write(f"**Last Seen:** {pd.to_datetime(d['last_seen'], unit='s')}")
        st.write(f"**Is Known (Whitelisted):** {'Yes' if d['is_known'] else 'No'}")
        st.write(f"**Service UUIDs:** {d['service_uuids']}")
        st.write(f"**Manufacturer Data:** {d['manufacturer_data_hex']}")
    else:
        st.info("No Bluetooth record found for this MAC.")

st.markdown("### Risk Score")
risk_score = 0
risk_factors = []

# Sensitive Ports
sensitive_ports = {21, 22, 23, 445, 3389}
open_sensitive = []
ports_df = db.get_device_ports(mac)
if not ports_df.empty:
    for _, row in ports_df.iterrows():
        if row['is_active'] and row['port'] in sensitive_ports:
            open_sensitive.append(row['port'])
if open_sensitive:
    risk_score += 30
    risk_factors.append(f"Open sensitive ports: {open_sensitive}")

# Unwhitelisted
if not net_device.empty:
    d = net_device.iloc[0]
    if not d.get('is_known', True):
        risk_score += 20
        risk_factors.append("Unknown/Unwhitelisted device")
elif not bt_device.empty:
    d = bt_device.iloc[0]
    if not d.get('is_known', True):
        risk_score += 20
        risk_factors.append("Unknown/Unwhitelisted BT device")

# Threat Intel Events
if not net_device.empty:
    ip = net_device.iloc[0]['ip']
    ti_events_df = db.get_events(category='security')
    if not ti_events_df.empty:
        hits = ti_events_df[ti_events_df['message'].str.contains(f"Threat Intel Hit: {ip}", na=False)]
        if not hits.empty:
            risk_score += 50
            risk_factors.append(f"Threat Intel Hits ({len(hits)} recent)")

risk_score = min(risk_score, 100)
if risk_score > 70:
    badge_color = "red"
elif risk_score > 30:
    badge_color = "orange"
elif risk_score > 0:
    badge_color = "yellow"
else:
    badge_color = "green"

st.markdown(f"**Score:** :{badge_color}[{risk_score}/100]")
if risk_factors:
    st.write("**Contributing Factors:**")
    for f in risk_factors:
        st.write(f"- {f}")
else:
    st.write("✅ No elevated risk factors detected.")

st.markdown("### Open Ports")
ports_df = db.get_device_ports(mac)
if not ports_df.empty:
    st.dataframe(ports_df, width="stretch", hide_index=True)
else:
    st.info("No open ports found or device hasn't been scanned.")

st.markdown("### Port History")
port_history_df = db.get_device_port_history(mac)
if not port_history_df.empty:
    def color_event(val):
        if val == 'opened':
            return 'color: red'
        if val == 'closed':
            return 'color: green'
        return 'color: inherit'
        
    st.dataframe(port_history_df[['datetime', 'port', 'service', 'event']].style.map(color_event, subset=['event']), width="stretch", hide_index=True)
else:
    st.info("No port history recorded for this device.")

st.markdown("### Event History")
events_df = db.get_device_events(mac)
if not events_df.empty:
    def color_severity(val):
        if val in ['high', 'critical']:
            return 'color: red'
        if val == 'warning':
            return 'color: orange'
        if val == 'info':
            return 'color: green'
        return 'color: inherit'
        
    st.dataframe(events_df[['datetime', 'category', 'severity', 'message']].style.map(color_severity, subset=['severity']), width="stretch", hide_index=True)
else:
    st.info("No events associated with this device.")

if not net_device.empty:
    ip = net_device.iloc[0]['ip']
    st.markdown("### Recent DNS Queries")
    dns_df = db.get_device_dns_queries(ip, limit=50)
    if not dns_df.empty:
        st.dataframe(dns_df[['datetime', 'query_name', 'query_type']], width="stretch", hide_index=True)
    else:
        st.info("No DNS queries recorded for this device.")

if st.button("⬅️ Back to Device History"):
    st.switch_page("views/1_Device_History.py")
