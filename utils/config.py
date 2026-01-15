import os
import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env file for local development
load_dotenv()

def get_secret(key, default=None):
    """
    Retrieves a secret or configuration value.
    
    Priority:
    1. Streamlit Secrets (st.secrets) - for Production/Cloud
    2. Environment Variables (os.getenv) - for Local/Docker
    3. Default value
    """
    # 1. Try Streamlit Secrets
    try:
        # Check if key is available in st.secrets
        # We use strict checking to avoid side effects if secrets aren't loaded
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except (FileNotFoundError, KeyError, Exception):
        # Fallback if secrets.toml is missing or other issues
        pass
    
    # 2. Fallback to Environment Variables
    return os.getenv(key, default)
