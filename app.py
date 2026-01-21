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
st.set_page_config(page_title="CHERRY v14.0.43", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; letter-spacing: 2px !important; }
    .cart-area { font-family: 'Courier New', monospace; background-color: #2b2b2b; padding: 15px; border-radius: 5px; white-space: pre-wrap; border: 1px solid #3b3b3b; min-height: 200px; font-size: 14px; }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; margin: 10px 0; border: 2px solid #e44d26; padding: 10px; border-radius: 10px; background-color: #fff3f0; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; border: 1px solid #ffffff !important; font-weight: bold !important; }
    .phone-helper { color: #f1c40f; font-family: monospace; font-size: 1.2rem; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'is_logged_out' not in st.session_state: st.session_state.is_logged_out = False

def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart = []
    st.session_state.selected_cust_id = None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1
    st.session_state.ph_key += 1
    st.rerun()

def play_sound(url):
    st.components.v1.html(f'<audio autoplay style="display:none"><source src="{url}" type="audio/mpeg"></audio>', height=0)

@st.dialog("👤 Νέος Πελάτης")
def new_customer_popup(phone=""):
    name = st.text_input("Ονοματεπώνυμο")
    if st.button("Αποθήκευση", use_container_width=True):
        res = supabase.table("customers").insert({"name": name, "phone": phone}).execute()
        if res.data:
            st.success("Αποθηκεύτηκε!"); time.sleep(0.5); st.rerun()
@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center; color: #111;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(0, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(0, "Κάρτα")

def finalize(disc_val, method):
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    try:
        for i in st.session_state.cart:
            supabase.table("sales").insert({"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": 0, "final_item_price": float(i['price']), "method": str(method), "s_date": ts, "cust_id": c_id}).execute()
        st.balloons(); play_sound("https://www.soundjay.com/misc/sounds/magic-chime-01.mp3")
        time.sleep(2.0); reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

# --- MAIN UI ---
if st.session_state.is_logged_out:
    if st.button("Επανασύνδεση"): st.session_state.is_logged_out = False; st.rerun()
    st.stop()

with st.sidebar:
    st.title(f"CHERRY 14.0.43\n{get_athens_now().strftime('%H:%M:%S')}")
    view = st.radio("ΜΕΝΟΥ", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])

if view == "🛒 ΤΑΜΕΙΟ":
    st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
    cl, cr = st.columns([1, 1.5])
    with cl:
        if st.session_state.selected_cust_id is None:
            # Δυναμική απεικόνιση παυλών
            ph_input = st.text_input("Τηλέφωνο Πελάτη", key="temp_ph")
            
            # Υπολογισμός παυλών που απομένουν
            current_len = len(ph_input)
            rem_dashes = "-" * (10 - current_len) if current_len <= 10 else ""
            
            if current_len > 0 and current_len <= 10:
                st.markdown(f"<div class='phone-helper'>{ph_input}{rem_dashes}</div>", unsafe_allow_html=True)
            elif current_len == 0:
                st.markdown("<div class='phone-helper'>----------</div>", unsafe_allow_html=True)

            if ph_input:
                if not ph_input.isdigit() or len(ph_input) != 10:
                    if len(ph_input) >= 10: # Μόνο αν ξεπεράσει ή φτάσει λάθος
                        play_sound("https://www.soundjay.com/buttons/beep-10.mp3")
                        st.error("⚠️ Απαιτούνται ακριβώς 10 νούμερα.")
                else:
                    # Αν είναι ακριβώς 10 και νούμερα
                    res = supabase.table("customers").select("*").eq("phone", ph_input.strip()).execute()
                    if res.data: 
                        st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']
                        st.rerun()
                    else:
                        new_customer_popup(ph_input.strip())
            
            if st.button("🛒 ΛΙΑΝΙΚΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
        else:
            if st.button(f"👤 {st.session_state.cust_name} (Αλλαγή)", use_container_width=True): st.session_state.selected_cust_id = None; st.rerun()
            bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
            if bc:
                res = supabase.table("inventory").select("*").eq("barcode", bc.strip()).execute()
                if res.data:
                    st.session_state.cart.append({'bc': res.data[0]['barcode'], 'name': res.data[0]['name'], 'price': float(res.data[0]['price'])})
                    st.session_state.bc_key += 1; st.rerun()
            if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
    with cr:
        total = sum(i['price'] for i in st.session_state.cart)
        st.markdown(f"<div class='cart-area'>{chr(10).join([f'{i['name'][:20]:<20} | {i['price']:>6.2f}€' for i in st.session_state.cart])}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)
