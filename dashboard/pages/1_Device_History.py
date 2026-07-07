import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
from dashboard import db
from auth import check_password

st.set_page_config(page_title="Device History - OverwatcherPI", layout="wide")
if not check_password():
    st.stop()
    
st.title("📖 Device History")

tab1, tab2 = st.tabs(["Network Devices", "Bluetooth Devices"])

with tab1:
    st.subheader("All Network Devices")
    show_all_net = st.checkbox("Show all history (ignore 90-day limit)", key="net_limit")
    days_net = 0 if show_all_net else 90
    
    with st.spinner("Fetching network devices..."):
        net_df = db.get_all_network_devices(days=days_net)
    
    if not net_df.empty:
        search_net = st.text_input("Search Network Devices (IP, MAC, Vendor, Hostname):")
        
        if search_net:
            search_net = search_net.lower()
            mask = (
                net_df['ip'].str.lower().str.contains(search_net, na=False) |
                net_df['mac'].str.lower().str.contains(search_net, na=False) |
                net_df['vendor'].str.lower().str.contains(search_net, na=False) |
                net_df['hostname'].str.lower().str.contains(search_net, na=False)
            )
            display_df = net_df[mask].copy()
        else:
            display_df = net_df.copy()
            
        display_df['first_seen'] = pd.to_datetime(display_df['first_seen'], unit='s')
        display_df['last_seen'] = pd.to_datetime(display_df['last_seen'], unit='s')
        
        st.dataframe(display_df, width="stretch")
        
        csv_net = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download CSV", data=csv_net, file_name='network_devices.csv', mime='text/csv')
    else:
        st.info("No network devices found.")

with tab2:
    st.subheader("All Bluetooth Devices")
    show_all_bt = st.checkbox("Show all history (ignore 90-day limit)", key="bt_limit")
    days_bt = 0 if show_all_bt else 90
    
    with st.spinner("Fetching bluetooth devices..."):
        bt_df = db.get_all_bt_devices(days=days_bt)
    
    if not bt_df.empty:
        search_bt = st.text_input("Search Bluetooth Devices (MAC, Name):")
        
        if search_bt:
            search_bt = search_bt.lower()
            mask = (
                bt_df['address'].str.lower().str.contains(search_bt, na=False) |
                bt_df['name'].str.lower().str.contains(search_bt, na=False)
            )
            display_bt_df = bt_df[mask].copy()
        else:
            display_bt_df = bt_df.copy()
            
        display_bt_df['last_seen'] = pd.to_datetime(display_bt_df['last_seen'], unit='s')
        
        st.dataframe(display_bt_df, width="stretch")
        
        csv_bt = display_bt_df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download CSV", data=csv_bt, file_name='bluetooth_devices.csv', mime='text/csv')
    else:
        st.info("No bluetooth devices found.")
