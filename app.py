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
st.set_page_config(page_title="CHERRY v14.0.24", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; }
    input { color: #000000 !important; }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; font-weight: bold !important; height: 55px !important; width: 100% !important; }
    .stAlert { background-color: #2b2b2b; color: white; border: 1px solid #444; }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'audio_unlocked' not in st.session_state: st.session_state.audio_unlocked = False
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0

# --- 3. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def play_sound(url):
    # JavaScript που "εκβιάζει" το παίξιμο στο κινητό
    js = f"""
        <script>
        var audio = new Audio('{url}');
        audio.muted = false;
        audio.play().catch(function(error) {{
            console.log("Audio play failed:", error);
        }});
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
        
        play_sound("https://www.soundjay.com/misc/sounds/magic-chime-01.mp3")
        st.balloons()
        st.success("Η ΣΥΝΑΛΛΑΓΗ ΟΛΟΚΛΗΡΩΘΗΚΕ!")
        time.sleep(1.5)
        st.session_state.cart = []
        st.session_state.bc_key += 1
        st.rerun()
    except Exception as e: st.error(f"Σφάλμα: {e}")

# --- 4. MAIN UI ---

# ΒΗΜΑ 1: ΞΕΚΛΕΙΔΩΜΑ ΗΧΟΥ (Απαραίτητο για Chrome Mobile)
if not st.session_state.audio_unlocked:
    st.markdown("<br><br><h1 style='text-align:center;'>🍒 CHERRY v14.0.24</h1>", unsafe_allow_html=True)
    st.warning("⚠️ Πριν ξεκινήσετε: Βεβαιωθείτε ότι ο διακόπτης στο πλάι του iPhone είναι ΑΝΟΙΧΤΟΣ (όχι σίγαση).")
    if st.button("🔊 ΕΝΕΡΓΟΠΟΙΗΣΗ ΗΧΟΥ & ΕΙΣΟΔΟΣ"):
        st.session_state.audio_unlocked = True
        play_sound("https://www.soundjay.com/buttons/beep-01a.mp3") # Δοκιμαστικό μπιπ
        st.rerun()
    st.stop()

# ΒΗΜΑ 2: ΤΑΜΕΙΟ
st.title("🛒 ΤΑΜΕΙΟ")
col1, col2 = st.columns([1, 1.2])

with col1:
    bc = st.text_input("Σάρωση Barcode", key=f"bc_{st.session_state.bc_key}")
    if bc:
        res = supabase.table("inventory").select("*").eq("barcode", bc.strip()).execute()
        if res.data:
            item = res.data[0]
            st.session_state.cart.append({'bc': item['barcode'], 'name': item['name'], 'price': float(item['price'])})
            st.session_state.bc_key += 1
            st.rerun()
        else:
            play_sound("https://www.soundjay.com/buttons/beep-10.mp3")
            st.error("Το Barcode δεν βρέθηκε!")

with col2:
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)
    
    if st.session_state.cart:
        st.divider()
        if st.button("💵 ΜΕΤΡΗΤΑ"): finalize("Μετρητά")
        if st.button("💳 ΚΑΡΤΑ"): finalize("Κάρτα")
        if st.button("🗑️ ΑΚΥΡΩΣΗ"): 
            st.session_state.cart = []
            st.rerun()
