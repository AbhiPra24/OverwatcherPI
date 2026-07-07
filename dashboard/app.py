import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from auth import check_password

st.set_page_config(page_title="OverwatcherPI Dashboard", layout="wide")

if not check_password():
    st.stop()

# Global Sidebar
with st.sidebar:
    st.text_input("🔍 Global Search", key="global_search", placeholder="IP, MAC, Vendor, or Event...")
    
    import time
    from dashboard.db import get_connection
    last_viewed = st.session_state.get("alerts_last_viewed", 0)
    
    try:
        with get_connection() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM events WHERE timestamp > ?", (last_viewed,))
            new_alerts = cur.fetchone()[0]
            
        if new_alerts > 0:
            st.markdown(f"**🚨 {new_alerts} new alert(s)**")
    except Exception:
        pass

# Define Pages
overview = st.Page("views/0_Overview.py", title="Live Overview", icon="🛡️")
security = st.Page("views/4_Security_Posture.py", title="Security Posture", icon="🔒")
trends = st.Page("views/5_Trends.py", title="Trends", icon="📈")

device_history = st.Page("views/1_Device_History.py", title="Device History", icon="📖")
device_detail = st.Page("views/3_Device_Detail.py", title="Device Detail", icon="🔍")

alerts = st.Page("views/2_Alerts.py", title="Alerts & Events", icon="🚨")

pg = st.navigation({
    "Dashboard": [overview, security, trends],
    "Devices": [device_history, device_detail],
    "Logs": [alerts]
})

pg.run()
