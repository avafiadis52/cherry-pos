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

# --- 3. CONFIG & STYLE ---
st.set_page_config(page_title="CHERRY v14.2.26", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; }
    .cart-area { font-family: 'Courier New', monospace; background-color: #2b2b2b; padding: 15px; border-radius: 5px; white-space: pre-wrap; border: 1px solid #3b3b3b; min-height: 200px; font-size: 14px; }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; padding: 10px; border-radius: 10px; background-color: #fff3f0; border: 2px solid #e44d26; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; font-weight: bold !important; border: 1px solid #808080 !important; }
    .data-row { font-family: 'Courier New', monospace; background-color: #262626; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; display: block; white-space: pre; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    .report-stat { background-color: #262730; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; }
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

def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.return_mode = False
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1
    st.rerun()

def speak_text(text_to_say, play_beep=True):
    beep_js = "var context = new (window.AudioContext || window.webkitAudioContext)(); var osc = context.createOscillator(); osc.type = 'sawtooth'; osc.frequency.setValueAtTime(150, context.currentTime); osc.connect(context.destination); osc.start(); osc.stop(context.currentTime + 0.2);" if play_beep else ""
    speech_js = f"var msg = new SpeechSynthesisUtterance('{text_to_say}'); msg.lang = 'el-GR'; window.speechSynthesis.speak(msg);"
    st.components.v1.html(f"<script>{beep_js}{speech_js}</script>", height=0)

@st.dialog("👤 Νέος Πελάτης")
def new_customer_popup(phone):
    name = st.text_input("Ονοματεπώνυμο Πελάτη")
    if st.button("Καταχώρηση", use_container_width=True):
        if name:
            res = supabase.table("customers").insert({"name": name.upper(), "phone": phone}).execute()
            if res.data:
                st.session_state.selected_cust_id = res.data[0]['id']
                st.session_state.cust_name = res.data[0]['name']
                st.rerun()

def finalize(disc_val, method):
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    for i in st.session_state.cart:
        d = round(i['price'] * ratio, 2)
        f = round(i['price'] - d, 2)
        data = {"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": float(d), "final_item_price": float(f), "method": str(method), "s_date": ts, "cust_id": c_id}
        supabase.table("sales").insert(data).execute()
        if i['bc'] != 'VOICE':
            res_inv = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
            if res_inv.data:
                new_stock = int(res_inv.data[0]['stock']) + (1 if f < 0 else -1)
                supabase.table("inventory").update({"stock": new_stock}).eq("barcode", i['bc']).execute()
    st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); time.sleep(1); reset_app()

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    disc = 0.0
    inp = st.text_input("Έκπτωση (π.χ. 5 ή 10%)")
    if inp:
        try:
            if "%" in inp: disc = round((float(inp.replace("%",""))/100 * total), 2)
            else: disc = round(float(inp), 2)
        except: pass
    final_p = round(total - disc, 2)
    st.markdown(f"<div class='final-amount-popup'>{final_p:.2f}€</div>", unsafe_allow_html=True)
    if st.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if st.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

# --- MAIN UI ---
if st.session_state.is_logged_out:
    if st.button("Επανασύνδεση"): st.session_state.is_logged_out = False; st.rerun()
else:
    with st.sidebar:
        st.write(get_athens_now().strftime("%d/%m/%Y %H:%M"))
        if HAS_MIC:
            text = speech_to_text(language='el', key=f"v_{st.session_state.mic_key}")
            if text:
                nums = re.findall(r"\d+", text)
                if nums:
                    p = float(nums[0])
                    val = -p if st.session_state.return_mode else p
                    st.session_state.cart.append({'bc': 'VOICE', 'name': 'ΦΩΝΗΤΙΚΗ', 'price': val})
                    st.session_state.mic_key += 1; st.rerun()
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])
        if st.button("❌ Έξοδος"): st.session_state.is_logged_out = True; st.rerun()

    if view == "🛒 ΤΑΜΕΙΟ":
        st.subheader(f"Πελάτης: {st.session_state.cust_name}")
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"ph_{st.session_state.ph_key}")
                if len(ph) == 10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data:
                        st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']
                        st.rerun()
                    else: new_customer_popup(ph)
                if st.button("🛒 ΛΙΑΝΙΚΗ"): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                if st.button("🔄 ΕΠΙΣΤΡΟΦΗ"): st.session_state.return_mode = not st.session_state.return_mode; st.rerun()
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        p = float(res.data[0]['price'])
                        val = -p if st.session_state.return_mode else p
                        st.session_state.cart.append({'bc': bc, 'name': res.data[0]['name'], 'price': val})
                        st.session_state.bc_key += 1; st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ"): payment_popup()
                if st.button("🔄 ΑΚΥΡΩΣΗ"): reset_app()
        with cr:
            st.markdown(f"<div class='total-label'>{sum(i['price'] for i in st.session_state.cart):.2f}€</div>", unsafe_allow_html=True)
            for idx, i in enumerate(st.session_state.cart):
                if st.button(f"❌ {i['name']} {i['price']}€", key=f"del_{idx}"): st.session_state.cart.pop(idx); st.rerun()

    elif view == "📊 MANAGER":
        res = supabase.table("sales").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            st.metric("Τζίρος", f"{df['final_item_price'].sum():.2f}€")
            st.dataframe(df)

    elif view == "📦 ΑΠΟΘΗΚΗ":
        b = st.text_input("Barcode")
        n = st.text_input("Όνομα")
        p = st.number_input("Τιμή", min_value=0.0)
        s = st.number_input("Stock", min_value=0)
        if st.button("Προσθήκη"):
            supabase.table("inventory").upsert({"barcode": b, "name": n.upper(), "price": p, "stock": s}).execute()
            st.rerun()
        res = supabase.table("inventory").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data))

    elif view == "👥 ΠΕΛΑΤΕΣ":
        res = supabase.table("customers").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data))
