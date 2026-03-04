"""
load_env.py
-----------
Loads environment variables from:
  1. Local .env file (development)
  2. Streamlit Cloud secrets (production)

This means the same code works locally AND on Streamlit Cloud
without any changes.
"""
import os
from dotenv import load_dotenv

# ── Local development: load from .env file ────────────────────────────────────
load_dotenv()

# ── Streamlit Cloud: load from st.secrets if running on the cloud ─────────────
try:
    import streamlit as st
    if hasattr(st, "secrets") and "azure_openai" in st.secrets:
        os.environ["AZURE_OPENAI_API_KEY"]     = st.secrets["azure_openai"]["AZURE_OPENAI_API_KEY"]
        os.environ["AZURE_OPENAI_API_VERSION"] = st.secrets["azure_openai"]["AZURE_OPENAI_API_VERSION"]
        os.environ["AZURE_OPENAI_ENDPOINT"]    = st.secrets["azure_openai"]["AZURE_OPENAI_ENDPOINT"]
        os.environ["AZURE_OPENAI_DEPLOYMENT"]  = st.secrets["azure_openai"]["AZURE_OPENAI_DEPLOYMENT"]
except Exception:
    pass  # Not running in Streamlit context — that's fine
