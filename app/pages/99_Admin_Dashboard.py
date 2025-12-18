import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="Admin Dashboard", page_icon="🛡️", layout="wide")

st.title("🛡️ Agent Admin Dashboard")

# Basic Auth
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    password = st.text_input("Enter Admin Password", type="password")
    if st.button("Login"):
        if password == "admin": # Simple default for prototype
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid password")
    st.stop()

# --- Dashboard Content ---

st.header("🤖 Autonomous Agents Status")

STATUS_FILE = "data/agent_status.json"

if st.button("Refresh Status"):
    st.rerun()

# Auto-refresh
time.sleep(2)
st.rerun()

if not os.path.exists(STATUS_FILE):
    st.warning("No agent status file found. Are the agents running?")
    st.info("Run `python agents/orchestrator.py` to start the agent system.")
else:
    try:
        with open(STATUS_FILE, 'r') as f:
            data = json.load(f)
        
        # Display as cards
        cols = st.columns(len(data))
        
        for idx, (agent_name, info) in enumerate(data.items()):
            with cols[idx % 3]:
                state = info.get("state", "unknown")
                color = "green" if state == "active" or state == "running" else "red"
                if state == "stopped": color = "gray"
                
                st.markdown(f"""
                <div style="padding: 20px; border-radius: 10px; border: 1px solid #333; background-color: #1e1e1e;">
                    <h3 style="color: {color};">● {agent_name}</h3>
                    <p><b>State:</b> {state}</p>
                    <p><b>Last Heartbeat:</b> {info.get('last_heartbeat')}</p>
                    <p><b>Interval:</b> {info.get('interval')}s</p>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander("Details"):
                    st.json(info.get("details", {}))
        
        st.subheader("📊 System Health")
        st.write("Agent system running since:", data.get(list(data.keys())[0], {}).get("details", {}).get("started_at", "Unknown"))
        
    except Exception as e:
        st.error(f"Error reading status file: {e}")

st.divider()
st.subheader("📝 System Logs")
# In a real app, read from a log file
st.info("Log integration coming in Phase 4.")
