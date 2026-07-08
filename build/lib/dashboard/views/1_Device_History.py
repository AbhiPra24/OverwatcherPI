import streamlit as st
import pandas as pd
from dashboard import db
    
st.title("📖 Device History")

tab1, tab2 = st.tabs(["Network Devices", "Bluetooth Devices"])

with tab1:
    st.subheader("All Network Devices")
    show_all_net = st.checkbox("Show all history (ignore 90-day limit)", key="net_limit")
    days_net = 0 if show_all_net else 90
    
    with st.spinner("Fetching network devices..."):
        net_df = db.get_all_network_devices(days=days_net)
    
    if not net_df.empty:
        search_term = st.session_state.get("global_search", "").lower()
        
        if search_term:
            mask = (
                net_df['ip'].str.lower().str.contains(search_term, na=False) |
                net_df['mac'].str.lower().str.contains(search_term, na=False) |
                net_df['vendor'].str.lower().str.contains(search_term, na=False) |
                net_df['hostname'].str.lower().str.contains(search_term, na=False) |
                (net_df['friendly_name'].str.lower().str.contains(search_term, na=False) if 'friendly_name' in net_df.columns else False)
            )
            display_df = net_df[mask].copy()
        else:
            display_df = net_df.copy()
            
        display_df['first_seen'] = pd.to_datetime(display_df['first_seen'], unit='s')
        display_df['last_seen'] = pd.to_datetime(display_df['last_seen'], unit='s')
        
        def format_vendor(v):
            if not v or v == "Unknown":
                return "❓ Unknown"
            elif str(v).startswith("Private"):
                return f"🎭 {v}"
            else:
                return f"✅ {v}"
                
        display_df['vendor_badge'] = display_df['vendor'].apply(format_vendor)
        
        
        if 'friendly_name' not in display_df.columns:
            display_df['friendly_name'] = None
            
        def format_name(row):
            if pd.notna(row['friendly_name']) and row['friendly_name']:
                return f"👤 {row['friendly_name']}"
            elif pd.notna(row['hostname']) and row['hostname']:
                return row['hostname']
            return ""
            
        display_df['display_name'] = display_df.apply(format_name, axis=1)
        
        # Display with new column order
        event = st.dataframe(
            display_df[['ip', 'mac', 'display_name', 'vendor_badge', 'first_seen', 'last_seen', 'is_known', 'is_active']], 
            width="stretch",
            on_select="rerun",
            selection_mode="single-row"
        )
        
        if event and len(event.selection.rows) > 0:
            selected_idx = event.selection.rows[0]
            mac = display_df.iloc[selected_idx]['mac']
            st.session_state["selected_device_mac"] = mac
            st.switch_page("views/3_Device_Detail.py")
        
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
        search_term = st.session_state.get("global_search", "").lower()
        
        if search_term:
            mask = (
                bt_df['address'].str.lower().str.contains(search_term, na=False) |
                bt_df['name'].str.lower().str.contains(search_term, na=False)
            )
            display_bt_df = bt_df[mask].copy()
        else:
            display_bt_df = bt_df.copy()
            
        display_bt_df['last_seen'] = pd.to_datetime(display_bt_df['last_seen'], unit='s')
        
        def format_vendor(v):
            if not v or v == "Unknown":
                return "❓ Unknown"
            elif str(v).startswith("Private"):
                return f"🎭 {v}"
            else:
                return f"✅ {v}"
                
        display_bt_df['name_badge'] = display_bt_df['name'].apply(format_vendor)
        
        # Display with new column order
        event_bt = st.dataframe(
            display_bt_df[['address', 'name_badge', 'rssi', 'last_seen', 'is_known', 'manufacturer_data_hex', 'service_uuids']], 
            width="stretch",
            on_select="rerun",
            selection_mode="single-row"
        )
        
        if event_bt and len(event_bt.selection.rows) > 0:
            selected_idx = event_bt.selection.rows[0]
            mac = display_bt_df.iloc[selected_idx]['address']
            st.session_state["selected_device_mac"] = mac
            st.switch_page("views/3_Device_Detail.py")
        
        csv_bt = display_bt_df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download CSV", data=csv_bt, file_name='bluetooth_devices.csv', mime='text/csv')
    else:
        st.info("No bluetooth devices found.")
