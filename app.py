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
st.set_page_config(page_title="CHERRY v14.0.29", layout="wide", page_icon="🍒")

# Στυλ για να αναβοσβήνει η οθόνη σε λάθος ή επιτυχία
st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: bold !important; }
    input { color: #000000 !important; font-size: 20px !important; }
    .total-label { font-size: 80px; font-weight: bold; color: #2ecc71; text-align: center; }
    
    /* Animation για Λάθος (Κόκκινο) */
    @keyframes flash-red {
        0% { background-color: #c0392b; }
        100% { background-color: #1a1a1a; }
    }
    .flash-error { animation: flash-red 0.5s; }

    /* Animation για Επιτυχία (Πράσινο) */
    @keyframes flash-green {
        0% { background-color: #27ae60; }
        100% { background-color: #1a1a1a; }
    }
    .flash-success { animation: flash-green 0.5s; }
    
    div.stButton > button { 
        background-color: #f1c40f !important; 
        color: black !important; 
        border-radius: 12px !important; 
        font-weight: bold !important; 
        height: 60px !important;
        font-size: 18px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'visual_feedback' not in st.session_state: st.session_state.visual_feedback = None

# --- 3. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def finalize(method):
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        for i in st.session_state.cart:
            supabase.table("sales").insert({
                "barcode": str(i['bc']), "item_name": i['name'], "unit_price": i['price'],
                "discount": 0, "final_item_price": i['price'], "method": method, "s_date": ts
            }).execute()
        
        st.session_state.visual_feedback = "success"
        st.balloons()
        time.sleep(0.5)
        st.session_state.cart = []
        st.session_state.bc_key += 1
        st.rerun()
    except Exception as e: st.error(f"Σφάλμα: {e}")

# --- 4. MAIN UI ---

# Εφαρμογή του εφέ στην οθόνη
if st.session_state.visual_feedback == "error":
    st.markdown("<script>document.body.classList.add('flash-error');</script>", unsafe_allow_html=True)
    st.session_state.visual_feedback = None
elif st.session_state.visual_feedback == "success":
    st.markdown("<script>document.body.classList.add('flash-success');</script>", unsafe_allow_html=True)
    st.session_state.visual_feedback = None

st.title("🛒 ΤΑΜΕΙΟ")
c1, c2 = st.columns([1, 1.2])

with c1:
    bc = st.text_input("Σάρωση Barcode", key=f"bc_{st.session_state.bc_key}")
    if bc:
        res = supabase.table("inventory").select("*").eq("barcode", bc.strip()).execute()
        if res.data:
            item = res.data[0]
            st.session_state.cart.append({'bc': item['barcode'], 'name': item['name'], 'price': float(item['price'])})
            st.session_state.bc_key += 1
            st.rerun()
        else:
            st.session_state.visual_feedback = "error"
            st.error("❌ Barcode δεν βρέθηκε!")
            # Δόνηση (μόνο αν το επιτρέπει η συσκευή)
            st.components.v1.html("<script>if(navigator.vibrate) navigator.vibrate(200);</script>", height=0)

with c2:
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)
    
    if st.session_state.cart:
        st.divider()
        if st.button("💵 ΜΕΤΡΗΤΑ", use_container_width=True): finalize("Μετρητά")
        if st.button("💳 ΚΑΡΤΑ", use_container_width=True): finalize("Κάρτα")
        if st.button("🗑️ ΑΚΥΡΩΣΗ", use_container_width=True): 
            st.session_state.cart = []
            st.rerun()
