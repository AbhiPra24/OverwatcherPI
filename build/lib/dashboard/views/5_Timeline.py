import streamlit as st
import pandas as pd
from dashboard import db

st.title("⏱️ Unified Timeline")
st.query_params.update({"view": "timeline"})

@st.fragment(run_every=30)
def timeline_view():
    st.write("Chronological stream of network events.")
    with st.spinner("Fetching data..."):
        events_df = db.get_events(limit=100)
        scan_df = db.get_scan_history(days=1)
        try:
            with db.get_connection() as conn:
                port_df = pd.read_sql_query("SELECT timestamp, mac, port, service, event FROM port_history ORDER BY timestamp DESC LIMIT 100", conn)
        except Exception:
            port_df = pd.DataFrame()
            
    timeline_data = []
    if not events_df.empty:
        for _, row in events_df.iterrows():
            timeline_data.append({
                'timestamp': row['timestamp'],
                'type': 'Event',
                'description': f"[{row['severity'].upper()}] {row['category']}: {row['message']}"
            })
            
    if not scan_df.empty:
        scan_df = scan_df.reset_index()
        for _, row in scan_df.iterrows():
            ts = row['datetime'].timestamp()
            timeline_data.append({
                'timestamp': ts,
                'type': 'Scan',
                'description': f"Network scan completed. Devices found: {row['device_count']}"
            })
            
    if not port_df.empty:
        for _, row in port_df.iterrows():
            timeline_data.append({
                'timestamp': row['timestamp'],
                'type': 'Port Activity',
                'description': f"Port {row['port']} ({row['service']}) {row['event']} on MAC {row['mac']}"
            })
            
    if not timeline_data:
        st.info("No timeline data available.")
        return
        
    timeline_df = pd.DataFrame(timeline_data)
    timeline_df['datetime'] = pd.to_datetime(timeline_df['timestamp'], unit='s')
    timeline_df = timeline_df.sort_values(by='timestamp', ascending=False).drop(columns=['timestamp'])
    
    def color_type(val):
        if val == 'Event': return 'background-color: rgba(255, 100, 100, 0.2)'
        if val == 'Port Activity': return 'background-color: rgba(255, 200, 100, 0.2)'
        if val == 'Scan': return 'background-color: rgba(100, 200, 255, 0.2)'
        return ''
        
    st.dataframe(timeline_df[['datetime', 'type', 'description']].style.map(color_type, subset=['type']), width="stretch", hide_index=True)

timeline_view()
