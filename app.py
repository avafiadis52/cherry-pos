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
st.set_page_config(page_title="CHERRY v14.1.9", layout="wide", page_icon="🍒")

if st.session_state.get('is_logged_out', False):
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {display: none;}
            .stApp {background-color: #1a1a1a;}
        </style>
        <div style='text-align: center; padding-top: 150px;'>
            <h1 style='color: #e74c3c; font-size: 50px;'>🔒 Η ΕΦΑΡΜΟΓΗ ΕΚΛΕΙΣΕ</h1>
            <p style='color: white;'>Όλα τα δεδομένα καθαρίστηκαν.</p>
        </div>
    """, unsafe_allow_html=True)
    if st.button("🔄 ΕΠΑΝΕΚΚΙΝΗΣΗ"):
        st.session_state.clear()
        st.session_state.is_logged_out = False
        st.rerun()
    st.stop()

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

# --- 3. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def play_cash_sound():
    # Ήχος κερμάτων / ταμείου
    sound_url = "https://www.soundjay.com/misc/sounds/cash-register-purchase-1.mp3"
    st.components.v1.html(f"""<script>var audio = new Audio("{sound_url}"); audio.play();</script>""", height=0)

def reset_app():
    st.session_state.cart = []
    st.session_state.selected_cust_id = None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1; st.session_state.ph_key += 1
    st.rerun()

@st.dialog("📦 ΕΛΕΥΘΕΡΟ ΕΙΔΟΣ (999)")
def manual_item_popup():
    st.write("Πείτε: '[Όνομα] και [Τιμή]'")
    st.components.v1.html("""
    <script>
    const recognition = new (window.webkitSpeechRecognition || window.Recognition)();
    recognition.lang = 'el-GR';
    recognition.onresult = function(event) {
        const text = event.results[0][0].transcript;
        const parent = window.parent.document;
        let parts = text.split(" και ");
        let name = parts[0] || "";
        let price = (parts[1] || "").replace(/[^0-9,.]/g, '').replace(',', '.');
        
        const inputs = parent.querySelectorAll('input');
        let nameInp, priceInp;
        inputs.forEach(input => {
            if (input.ariaLabel === "Όνομα Είδους") nameInp = input;
            if (input.type === "number") priceInp = input;
        });

        if (nameInp && priceInp) {
            // Virtual Typing για να το "νιώσει" το Streamlit
            nameInp.value = name;
            nameInp.dispatchEvent(new Event('input', { bubbles: true }));
            nameInp.dispatchEvent(new Event('change', { bubbles: true }));
            
            priceInp.value = price;
            priceInp.dispatchEvent(new Event('input', { bubbles: true }));
            priceInp.dispatchEvent(new Event('change', { bubbles: true }));
            
            // Κλικ στο κουμπί μετά από λίγο
            setTimeout(() => {
                const buttons = parent.querySelectorAll('button');
                buttons.forEach(btn => {
                    if (btn.innerText.includes("ΠΡΟΣΘΗΚΗ")) btn.click();
                });
            }, 600);
        }
    };
    </script>
    <button onclick="recognition.start()" style="width:100%; height:45px; border-radius:10px; background:#e74c3c; color:white; font-weight:bold; cursor:pointer; border:none; margin-bottom:10px;">🎤 ΦΩΝΗΤΙΚΗ ΕΝΤΟΛΗ</button>
    """, height=60)
    
    m_name = st.text_input("Όνομα Είδους")
    m_price = st.number_input("Τιμή (€)", min_value=0.0, format="%.2f", step=0.1)
    if st.button("ΠΡΟΣΘΗΚΗ", use_container_width=True):
        if m_name and m_price > 0:
            st.session_state.cart.append({'bc': '999', 'name': m_name, 'price': round(float(m_price), 2)})
            st.session_state.bc_key += 1; st.rerun()

@st.dialog("💰 ΠΛΗΡΩΜΗ")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center; color: #111;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    opt = st.radio("Έκπτωση;", ["ΟΧΙ", "ΝΑΙ"], horizontal=True)
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή % (π.χ. 10%)")
        if inp:
            try:
                if "%" in inp: disc = round((float(inp.replace("%",""))/100 * total), 2)
                else: disc = round(float(inp), 2)
            except: st.error("Σφάλμα τιμής")
    final_p = round(total - disc, 2)
    st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {final_p:.2f}€</div>", unsafe_allow_html=True)
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("💵 ΜΕΤΡΗΤΑ", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 ΚΑΡΤΑ", use_container_width=True): finalize(disc, "Κάρτα")

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
            if i['bc'] != '999':
                res = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
                if res.data: supabase.table("inventory").update({"stock": res.data[0]['stock'] - 1}).eq("barcode", i['bc']).execute()
        
        # 1. ΠΑΙΖΕΙ ΤΟΝ ΗΧΟ
        play_cash_sound()
        st.success("ΟΛΟΚΛΗΡΩΘΗΚΕ!")
        time.sleep(1.0) # Λίγος χρόνος να ακουστεί ο ήχος
        reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

# (Υπόλοιπο UI - Manager, Αποθήκη, κλπ παραμένουν ίδια)
with st.sidebar:
    st.markdown(f"<div class='sidebar-date'>📅 {get_athens_now().strftime('%d/%m/%Y')}</div>", unsafe_allow_html=True)
    st.title("CHERRY 14.1.9")
    view = st.radio("ΜΕΝΟΥ", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])
    if st.button("❌ ΕΞΟΔΟΣ", key="logout_btn", use_container_width=True): 
        st.session_state.is_logged_out = True
        st.rerun()

if view == "🛒 ΤΑΜΕΙΟ":
    st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
    cl, cr = st.columns([1, 1.5])
    with cl:
        if st.session_state.selected_cust_id is None:
            ph = st.text_input("Τηλέφωνο Πελάτη", key=f"ph_{st.session_state.ph_key}")
            if ph:
                res = supabase.table("customers").select("*").eq("phone", ph.strip()).execute()
                if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
            if st.button("🛒 ΛΙΑΝΙΚΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
        else:
            st.button(f"👤 {st.session_state.cust_name}", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
            bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
            if bc:
                if bc.strip() == "999": manual_item_popup()
                else:
                    res = supabase.table("inventory").select("*").eq("barcode", bc.strip()).execute()
                    if res.data:
                        item = res.data[0]
                        st.session_state.cart.append({'bc': item['barcode'], 'name': item['name'], 'price': round(float(item['price']), 2)})
                        st.session_state.bc_key += 1; st.rerun()
                    else: st.error("Σφάλμα!"); st.session_state.bc_key += 1
            if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
        if st.button("🗑️ ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
    with cr:
        total = sum(i['price'] for i in st.session_state.cart)
        st.markdown(f"<div class='cart-area'>{[i['name'] + ' | ' + str(i['price']) + '€' for i in st.session_state.cart]}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

# (Προσθήκη Manager, Αποθήκη αν χρειαστεί - Ο κώδικας v14.0.9 παραμένει ενεργός)
