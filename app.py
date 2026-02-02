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

# --- 3. CONFIG & STYLE (Version v14.2.38 - Total Black Edition) ---
st.set_page_config(page_title="CHERRY v14.2.38", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    /* Total Black Theme */
    .stApp { background-color: #000000; color: #e0e0e0; }
    
    /* Input & Labels */
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; }
    input { background-color: #1a1a1a !important; color: #ffffff !important; border: 1px solid #333 !important; }
    
    /* Cart Area */
    .cart-area { 
        font-family: 'Courier New', monospace; 
        background-color: #000000; 
        padding: 15px; 
        border-radius: 10px; 
        white-space: pre-wrap; 
        border: 2px solid #2ecc71 !important; 
        box-shadow: 0 0 10px rgba(46, 204, 113, 0.2); 
        min-height: 300px; 
        font-size: 16px;
        color: #2ecc71; 
    }

    .total-label { font-size: 75px; font-weight: bold; color: #2ecc71; text-align: center; margin-top: 10px; text-shadow: 2px 2px 15px rgba(46, 204, 113, 0.4); }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    
    /* Buttons */
    div.stButton > button { 
        background-color: #1a1a1a !important; 
        color: #ffffff !important; 
        border: 1px solid #444 !important;
        transition: 0.3s;
    }
    div.stButton > button:hover { border-color: #2ecc71 !important; color: #2ecc71 !important; }
    
    /* Reports & Boxes */
    .report-stat { 
        background-color: #0a0a0a; 
        padding: 15px; 
        border-radius: 8px; 
        text-align: center; 
        border: 1px solid #333; 
        margin-bottom: 10px; 
    }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; }
    .stat-desc { font-size: 12px; color: #666; }
    .day-header { background-color: #1a1a1a; color: #f1c40f; padding: 8px 15px; border-radius: 5px; margin-top: 25px; margin-bottom: 10px; font-weight: bold; border-left: 5px solid #f1c40f; }
    
    /* Data Rows */
    .data-row { 
        font-family: 'Courier New', monospace;
        background-color: #0a0a0a; 
        padding: 12px; 
        border-radius: 8px; 
        margin-bottom: 5px; 
        border: 1px solid #222;
        border-left: 4px solid #3498db;
    }
    
    /* Sidebar */
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; margin-bottom: 20px; border-bottom: 1px solid #333; padding-bottom: 10px; }
    
    /* Tables */
    [data-testid="stDataFrame"] { background-color: #000000 !important; }
    </style>
    """, unsafe_allow_html=True)

# Session States initialization
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
    beep_js = "var c=new AudioContext(); var o=c.createOscillator(); o.type='sawtooth'; o.frequency.setValueAtTime(150,c.currentTime); o.connect(c.destination); o.start(); o.stop(c.currentTime+0.2);" if play_beep else ""
    speech_js = f"var m=new SpeechSynthesisUtterance('{text_to_say}'); m.lang='el-GR'; window.speechSynthesis.speak(m);" if text_to_say else ""
    st.components.v1.html(f"<script>{beep_js}{speech_js}</script>", height=0)

def finalize(disc_val, method):
    if not supabase: return
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
            if i['bc'] != 'VOICE':
                res_inv = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
                if res_inv.data:
                    change = 1 if i['price'] < 0 else -1
                    supabase.table("inventory").update({"stock": int(res_inv.data[0]['stock']) + change}).eq("barcode", i['bc']).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); st.balloons()
        speak_text("Επιτυχής Πληρωμή", play_beep=False)
        time.sleep(1.5); reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    opt = st.radio("Έκπτωση;", ["ΟΧΙ", "ΝΑΙ"], horizontal=True)
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή %")
        if inp:
            try:
                disc = round((float(inp.replace("%",""))/100 * total), 2) if "%" in inp else round(float(inp), 2)
            except: st.error("Σφάλμα")
    final_p = round(total - disc, 2)
    st.markdown(f"<div style='font-size:35px; color:#e44d26; text-align:center; font-weight:bold; margin:10px;'>ΠΛΗΡΩΤΕΟ: {final_p:.2f}€</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

# --- 5. MAIN UI ---
if st.session_state.is_logged_out:
    st.button("Επανασύνδεση", on_click=lambda: st.session_state.update({"is_logged_out": False}))
else:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-date'>{get_athens_now().strftime('%d/%m/%Y %H:%M:%S')}</div>", unsafe_allow_html=True)
        if HAS_MIC:
            text = speech_to_text(language='el', start_prompt="🎙️ ΦΩΝΗΤΙΚΗ ΕΝΤΟΛΗ", key=f"v_{st.session_state.mic_key}")
            if text:
                nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
                if nums:
                    p = float(nums[0])
                    st.session_state.cart.append({'bc':'VOICE', 'name': text.upper(), 'price': -p if st.session_state.return_mode else p})
                    st.session_state.mic_key += 1; st.rerun()

        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ", "⚙️ SYSTEM"], key="sidebar_nav")
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        if st.button("❌ Έξοδος", use_container_width=True): st.session_state.is_logged_out = True; st.rerun()

    current_view = view if view != "🔄 ΕΠΙΣΤΡΟΦΗ" else "🛒 ΤΑΜΕΙΟ"

    if current_view == "🛒 ΤΑΜΕΙΟ":
        if st.session_state.return_mode: st.error("⚠️ ΛΕΙΤΟΥΡΓΙΑ ΕΠΙΣΤΡΟΦΗΣ")
        else: st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
            
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"ph_{st.session_state.ph_key}")
                if ph and len(ph) == 10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data:
                        st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                if st.button("🛒 ΛΙΑΝΙΚΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name} (Αλλαγή)", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        val = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'bc': bc, 'name': res.data[0]['name'].upper(), 'price': val})
                        st.session_state.bc_key += 1; st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
                if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            lines = [f"{i['name'][:20]:<20} | {i['price']:>6.2f}€" for i in st.session_state.cart]
            st.markdown(f"<div class='cart-area'>{'Είδος':<20} | {'Τιμή':>6}\n{'-'*30}\n{chr(10).join(lines)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif current_view == "📊 MANAGER" and supabase:
        res_s = supabase.table("sales").select("*").execute()
        if res_s.data:
            df = pd.DataFrame(res_s.data)
            df['ΗΜΕΡΟΜΗΝΙΑ'] = pd.to_datetime(df['s_date']).dt.date
            t1, t2 = st.tabs(["📅 ΣΗΜΕΡΑ", "📆 ΠΕΡΙΟΔΟΣ"])
            with t1:
                today = get_athens_now().date()
                tdf = df[df['ΗΜΕΡΟΜΗΝΙΑ'] == today]
                st.metric("ΣΥΝΟΛΟ ΗΜΕΡΑΣ", f"{tdf['final_item_price'].sum():.2f}€")
                st.dataframe(tdf, use_container_width=True, hide_index=True)
            with t2:
                cs, ce = st.columns(2); sd, ed = cs.date_input("Από", date.today()-timedelta(7)), ce.date_input("Έως", date.today())
                pdf = df[(df['ΗΜΕΡΟΜΗΝΙΑ'] >= sd) & (df['ΗΜΕΡΟΜΗΝΙΑ'] <= ed)].sort_values('s_date', ascending=False)
                st.markdown(f"<div class='report-stat' style='border-color:#3498db;'><div class='stat-val'>{pdf['final_item_price'].sum():.2f}€</div><div class='stat-desc'>Τζίρος Περιόδου</div></div>", unsafe_allow_html=True)
                
                for d in sorted(pdf['ΗΜΕΡΟΜΗΝΙΑ'].unique(), reverse=True):
                    st.markdown(f"<div class='day-header'>📅 {d.strftime('%d/%m/%Y')}</div>", unsafe_allow_html=True)
                    ddf = pdf[pdf['ΗΜΕΡΟΜΗΝΙΑ'] == d]
                    m_val = ddf[ddf['method']=='Μετρητά']['final_item_price'].sum()
                    k_val = ddf[ddf['method']=='Κάρτα']['final_item_price'].sum()
                    c1, c2 = st.columns(2)
                    c1.markdown(f"<div class='report-stat'>💵 Μετρητά: <b>{m_val:.2f}€</b></div>", unsafe_allow_html=True)
                    c2.markdown(f"<div class='report-stat'>💳 Κάρτα: <b>{k_val:.2f}€</b></div>", unsafe_allow_html=True)
                    st.dataframe(ddf[['item_name', 'final_item_price', 'method']], use_container_width=True, hide_index=True)

    elif current_view == "📦 ΑΠΟΘΗΚΗ":
        res = supabase.table("inventory").select("*").execute()
        if res.data:
            df_i = pd.DataFrame(res.data).sort_values('name')
            for _, r in df_i.iterrows():
                st.markdown(f"<div class='data-row'>📦 {r['barcode']} | {r['name']} | {r['price']}€ | Stock: {r['stock']}</div>", unsafe_allow_html=True)

    elif current_view == "👥 ΠΕΛΑΤΕΣ":
        res_c = supabase.table("customers").select("*").execute()
        if res_c.data:
            for r in res_c.data:
                st.markdown(f"<div class='data-row'>👤 {r['name']} | 📞 {r['phone']}</div>", unsafe_allow_html=True)
