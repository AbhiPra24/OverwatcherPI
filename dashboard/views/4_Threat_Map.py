import streamlit as st
import pandas as pd
from dashboard import db
from utils.osint import get_ip_info_sync
import socket
import concurrent.futures

st.title("🗺️ Threat Map & External Connections")
st.query_params.update({"view": "threat_map"})

@st.fragment(run_every=30)
def threat_map_view():
    st.write("Recent external connections and OSINT data.")
    with st.spinner("Fetching DNS queries..."):
        try:
            with db.get_connection() as conn:
                df = pd.read_sql_query("SELECT timestamp, src_ip, query_name, query_type FROM dns_queries ORDER BY timestamp DESC LIMIT 500", conn)
        except Exception as e:
            st.error(f"Error fetching DNS queries: {e}")
            return
            
    if df.empty:
        st.info("No recent DNS queries.")
        return
        
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    domains = df['query_name'].unique()
    
    def resolve_domain(domain):
        try:
            return socket.gethostbyname(domain)
        except Exception:
            return None

    domain_to_ip = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_domain = {executor.submit(resolve_domain, d): d for d in domains}
        for future in concurrent.futures.as_completed(future_to_domain):
            domain = future_to_domain[future]
            try:
                ip = future.result()
                if ip:
                    domain_to_ip[domain] = ip
            except Exception:
                pass
                
    df['resolved_ip'] = df['query_name'].map(domain_to_ip)
    
    def is_external(ip):
        if not isinstance(ip, str):
            return False
        return not (ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."))
        
    external_df = df[df['resolved_ip'].apply(is_external)].copy()
    
    if external_df.empty:
        st.info("No external connections found in recent DNS queries.")
        return
        
    unique_ips = external_df['resolved_ip'].unique()
    ip_osint = {ip: get_ip_info_sync(ip) for ip in unique_ips}
    external_df['osint_info'] = external_df['resolved_ip'].map(ip_osint)
    
    summary = external_df.groupby(['src_ip', 'query_name', 'resolved_ip', 'osint_info']).size().reset_index(name='count')
    summary = summary.sort_values(by='count', ascending=False)
    st.dataframe(summary, width="stretch", hide_index=True)

threat_map_view()
