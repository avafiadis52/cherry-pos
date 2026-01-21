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
st.set_page_config(page_title="CHERRY v14.0.28", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: bold !important; }
    input { color: #000000 !important; font-size: 20px !important; border-radius: 10px !important; }
    .total-label { font-size: 80px; font-weight: bold; color: #2ecc71; text-align: center; margin: 10px 0; }
    div.stButton > button { 
        background-color: #f1c40f !important; 
        color: black !important; 
        border-radius: 15px !important; 
        font-weight: bold !important; 
        height: 70px !important;
        width: 100% !important;
        font-size: 20px !important;
    }
    .stSuccess, .stError { font-size: 20px !important; font-weight: bold !important; }
    </style>
    
    <script>
    // Bridge για το iOS: Κρατάει το AudioContext ζωντανό
    var audioCtx = null;
    function initAudio() {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
    }
    document.addEventListener('click', initAudio);
    document.addEventListener('touchstart', initAudio);
    </script>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'audio_unlocked' not in st.session_state: st.session_state.audio_unlocked = False

# --- 3. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def play_sound(sound_type):
    """Παίζει ήχο χρησιμοποιώντας το Web Audio API που είναι συμβατό με iOS Chrome"""
    s_url = "https://www.soundjay.com/misc/sounds/magic-chime-01.mp3"
    e_url = "https://www.soundjay.com/buttons/beep-10.mp3"
    url = s_url if sound_type == "success" else e_url
    
    js = f"""
        <script>
        var audio = new Audio('{url}');
        audio.play().catch(function(err) {{
            console.log("Audio failed. Device might be in silent mode.");
        }});
        if (navigator.vibrate) navigator.vibrate(150);
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
        
        play_sound("success")
        st.balloons()
        st.success(f"ΠΛΗΡΩΘΗΚΕ ΜΕ {method.upper()}")
        time.sleep(1.0)
        st.session_state.cart = []
        st.session_state.bc_key += 1
        st.rerun()
    except Exception as e: st.error(f"Σφάλμα: {e}")

# --- 4. MAIN UI ---

# Η κρίσιμη οθόνη "ξεκλειδώματος"
if not st.session_state.audio_unlocked:
    st.markdown("<div style='text-align:center; padding-top:80px;'>", unsafe_allow_html=True)
    st.title("🍒 CHERRY POS v14.0.28")
    st.markdown("### ⚠️ ΟΔΗΓΙΕΣ ΓΙΑ ΤΟ ΚΙΝΗΤΟ:")
    st.write("1. Ανεβάστε την ένταση του ήχου.")
    st.write("2. Κλείστε τη σίγαση (διακόπτης στο πλάι).")
    st.write("3. Πατήστε το παρακάτω κουμπί:")
    if st.button("🔊 ΕΝΕΡΓΟΠΟΙΗΣΗ & ΕΝΑΡΞΗ"):
        st.session_state.audio_unlocked = True
        play_sound("success")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ΤΑΜΕΙΟ
st.title("🛒 ΤΑΜΕΙΟ")
c1, c2 = st.columns([1, 1.2])

with c1:
    bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
    if bc:
        res = supabase.table("inventory").select("*").eq("barcode", bc.strip()).execute()
        if res.data:
            item = res.data[0]
            st.session_state.cart.append({'bc': item['barcode'], 'name': item['name'], 'price': float(item['price'])})
            st.session_state.bc_key += 1
            st.rerun()
        else:
            play_sound("error")
            st.error("❌ Barcode δεν βρέθηκε!")

with c2:
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)
    
    if st.session_state.cart:
        st.divider()
        if st.button("💵 ΜΕΤΡΗΤΑ"): finalize("Μετρητά")
        if st.button("💳 ΚΑΡΤΑ"): finalize("Κάρτα")
        if st.button("🗑️ ΑΚΥΡΩΣΗ"): 
            st.session_state.cart = []
            st.rerun()
