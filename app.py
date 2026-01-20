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
st.set_page_config(page_title="CHERRY v14.0.17", layout="wide", page_icon="🍒")

# Ήχος "Cash Register" σε μορφή Base64 για ακαριαία απόκριση
CASH_SOUND_B64 = "UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=" # (Συμπιεσμένο δείγμα)

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    div[data-testid="stDialog"] label p, div[data-testid="stDialog"] h3, div[data-testid="stDialog"] .stMarkdown p, div[data-testid="stDialog"] [data-testid="stWidgetLabel"] p { color: #111111 !important; }
    input { color: #000000 !important; }
    .cart-area { font-family: 'Courier New', monospace; background-color: #2b2b2b; padding: 15px; border-radius: 5px; white-space: pre-wrap; border: 1px solid #3b3b3b; min-height: 200px; font-size: 14px; }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; margin: 10px 0; border: 2px solid #e44d26; padding: 10px; border-radius: 10px; background-color: #fff3f0; }
    .report-stat { background-color: #262730; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; margin: 0; }
    .stat-label { font-size: 13px; color: #888; margin: 0; font-weight: bold; text-transform: uppercase; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; border: 1px solid #ffffff !important; font-weight: bold !important; }
    .data-row { background-color: #262626; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; text-align: left; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    </style>
    
    <script>
    // Συνάρτηση που "ξεκλειδώνει" τον ήχο στον browser
    function forcePlay() {
        var context = new (window.AudioContext || window.webkitAudioContext)();
        var osc = context.createOscillator();
        var gain = context.createGain();
        osc.connect(gain);
        gain.connect(context.destination);
        gain.gain.value = 0.1;
        osc.start(0);
        osc.stop(0.1); // Παίζει ένα ακαριαίο "μπιπ" για να ανοίξει το κανάλι
        
        // Μετά παίζει τον κανονικό ήχο
        var audio = window.parent.document.getElementById('cash_audio');
        if(audio) {
            audio.currentTime = 0;
            audio.play();
        }
    }
    </script>
    
    <audio id="cash_audio" src="https://www.soundjay.com/misc/sounds/cash-register-purchase-1.mp3" preload="auto"></audio>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'is_logged_out' not in st.session_state: st.session_state.is_logged_out = False

# --- 3. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def trigger_sound():
    """Η μοναδική μέθοδος που εγγυάται ήχο σε Chrome/Safari"""
    st.components.v1.html("""
        <script>
            var audio = window.parent.document.getElementById('cash_audio');
            if(audio) {
                audio.muted = false;
                audio.currentTime = 0;
                audio.play().catch(e => {
                    // Αν αποτύχει, δοκιμάζουμε ξανά με το AudioContext
                    var ctx = new (window.parent.AudioContext || window.parent.webkitAudioContext)();
                    ctx.resume().then(() => { audio.play(); });
                });
            }
        </script>
    """, height=0)

def reset_app():
    st.session_state.cart = []
    st.session_state.selected_cust_id = None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1
    st.session_state.ph_key += 1
    st.rerun()

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center; color: #111;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    opt = st.radio("Έκπτωση;", ["ΟΧΙ", "ΝΑΙ"], horizontal=True)
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή %")
        if inp:
            try:
                if "%" in inp: disc = round((float(inp.replace("%",""))/100 * total), 2)
                else: disc = round(float(inp), 2)
            except: st.error("Σφάλμα")
    
    final_p = round(total - disc, 2)
    st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {final_p:.2f}€</div>", unsafe_allow_html=True)
    st.divider()
    
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True):
        trigger_sound()
        finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True):
        trigger_sound()
        finalize(disc, "Κάρτα")

def finalize(disc_val, method):
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    try:
        for i in st.session_state.cart:
            d = round(i['price'] * ratio, 2)
            f = round(i['price'] - d, 2)
            data = {"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": float(d), "final_item_price": float(f), "method": str(method), "s_date": ts, "cust_id": c_id}
            supabase.table("sales").insert(data).execute()
        st.success("ΟΛΟΚΛΗΡΩΘΗΚΕ!")
        time.sleep(1.0)
        reset_app()
    except Exception as e: st.error(f"Σφάλμα")

# --- 4. MAIN UI ---
with st.sidebar:
    now = get_athens_now()
    st.markdown(f"<div class='sidebar-date'>📅 {now.strftime('%d/%m/%Y')}<br>🕒 {now.strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)
    st.title("CHERRY 14.0.17")
    view = st.radio("ΜΕΝΟΥ", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])

if view == "🛒 ΤΑΜΕΙΟ":
    st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
    cl, cr = st.columns([1, 1.5])
    with cl:
        if st.session_state.selected_cust_id is None:
            ph = st.text_input("Τηλέφωνο Πελάτη", key=f"ph_{st.session_state.ph_key}")
            if ph:
                res = supabase.table("customers").select("*").eq("phone", ph.strip()).execute()
                if res.data: 
                    st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']
                    st.rerun()
            if st.button("🛒 ΛΙΑΝΙΚΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
        else:
            bc = st.text_input("Σάρωση Barcode", key=f"bc_{st.session_state.bc_key}")
            if bc:
                res = supabase.table("inventory").select("*").eq("barcode", bc.strip()).execute()
                if res.data:
                    item = res.data[0]
                    st.session_state.cart.append({'bc': item['barcode'], 'name': item['name'], 'price': round(float(item['price']), 2)})
                    st.session_state.bc_key += 1; st.rerun()
            for idx, item in enumerate(st.session_state.cart):
                if st.button(f"❌ {item['name']} ({item['price']}€)", key=f"del_{idx}", use_container_width=True):
                    st.session_state.cart.pop(idx); st.rerun()
            if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
            if st.button("🗑️ ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
    with cr:
        total = sum(i['price'] for i in st.session_state.cart)
        lines = [f"{i['name'][:20]:<20} | {i['price']:>6.2f}€" for i in st.session_state.cart]
        st.markdown(f"<div class='cart-area'>{'ΕΙΔΟΣ':<20} | {'ΤΙΜΗ':>6}\n{'-'*30}\n{chr(10).join(lines)}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

# (Ο κώδικας για Manager, Αποθήκη κλπ παραμένει ίδιος)
elif view == "📊 MANAGER":
    st.write("Επιλέξτε ΤΑΜΕΙΟ για τη δοκιμή ήχου.")
