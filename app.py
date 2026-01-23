import pandas as pd
from datetime import datetime, date, timedelta
import time
import streamlit as st
from supabase import create_client, Client

# --- 1. EXPERIMENTAL COMPONENT LOAD ---
try:
    from streamlit_mic_recorder import speech_to_text
    HAS_MIC = True
except ImportError:
    HAS_MIC = False

# --- 2. SUPABASE SETUP ---
SUPABASE_URL = "https://hnwynihjkdkryrfepenh.supabase.co"
SUPABASE_KEY = "sb_publishable_ualF72lJKgUQA4TzjPQ-OA_zih7zJ-s"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# --- 3. CONFIG & STYLE ---
st.set_page_config(page_title="CHERRY v14.0.61", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; font-size: 1.2rem !important; }
    .cart-area { font-family: 'Courier New', monospace; background-color: #2b2b2b; padding: 15px; border-radius: 5px; white-space: pre-wrap; border: 1px solid #3b3b3b; min-height: 200px; font-size: 14px; }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; border: 1px solid #ffffff !important; font-weight: bold !important; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; text-align: left; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'is_logged_out' not in st.session_state: st.session_state.is_logged_out = False

# --- 4. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart = []
    st.session_state.selected_cust_id = None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1
    st.session_state.ph_key += 1
    st.rerun()

# --- 5. MAIN UI ---
if st.session_state.is_logged_out:
    st.markdown("<h1 style='text-align: center;'>Αποσυνδεθήκατε</h1>", unsafe_allow_html=True)
    if st.button("Επανασύνδεση"): st.session_state.is_logged_out = False; st.rerun()
else:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-date'>{get_athens_now().strftime('%d/%m/%Y %H:%M:%S')}</div>", unsafe_allow_html=True)
        st.title("CHERRY 14.0.61")
        
        # --- VOICE CONTROL LOGIC ---
        if HAS_MIC:
            st.write("🎤 Φωνητικός Έλεγχος")
            text = speech_to_text(language='el', start_prompt="Πείτε εντολή", stop_prompt="Τέλος", key='speech')
            if text:
                cmd = text.lower()
                st.info(f"Ακούστηκε: {cmd}")
                if "διαγραφή" in cmd or "άδειασμα" in cmd:
                    st.session_state.cart = []
                    st.toast("🧹 Το καλάθι άδειασε!")
                elif "λιανική" in cmd:
                    st.session_state.selected_cust_id = 0
                    st.session_state.cust_name = "Λιανική Πώληση"
                    st.toast("👤 Λιανική Πώληση")
        else:
            st.warning("⚠️ Πρόσθεσε το 'streamlit-mic-recorder' στο requirements.txt για φωνητικές εντολές.")

        st.divider()
        view = st.radio("ΜΕΝΟΥ", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])
        if st.button("❌ ΕΞΟΔΟΣ", use_container_width=True): 
            st.session_state.cart = []; st.session_state.is_logged_out = True; st.rerun()

    if view == "🛒 ΤΑΜΕΙΟ":
        st.markdown(f"<div class='status-header'>ΠΕΛΑΤΗΣ: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο Πελάτη", placeholder="----------", key=f"ph_{st.session_state.ph_key}")
                if ph:
                    clean_ph = "".join(filter(str.isdigit, ph))
                    if len(clean_ph) == 10:
                        res = supabase.table("customers").select("*").eq("phone", clean_ph).execute()
                        if res.data: 
                            st.session_state.selected_cust_id = res.data[0]['id']
                            st.session_state.cust_name = res.data[0]['name']
                            st.rerun()
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True): 
                    st.session_state.selected_cust_id = 0
                    st.session_state.cust_name = "Λιανική Πώληση"
                    st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name} (Αλλαγή)", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc.strip()).execute()
                    if res.data:
                        item = res.data[0]
                        st.session_state.cart.append({'bc': item['barcode'], 'name': item['name'], 'price': round(float(item['price']), 2)})
                        st.session_state.bc_key += 1; st.rerun()
                
                for idx, item in enumerate(st.session_state.cart):
                    if st.button(f"❌ {item['name']} ({item['price']}€)", key=f"del_{idx}", use_container_width=True):
                        st.session_state.cart.pop(idx); st.rerun()
            
            if st.button("❌ ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
            
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            lines = [f"{i['name'][:20]:<20} | {i['price']:>6.2f}€" for i in st.session_state.cart]
            st.markdown(f"<div class='cart-area'>{'ΕΙΔΟΣ':<20} | {'ΤΙΜΗ':>6}\n{'-'*30}\n{chr(10).join(lines)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)
