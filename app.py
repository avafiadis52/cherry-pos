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
st.set_page_config(page_title="CHERRY v14.0.26", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: bold !important; }
    input { color: #000000 !important; font-size: 20px !important; }
    .total-label { font-size: 75px; font-weight: bold; color: #2ecc71; text-align: center; }
    div.stButton > button { 
        background-color: #f1c40f !important; 
        color: black !important; 
        border-radius: 15px !important; 
        font-weight: bold !important; 
        height: 65px !important;
    }
    .main-btn { background-color: #ffffff !important; border: 2px solid #2ecc71 !important; }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'audio_unlocked' not in st.session_state: st.session_state.audio_unlocked = False

# --- 3. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def force_play_sound(type="success"):
    """Χρησιμοποιεί HTML5 Video tag για να 'εκβιάσει' τον ήχο στο iOS"""
    # Success chime
    s_url = "https://www.soundjay.com/misc/sounds/magic-chime-01.mp3"
    # Error beep
    e_url = "https://www.soundjay.com/buttons/beep-10.mp3"
    
    target = s_url if type == "success" else e_url
    
    js = f"""
        <script>
        var video = document.createElement('video');
        video.src = '{target}';
        video.setAttribute('playsinline', '');
        video.muted = false;
        video.play();
        if (navigator.vibrate) navigator.vibrate(200);
        </script>
    """
    st.components.v1.html(js, height=0)

def finalize(method):
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        for i in st.session_state.cart:
            supabase.table("sales").insert({
                "barcode": str(i['bc']), "item_name": i['name'], "unit_price": i['price'],
                "discount": 0, "final_item_price": i['price'], "method": method, "s_date": ts
            }).execute()
        
        force_play_sound("success")
        st.balloons()
        st.success("Η ΣΥΝΑΛΛΑΓΗ ΟΛΟΚΛΗΡΩΘΗΚΕ!")
        time.sleep(1.0)
        st.session_state.cart = []
        st.session_state.bc_key += 1
        st.rerun()
    except Exception as e: st.error(f"Σφάλμα: {e}")

# --- 4. MAIN UI ---

if not st.session_state.audio_unlocked:
    st.markdown("<div style='text-align:center; padding-top:100px;'>", unsafe_allow_html=True)
    st.title("🍒 CHERRY POS 14.0.26")
    st.info("⚠️ Παρακαλώ απενεργοποιήστε τη 'Σίγαση' (διακόπτης στο πλάι) και τη 'Λειτουργία Χαμηλής Ισχύος'.")
    if st.button("🚀 ΕΝΑΡΞΗ & ΤΕΣΤ ΗΧΟΥ", key="unlock"):
        st.session_state.audio_unlocked = True
        force_play_sound("success")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ΤΑΜΕΙΟ
st.title("🛒 ΤΑΜΕΙΟ")
c1, c2 = st.columns([1, 1.2])

with c1:
    bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}", auto_focus=True)
    if bc:
        res = supabase.table("inventory").select("*").eq("barcode", bc.strip()).execute()
        if res.data:
            item = res.data[0]
            st.session_state.cart.append({'bc': item['barcode'], 'name': item['name'], 'price': float(item['price'])})
            st.session_state.bc_key += 1
            st.rerun()
        else:
            force_play_sound("error")
            st.error("Το Barcode δεν βρέθηκε!")

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
