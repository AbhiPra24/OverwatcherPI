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

with col1:
    st.markdown("### Network Info")
    if not net_device.empty:
        d = net_device.iloc[0]
        st.write(f"**IP:** {d['ip']}")
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
        if val == 'opened': return 'color: red'
        if val == 'closed': return 'color: green'
        return 'color: inherit'
        
    st.dataframe(port_history_df[['datetime', 'port', 'service', 'event']].style.map(color_event, subset=['event']), width="stretch", hide_index=True)
else:
    st.info("No port history recorded for this device.")

st.markdown("### Event History")
events_df = db.get_device_events(mac)
if not events_df.empty:
    def color_severity(val):
        if val in ['high', 'critical']: return 'color: red'
        if val == 'warning': return 'color: orange'
        if val == 'info': return 'color: green'
        return 'color: inherit'
        
    st.dataframe(events_df[['datetime', 'category', 'severity', 'message']].style.map(color_severity, subset=['severity']), width="stretch", hide_index=True)
else:
    st.info("No events associated with this device.")

if st.button("⬅️ Back to Device History"):
    st.switch_page("views/1_Device_History.py")
