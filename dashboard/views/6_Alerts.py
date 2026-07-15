import streamlit as st
from dashboard import db
import time
st.session_state["alerts_last_viewed"] = time.time()

st.title("🚨 Alerts & Events")

query_params = st.query_params
default_category = query_params.get("category", "All")
categories = ["All", "network", "bluetooth", "security"]
if default_category not in categories:
    default_category = "All"
default_idx = categories.index(default_category)

col1, col2, col3 = st.columns(3)
with col1:
    category = st.selectbox("Filter by Category", categories, index=default_idx)
    st.query_params["category"] = category
with col2:
    limit = st.number_input("Event Limit", min_value=10, max_value=1000, value=200)
with col3:
    st.write("") # Spacer
    st.write("") # Spacer
    grouped = st.checkbox("Group near-duplicate alerts")

with st.spinner("Fetching alerts..."):
    events_df = db.get_events(limit=limit, category=category if category != "All" else None, grouped=grouped)

search_term = st.session_state.get("global_search", "").lower()
if not events_df.empty and search_term:
    mask = (
        events_df['message'].str.lower().str.contains(search_term, na=False) |
        events_df['related_id'].str.lower().str.contains(search_term, na=False)
    )
    events_df = events_df[mask]

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
