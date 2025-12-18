import streamlit as st
import json
import os
import toml
from app.components.sidebar import render_sidebar

# Page Config
st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")

# Sidebar
render_sidebar()

st.title("⚙️ User Preferences & Settings")

# Paths
PREFS_FILE = "data/preferences.json"
CONFIG_FILE = ".streamlit/config.toml"

# Utility: Load/Save Prefs
def load_prefs():
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_prefs(prefs):
    if not os.path.exists("data"):
        os.makedirs("data")
    with open(PREFS_FILE, 'w') as f:
        json.dump(prefs, f, indent=4)

# Utility: Theme
def get_current_theme():
    try:
        config = toml.load(CONFIG_FILE)
        bg = config.get("theme", {}).get("backgroundColor", "#0B0C10")
        return "dark" if bg == "#0B0C10" else "light"
    except:
        return "dark"

def set_theme(mode):
    try:
        config = toml.load(CONFIG_FILE)
        if mode == "light":
            config["theme"]["primaryColor"] = "#FF1801"
            config["theme"]["backgroundColor"] = "#FFFFFF"
            config["theme"]["secondaryBackgroundColor"] = "#F0F2F6"
            config["theme"]["textColor"] = "#31333F"
        else:
            config["theme"]["primaryColor"] = "#FF1801"
            config["theme"]["backgroundColor"] = "#0B0C10"
            config["theme"]["secondaryBackgroundColor"] = "#1F2833"
            config["theme"]["textColor"] = "#FFFFFF"
            
        with open(CONFIG_FILE, 'w') as f:
            toml.dump(config, f)
        return True
    except Exception as e:
        st.error(f"Failed to update theme: {e}")
        return False

# --- UI ---

st.subheader("👤 Personalization")

prefs = load_prefs()

col1, col2 = st.columns(2)

with col1:
    # Favorites
    fav_driver = st.text_input("Favorite Driver (Abbreviation)", value=prefs.get("favorite_driver", "VER"))
    fav_team = st.text_input("Favorite Team", value=prefs.get("favorite_team", "Red Bull Racing"))

with col2:
    # Notification Settings (Mock)
    st.write("🔔 Notifications")
    email_notify = st.checkbox("Email Alerts", value=prefs.get("email_notify", False))
    push_notify = st.checkbox("Push Notifications", value=prefs.get("push_notify", False))

if st.button("Save Preferences"):
    new_prefs = {
        "favorite_driver": fav_driver,
        "favorite_team": fav_team,
        "email_notify": email_notify,
        "push_notify": push_notify
    }
    save_prefs(new_prefs)
    st.success("Preferences saved successfully!")

st.divider()

st.subheader("🎨 Appearance")

current_theme = get_current_theme()
theme_option = st.radio("Theme Mode", ["Dark", "Light"], index=0 if current_theme == "dark" else 1)

if st.button("Apply Theme"):
    if set_theme(theme_option.lower()):
        st.success("Theme updated! Please refresh the page to see changes.")
    else:
        st.error("Failed to update theme.")

st.divider()

st.subheader("📱 Application Info")
st.code("""
Version: 1.2.0 (Phase 4)
Environment: Production
Database: Connected
Model Registry: Active
Feature Store: Active
""", language="text")
