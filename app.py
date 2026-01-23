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
st.set_page_config(page_title="CHERRY v14.0.59", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; font-size: 1.2rem !important; }
    .cart-area { font-family: 'Courier New', monospace; background-color: #2b2b2b; padding: 15px; border-radius: 5px; white-space: pre-wrap; border: 1px solid #3b3b3b; min-height: 200px; font-size: 14px; }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; margin: 10px 0; border: 2px solid #e44d26; padding: 10px; border-radius: 10px; background-color: #fff3f0; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; border: 1px solid #ffffff !important; font-weight: bold !important; }
    .data-row { background-color: #262626; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; text-align: left; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    
    /* Κρύψιμο του βοηθητικού input για τις φωνητικές εντολές */
    div[data-testid="stTextInput"]:has(input[aria-label="voice_trigger"]) {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'is_logged_out' not in st.session_state: st.session_state.is_logged_out = False

# --- 3. EXPERIMENTAL VOICE COMPONENT ---
def voice_commander_ui():
    # JavaScript logic to capture speech and inject it into a Streamlit input
    st.components.v1.html("""
    <script>
    const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = 'el-GR';
    recognition.interimResults = false;

    function startDictation() {
        recognition.start();
        const btn = document.getElementById('voice-btn');
        btn.innerHTML = "🔴 ΑΚΟΥΩ...";
        btn.style.backgroundColor = "#ff0000";
    }

    recognition.onresult = (event) => {
        const text = event.results[0][0].transcript.toLowerCase();
        const mainDoc = window.parent.document;
        // Βρίσκουμε το κρυφό input του Streamlit
        const inputs = mainDoc.querySelectorAll('input');
        for (let input of inputs) {
            if (input.ariaLabel === "voice_trigger") {
                input.value = text;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                // Προσομοίωση Enter
                const ke = new KeyboardEvent('keydown', { bubbles: true, cancelable: true, keyCode: 13, key: 'Enter' });
                input.dispatchEvent(ke);
                break;
            }
        }
        stopDictation();
    };

    function stopDictation() {
        recognition.stop();
        const btn = document.getElementById('voice-btn');
        btn.innerHTML = "🎤 ΦΩΝΗΤΙΚΗ ΕΝΤΟΛΗ";
        btn.style.backgroundColor = "#e74c3c";
    }

    recognition.onerror = () => stopDictation();
    recognition.onend = () => stopDictation();
    </script>
    <button id="voice-btn" onclick="startDictation()" 
            style="width: 100%; height: 50px; background-color: #e74c3c; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; font-family: sans-serif;">
        🎤 ΦΩΝΗΤΙΚΗ ΕΝΤΟΛΗ
    </button>
    """, height=60)

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

def play_sound(url):
    st.components.v1.html(f"""<audio autoplay style="display:none"><source src="{url}" type="audio/mpeg"></audio>""", height=0)

@st.dialog("➕ Χειροκίνητο Είδος (999)")
def manual_item_popup():
    m_name = st.text_input("Όνομα Είδους")
    m_price = st.number_input("Τιμή (€)", min_value=0.0, format="%.2f", step=0.1)
    if st.button("Προσθήκη", use_container_width=True):
        if m_name:
            st.session_state.cart.append({'bc': '999', 'name': m_name, 'price': round(float(m_price), 2)})
            st.session_state.bc_key += 1; st.rerun()

def finalize(disc_val, method):
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    try:
        for i in st.session_state.cart:
            d = round(i['price'] * ratio, 2); f = round(i['price'] - d, 2)
            data = {"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": float(d), "final_item_price": float(f), "method": str(method), "s_date": ts, "cust_id": c_id}
            supabase.table("sales").insert(data).execute()
        st.balloons(); play_sound("https://www.soundjay.com/misc/sounds/magic-chime-01.mp3"); time.sleep(1.0); reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

# --- 5. MAIN UI ---
if st.session_state.is_logged_out:
    st.markdown("<h1 style='text-align: center;'>Αποσυνδεθήκατε</h1>", unsafe_allow_html=True)
    if st.button("Επανασύνδεση"): st.session_state.is_logged_out = False; st.rerun()
else:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-date'>{get_athens_now().strftime('%d/%m/%Y %H:%M:%S')}</div>", unsafe_allow_html=True)
        st.title("CHERRY 14.0.59")
        view = st.radio("ΜΕΝΟΥ", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])
        voice_commander_ui()
        # Κρυφό input που δέχεται την εντολή από την JavaScript
        v_input = st.text_input("voice_trigger", key="v_trig", label_visibility="collapsed")
        if v_input:
            if "διαγραφή" in v_input or "άδειασμα" in v_input:
                st.session_state.cart = []
                st.toast("🧹 Το καλάθι άδειασε!")
            elif "λιανική" in v_input:
                st.session_state.selected_cust_id = 0
                st.toast("👤 Λιανική Πώληση")
        
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
                        if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                    elif len(clean_ph) > 0: st.error("Απαιτούνται 10 ψηφία!")
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name} (Αλλαγή)", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    if bc.strip() == "999": manual_item_popup()
                    else:
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
    
    # Οι υπόλοιπες σελίδες (MANAGER, ΑΠΟΘΗΚΗ κλπ) παραμένουν ίδιες...
