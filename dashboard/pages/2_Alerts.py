import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
from dashboard import db
from auth import check_password

st.set_page_config(page_title="Alerts - OverwatcherPI", layout="wide")
if not check_password():
    st.stop()
    
st.title("🚨 Alerts & Events")

col1, col2, col3 = st.columns(3)
with col1:
    category = st.selectbox("Filter by Category", ["All", "network", "bluetooth", "security"])
with col2:
    limit = st.number_input("Event Limit", min_value=10, max_value=1000, value=200)
with col3:
    st.write("") # Spacer
    st.write("") # Spacer
    grouped = st.checkbox("Group near-duplicate alerts")

with st.spinner("Fetching alerts..."):
    events_df = db.get_events(limit=limit, category=category if category != "All" else None, grouped=grouped)

def color_severity(val):
    if val in ['high', 'critical']:
        color = 'red'
    elif val == 'warning':
        color = 'orange'
    elif val == 'info':
        color = 'green'
    else:
        color = 'inherit'
    return f'color: {color}'

if not events_df.empty:
    if grouped:
        cols_to_show = ['last_seen', 'first_seen', 'count', 'category', 'severity', 'message', 'related_id']
    else:
        cols_to_show = ['datetime', 'category', 'severity', 'message', 'related_id']
        
    styled_df = events_df[cols_to_show].style.map(color_severity, subset=['severity'])
    
    st.dataframe(
        styled_df, 
        width="stretch",
        hide_index=True
    )
    
    csv_events = events_df.to_csv(index=False).encode('utf-8')
    st.download_button(label="📥 Download CSV", data=csv_events, file_name='alerts.csv', mime='text/csv')
else:
    st.info("No events found.")
