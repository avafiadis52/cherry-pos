import pandas as pd
from datetime import datetime, date, timedelta
import time
import streamlit as st
from supabase import create_client, Client
import re

# --- 1. VOICE COMPONENT SETUP ---
HAS_MIC = False
try:
    from streamlit_mic_recorder import speech_to_text
    HAS_MIC = True
except Exception:
    HAS_MIC = False

# --- 2. SUPABASE SETUP ---
SUPABASE_URL = "https://hnwynihjkdkryrfepenh.supabase.co"
SUPABASE_KEY = "sb_publishable_ualF72lJKgUQA4TzjPQ-OA_zih7zJ-s"

@st.cache_resource
def init_supabase():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        return None

supabase = init_supabase()

# --- 3. CONFIG & STYLE (Version v14.2.32) ---
st.set_page_config(page_title="CHERRY v14.2.32", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; }
    .cart-area { font-family: 'Courier New', monospace; background-color: #2b2b2b; padding: 15px; border-radius: 5px; white-space: pre-wrap; border: 1px solid #3b3b3b; min-height: 200px; font-size: 14px; }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; padding: 10px; border-radius: 10px; background-color: #fff3f0; border: 2px solid #e44d26; }
    
    div.stButton > button { 
        background-color: #d3d3d3 !important; 
        color: #000000 !important; 
        border-radius: 8px !important; 
        font-weight: bold !important; 
        border: 1px solid #808080 !important;
    }
    
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'is_logged_out' not in st.session_state: st.session_state.is_logged_out = False
if 'mic_key' not in st.session_state: st.session_state.mic_key = 28000
if 'return_mode' not in st.session_state: st.session_state.return_mode = False

# --- 4. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.return_mode = False
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1
    st.rerun()

def switch_to_normal():
    """Callback function to force normal mode"""
    st.session_state.return_mode = False
    if 'sidebar_nav' in st.session_state:
        st.session_state.sidebar_nav = "🛒 ΤΑΜΕΙΟ"

def finalize(disc_val, method):
    if not supabase: return
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    try:
        for i in st.session_state.cart:
            data = {"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": 0.0, "final_item_price": float(i['price']), "method": str(method), "s_date": ts, "cust_id": c_id}
            supabase.table("sales").insert(data).execute()
            if i['bc'] != 'VOICE':
                res_inv = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
                if res_inv.data:
                    change = 1 if i['price'] < 0 else -1
                    new_stock = int(res_inv.data[0]['stock']) + change
                    supabase.table("inventory").update({"stock": new_stock}).eq("barcode", i['bc']).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΣΥΝΑΛΛΑΓΗ"); st.balloons()
        time.sleep(1.5); reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(0, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(0, "Κάρτα")

# --- 5. MAIN UI ---
if st.session_state.is_logged_out:
    st.markdown("<h1 style='text-align:center;color:#e74c3c;'>Αποσυνδεθήκατε</h1>", unsafe_allow_html=True)
    if st.button("Επανασύνδεση"): st.session_state.is_logged_out = False; st.rerun()
else:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-date'>{get_athens_now().strftime('%d/%m/%Y %H:%M:%S')}</div>", unsafe_allow_html=True)
        st.subheader("🎙️ Φωνητική Εντολή")
        if HAS_MIC:
            text = speech_to_text(language='el', start_prompt="🔴 ΜΙΛΑ", key=f"voice_{st.session_state.mic_key}")
            if text:
                # Basic processing
                st.session_state.mic_key += 1; st.rerun()
        
        st.divider()
        menu_options = ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"]
        
        # Συγχρονισμός index με την κατάσταση επιστροφής
        def_idx = 1 if st.session_state.return_mode else 0
        view = st.radio("Μενού", menu_options, index=def_idx, key="sidebar_nav")
        
        # Update return mode state based on selection
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        current_screen = "🛒 ΤΑΜΕΙΟ" if view in ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ"] else view

        if st.button("❌ Έξοδος", use_container_width=True):
            st.session_state.cart = []; st.session_state.is_logged_out = True; st.rerun()

    if current_screen == "🛒 ΤΑΜΕΙΟ":
        # Διορθωμένο Κουμπί Επιστροφής στην Κεντρική Οθόνη
        if st.session_state.return_mode:
            st.button("🔄 ΛΕΙΤΟΥΡΓΙΑ ΕΠΙΣΤΡΟΦΗΣ (ΠΑΤΗΣΤΕ ΓΙΑ ΚΑΝΟΝΙΚΟ ΤΑΜΕΙΟ)", 
                      on_click=switch_to_normal, 
                      use_container_width=True)
            st.error("⚠️ ΣΚΑΝΑΡΕΤΕ ΤΟ ΕΙΔΟΣ ΠΡΟΣ ΕΠΙΣΤΡΟΦΗ")
        else:
            st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
            
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο (10 ψηφία)", key=f"ph_{st.session_state.ph_key}")
                if ph and len(ph) == 10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name} (Αλλαγή)", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc and supabase:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data: 
                        val = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'bc': res.data[0]['barcode'], 'name': res.data[0]['name'].upper(), 'price': val})
                        st.session_state.bc_key += 1; st.rerun()
                for idx, item in enumerate(st.session_state.cart):
                    if st.button(f"❌ {item['name']} {item['price']}€", key=f"del_{idx}", use_container_width=True): st.session_state.cart.pop(idx); st.rerun()
                if st.session_state.cart and st.button("💰 ΟΛΟΚΛΗΡΩΣΗ", use_container_width=True): payment_popup()
            if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            lines = [f"{i['name'][:20]:<20} | {i['price']:>6.2f}€" for i in st.session_state.cart]
            st.markdown(f"<div class='cart-area'>{'Είδος':<20} | {'Τιμή':>6}\n{'-'*30}\n{chr(10).join(lines)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif current_screen == "📊 MANAGER":
        st.title("📊 MANAGER")
        res_s = supabase.table("sales").select("*").execute()
        if res_s.data: st.dataframe(pd.DataFrame(res_s.data).sort_values('s_date', ascending=False), use_container_width=True)

    elif current_screen == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 ΑΠΟΘΗΚΗ")
        res = supabase.table("inventory").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data).sort_values('name'), use_container_width=True)

    elif current_screen == "👥 ΠΕΛΑΤΕΣ":
        st.title("👥 ΠΕΛΑΤΕΣ")
        res = supabase.table("customers").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data).sort_values('name'), use_container_width=True)
