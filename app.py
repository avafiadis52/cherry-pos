import pandas as pd
from datetime import datetime, date, timedelta
import time
import streamlit as st
from supabase import create_client, Client

# --- 1. SUPABASE SETUP ---
SUPABASE_URL = "https://hnwynihjkdkryrfepenh.supabase.co"
SUPABASE_KEY = "sb_publishable_ualF72lJKgUQA4TzjPQ-OA_zih7zJ-s"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# --- 2. CONFIG & STYLE ---
st.set_page_config(page_title="CHERRY v13.8.3", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    
    /* Λευκό χρώμα για τις λεζάντες των Input (Τηλέφωνο, Barcode) */
    .stTextInput label {
        color: white !important;
        font-weight: bold !important;
    }
    
    .cart-area { font-family: 'Courier New', monospace; background-color: #2b2b2b; padding: 15px; border-radius: 5px; white-space: pre-wrap; border: 1px solid #3b3b3b; min-height: 200px; font-size: 14px; }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #f1c40f; text-align: center; margin: 10px 0; border: 2px solid #f1c40f; padding: 10px; border-radius: 10px; }
    
    /* ΚΟΥΜΠΙΑ ΣΕ ΕΛΑΦΡΥ ΓΚΡΙ */
    div.stButton > button {
        background-color: #d3d3d3 !important;
        color: #000000 !important;
        border-radius: 8px !important;
        border: 1px solid #ffffff !important;
        font-weight: bold !important;
    }
    
    div.stDownloadButton > button {
        color: #000000 !important;
        background-color: #ffffff !important;
        font-weight: bold !important;
        border: 2px solid #2ecc71 !important;
    }

    @media (max-width: 640px) {
        .total-label { font-size: 45px; }
        .stButton>button { height: 3.5em; font-size: 16px !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'is_logged_out' not in st.session_state: st.
