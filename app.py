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
st.set_page_config(page_title="CHERRY v14.0.25", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; }
    input { color: #000000 !important; font-size: 18px !important; }
    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; margin: 20px 0; }
    div.stButton > button { 
        background-color: #d3d3d3 !important; 
        color: #000000 !important; 
        border-radius: 12px !important; 
        font-weight: bold !important; 
        height: 60px !important; 
        font-size: 18px !important;
    }
    .cart-box { background-color: #2b2b2b; padding: 10px; border-radius: 10px; border: 1px solid #444; }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'audio_unlocked' not in st.session_state: st.session_state.audio_unlocked = False

# --- 3. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def trigger_feedback(type="success"):
    """Στέλνει ήχο ΚΑΙ δόνηση στο κινητό"""
    sound_url = "https://www.soundjay.com/misc/sounds/magic-chime-01.mp3" if type == "success" else "https://www.soundjay.com/buttons/beep-10.mp3"
    
    js = f"""
        <script>
        // 1. Δόνηση (αν το υποστηρίζει η συσκευή)
        if (navigator.vibrate) {{
            navigator.vibrate({[200, 100, 200] if type == "error" else 150});
        }}
        // 2. Ήχος με προσπάθεια παράκαμψης σίγασης
        var audio = new Audio('{sound_url}');
        audio.volume = 1.0;
        var playPromise = audio.play();
        if (playPromise !== undefined) {{
            playPromise.catch(error => {{ console.log("Playback failed"); }});
        }}
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
        
        trigger_feedback("success")
        st.balloons()
        st.success("ΕΠΙΤΥΧΙΑ!")
        time.sleep(1.0)
        st.session_state.cart = []
        st.session_state.bc_key += 1
        st.rerun()
    except Exception as e: st.error(f"Σφάλμα: {e}")

# --- 4. MAIN UI ---

# ΥΠΟΧΡΕΩΤΙΚΟ ΞΕΚΛΕΙΔΩΜΑ (User Gesture)
if not st.session_state.audio_unlocked:
    st.markdown("<div style='text-align:center; padding:50px;'>", unsafe_allow_html=True)
    st.title("🍒 CHERRY POS")
    st.write("Πατήστε το κουμπί για να ενεργοποιηθούν οι ήχοι και οι δονήσεις στο κινητό.")
    if st.button("🚀 ΕΝΑΡΞΗ ΒΑΡΔΙΑΣ"):
        st.session_state.audio_unlocked = True
        trigger_feedback("success")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ΤΑΜΕΙΟ
st.title("🛒 ΤΑΜΕΙΟ")
c1, c2 = st.columns([1, 1.2])

with c1:
    bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}", placeholder="Σκανάρετε εδώ...")
    if bc:
        res = supabase.table("inventory").select("*").eq("barcode", bc.strip()).execute()
        if res.data:
            item = res.data[0]
            st.session_state.cart.append({'bc': item['barcode'], 'name': item['name'], 'price': float(item['price'])})
            st.session_state.bc_key += 1
            st.rerun()
        else:
            trigger_feedback("error")
            st.error("Άγνωστο Barcode!")

with c2:
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)
    
    if st.session_state.cart:
        with st.container():
            st.markdown("<div class='cart-box'>", unsafe_allow_html=True)
            for item in st.session_state.cart:
                st.write(f"• {item['name']} - {item['price']}€")
            st.markdown("</div>", unsafe_allow_html=True)
            
        st.write("")
        if st.button("💵 ΜΕΤΡΗΤΑ"): finalize("Μετρητά")
        if st.button("💳 ΚΑΡΤΑ"): finalize("Κάρτα")
        if st.button("🗑️ ΑΚΥΡΩΣΗ"): 
            st.session_state.cart = []
            st.rerun()
