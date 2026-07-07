import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
from dashboard import db

st.set_page_config(page_title="Alerts - OverwatcherPI", layout="wide")
st.title("🚨 Alerts & Events")

col1, col2 = st.columns(2)
with col1:
    category = st.selectbox("Filter by Category", ["All", "network", "bluetooth", "security"])
with col2:
    limit = st.number_input("Event Limit", min_value=10, max_value=1000, value=200)

events_df = db.get_events(limit=limit, category=category if category != "All" else None)

if not events_df.empty:
    st.dataframe(
        events_df[['datetime', 'category', 'severity', 'message', 'related_id']], 
        width="stretch",
        hide_index=True
    )
else:
    st.info("No events found.")
