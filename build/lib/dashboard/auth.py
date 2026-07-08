import streamlit as st
import sys
from pathlib import Path

# Import config from the main app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import config

def check_password():
    """Returns True if the user had a correct password or if no password is set."""
    if not config.dashboard_password:
        return True

    if st.session_state.get("password_correct", False):
        return True

    st.title("🔒 Authentication Required")
    st.text_input(
        "Enter Dashboard Password", type="password", key="password", on_change=_password_entered
    )
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 Password incorrect")
    return False

def _password_entered():
    if st.session_state["password"] == config.dashboard_password:
        st.session_state["password_correct"] = True
        del st.session_state["password"]  # don't store password
    else:
        st.session_state["password_correct"] = False
