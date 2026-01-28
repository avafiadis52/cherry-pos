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

# --- 3. CONFIG & STYLE (Version v14.2.29) ---
st.set_page_config(page_title="CHERRY v14.2.29", layout="wide", page_icon="🍒")

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
        height: 45px;
    }
    
    /* Style για το ενεργό κουμπί επιστροφής */
    .stButton > button.return-active {
        background-color: #e74c3c !important;
        color: white !important;
        border: 2px solid #ffffff !important;
    }

    .data-row { 
        font-family: 'Courier New', monospace;
        background-color: #262626; 
        padding: 12px; 
        border-radius: 8px; 
        margin-bottom: 5px; 
        border-left: 5px solid #3498db;
        display: block;
        white-space: pre;
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

def speak_text(text_to_say, play_beep=True):
    beep_js = "var context = new (window.AudioContext || window.webkitAudioContext)(); var osc = context.createOscillator(); osc.type = 'sawtooth'; osc.frequency.setValueAtTime(150, context.currentTime); osc.connect(context.destination); osc.start(); osc.stop(context.currentTime + 0.2);" if play_beep else ""
    speech_js = f"var msg = new SpeechSynthesisUtterance('{text_to_say}'); msg.lang = 'el-GR'; window.speechSynthesis.speak(msg);" if text_to_say else ""
    st.components.v1.html(f"<script>{beep_js}{speech_js}</script>", height=0)

def finalize(disc_val, method):
    if not supabase: return
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    c_id = int(st.session_state.selected_cust_id) if (st.session_state.selected_cust_id and st.session_state.selected_cust_id != 0) else None
    
    try:
        for i in st.session_state.cart:
            d = round(i['price'] * ratio, 2)
            f = round(i['price'] - d, 2)
            stock_change = 1 if f < 0 else -1
            
            data = {"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": float(d), "final_item_price": float(f), "method": str(method), "s_date": ts, "cust_id": c_id}
            supabase.table("sales").insert(data).execute()
            
            if i['bc'] != 'VOICE':
                res_inv = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
                if res_inv.data:
                    new_stock = int(res_inv.data[0]['stock']) + stock_change
                    supabase.table("inventory").update({"stock": new_stock}).eq("barcode", i['bc']).execute()

        st.success("✅ Η ΣΥΝΑΛΛΑΓΗ ΟΛΟΚΛΗΡΩΘΗΚΕ"); st.balloons()
        speak_text("Επιτυχία", play_beep=False)
        time.sleep(1.5); reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    final_p = total
    st.markdown(f"<div class='final-amount-popup'>ΠΟΣΟ: {final_p:.2f}€</div>", unsafe_allow_html=True)
    st.divider()
    c1, c2 = st.columns(2)
    label_m = "💵 ΕΠΙΣΤΡΟΦΗ ΜΕΤΡ." if final_p < 0 else "💵 ΜΕΤΡΗΤΑ"
    label_c = "💳 ΕΠΙΣΤΡΟΦΗ ΚΑΡΤΑ" if final_p < 0 else "💳 ΚΑΡΤΑ"
    if c1.button(label_m, use_container_width=True): finalize(0, "Μετρητά")
    if c2.button(label_c, use_container_width=True): finalize(0, "Κάρτα")

# --- 5. MAIN UI ---
if st.session_state.is_logged_out:
    st.markdown("<h1 style='text-align:center;color:#e74c3c;'>Αποσυνδεθήκατε</h1>", unsafe_allow_html=True)
    if st.button("Επανασύνδεση"): st.session_state.is_logged_out = False; st.rerun()
else:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-date'>{get_athens_now().strftime('%d/%m/%Y %H:%M:%S')}</div>", unsafe_allow_html=True)
        st.subheader("🎙️ Φωνητική Εντολή")
        if HAS_MIC:
            text = speech_to_text(language='el', start_prompt="🔴 ΠΑΤΑ ΚΑΙ ΜΙΛΑ", key=f"voice_{st.session_state.mic_key}")
            if text:
                raw_query = text.lower().strip()
                numbers = re.findall(r"[-+]?\d*\.\d+|\d+", raw_query)
                found_price = float(numbers[0]) if numbers else None
                if found_price:
                    final_price = -abs(found_price) if st.session_state.return_mode else abs(found_price)
                    name_prefix = "🔄 " if st.session_state.return_mode else ""
                    st.session_state.cart.append({'bc': 'VOICE', 'name': f"{name_prefix}ΦΩΝΗΤΙΚΗ ΠΩΛΗΣΗ", 'price': final_price})
                    st.session_state.mic_key += 1; time.sleep(0.4); st.rerun()

        st.divider()
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])
        if st.button("❌ Έξοδος", use_container_width=True):
            st.session_state.cart = []; st.session_state.is_logged_out = True; st.rerun()

    if view == "🛒 ΤΑΜΕΙΟ":
        st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο (10 ψηφία)", key=f"ph_{st.session_state.ph_key}")
                if ph:
                    clean_ph = ''.join(filter(str.isdigit, ph))
                    if len(clean_ph) == 10:
                        res = supabase.table("customers").select("*").eq("phone", clean_ph).execute()
                        if res.data:
                            st.session_state.selected_cust_id = int(res.data[0]['id'])
                            st.session_state.cust_name = res.data[0]['name']
                            st.rerun()
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name} (Αλλαγή)", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                
                # --- ΕΔΩ ΕΙΝΑΙ ΤΟ ΚΟΥΜΠΙ ΠΟΥ ΕΛΕΙΠΕ ---
                btn_label = "🚨 ΛΕΙΤΟΥΡΓΙΑ ΕΠΙΣΤΡΟΦΗΣ: ON" if st.session_state.return_mode else "🔄 ΕΠΙΣΤΡΟΦΗ ΕΙΔΟΥΣ"
                if st.button(btn_label, use_container_width=True):
                    st.session_state.return_mode = not st.session_state.return_mode
                    st.rerun()
                # -------------------------------------

                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc and supabase:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        price = float(res.data[0]['price'])
                        final_price = -abs(price) if st.session_state.return_mode else abs(price)
                        name_prefix = "🔄 " if st.session_state.return_mode else ""
                        st.session_state.cart.append({'bc': res.data[0]['barcode'], 'name': name_prefix + res.data[0]['name'].upper(), 'price': final_price})
                        st.session_state.bc_key += 1; st.rerun()
                    else: st.error("Το Barcode δεν βρέθηκε!")
                
                for idx, item in enumerate(st.session_state.cart):
                    if st.button(f"❌ {item['name']} {item['price']}€", key=f"del_{idx}", use_container_width=True):
                        st.session_state.cart.pop(idx); st.rerun()
                
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ / ΟΛΟΚΛΗΡΩΣΗ", use_container_width=True): payment_popup()
            if st.button("🔄 ΑΚΥΡΩΣΗ ΟΛΩΝ", use_container_width=True): reset_app()
        
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            lines = [f"{i['name'][:20]:<20} | {i['price']:>6.2f}€" for i in st.session_state.cart]
            st.markdown(f"<div class='cart-area'>{'Είδος':<20} | {'Τιμή':>6}\n{'-'*30}\n{chr(10).join(lines)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif view == "📊 MANAGER" and supabase:
        st.title("📊 Αναφορές")
        res_s = supabase.table("sales").select("*").execute()
        if res_s.data:
            df = pd.DataFrame(res_s.data)
            df['s_date_dt'] = pd.to_datetime(df['s_date'])
            df['ΗΜΕΡΟΜΗΝΙΑ'] = df['s_date_dt'].dt.date
            today_date = get_athens_now().date()
            tdf = df[df['ΗΜΕΡΟΜΗΝΙΑ'] == today_date].copy()
            st.markdown(f"""<div style='background-color:#262730; padding:20px; border-radius:10px; text-align:center;'>
                <div style='color:#2ecc71; font-weight:bold;'>ΚΑΘΑΡΟΣ ΤΖΙΡΟΣ ΗΜΕΡΑΣ</div>
                <div style='font-size:40px; font-weight:bold;'>{tdf['final_item_price'].sum():.2f}€</div>
            </div>""", unsafe_allow_html=True)
            st.dataframe(tdf[['s_date', 'item_name', 'final_item_price', 'method']].sort_values('s_date', ascending=False), use_container_width=True, hide_index=True)

    elif view == "📦 ΑΠΟΘΗΚΗ" and supabase:
        st.title("📦 Αποθήκη")
        res = supabase.table("inventory").select("*").execute()
        if res.data:
            df_inv = pd.DataFrame(res.data)
            st.dataframe(df_inv[['barcode', 'name', 'price', 'stock']], use_container_width=True, hide_index=True)
