import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
from dashboard import db

st.set_page_config(page_title="Device History - OverwatcherPI", layout="wide")
st.title("📖 Device History")

tab1, tab2 = st.tabs(["Network Devices", "Bluetooth Devices"])

with tab1:
    st.subheader("All Network Devices")
    net_df = db.get_all_network_devices()
    
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
    else:
        st.info("No network devices found.")

with tab2:
    st.subheader("All Bluetooth Devices")
    bt_df = db.get_all_bt_devices()
    
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
    else:
        st.info("No bluetooth devices found.")
