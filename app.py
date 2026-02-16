import pandas as pd
from datetime import datetime, date, timedelta
import time
import streamlit as st
from supabase import create_client, Client
import re
import plotly.express as px

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
st.set_page_config(page_title="CHERRY v14.2.63", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; }
    .cart-area { font-family: 'Courier New', monospace; background-color: #000000; padding: 15px; border-radius: 10px; white-space: pre-wrap; border: 4px solid #2ecc71 !important; box-shadow: 0 0 15px rgba(46, 204, 113, 0.4); min-height: 300px; font-size: 16px; color: #2ecc71; }
    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; margin-top: 10px; text-shadow: 2px 2px 10px rgba(46, 204, 113, 0.5); }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; padding: 10px; border-radius: 10px; background-color: #fff3f0; border: 2px solid #e44d26; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; font-weight: bold !important; border: 1px solid #808080 !important; }
    .data-row { font-family: 'Courier New', monospace; background-color: #262626; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; display: block; white-space: pre; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    .report-stat { background-color: #262730; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; }
    .day-header { background-color: #34495e; color: #f1c40f; padding: 10px; border-radius: 5px; margin-top: 25px; margin-bottom: 10px; font-weight: bold; border-left: 8px solid #f1c40f; }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
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
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    try:
        for i in st.session_state.cart:
            d = round(i['price'] * ratio, 2)
            f = round(i['price'] - d, 2)
            supabase.table("sales").insert({"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": float(d), "final_item_price": float(f), "method": str(method), "s_date": ts, "cust_id": c_id}).execute()
            if i['bc'] != 'VOICE':
                res_inv = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
                if res_inv.data:
                    ch = 1 if i['price'] < 0 else -1
                    supabase.table("inventory").update({"stock": int(res_inv.data[0]['stock']) + ch}).eq("barcode", i['bc']).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); st.balloons(); time.sleep(1.5); reset_app()
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
            except: pass
    st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {total-disc:.2f}€</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

# --- 5. LOGIN ---
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.title("🔒 CHERRY")
        if st.text_input("Password", type="password") == "CHERRY123":
            if st.button("Είσοδος"): st.session_state.logged_in = True; st.rerun()
else:
    # --- 6. MAIN UI ---
    with st.sidebar:
        st.markdown(f"<div class='sidebar-date'>{get_athens_now().strftime('%d/%m/%Y %H:%M:%S')}</div>", unsafe_allow_html=True)
        if HAS_MIC:
            t = speech_to_text(language='el', key=f"v_{st.session_state.mic_key}")
            if t:
                nums = re.findall(r"\d+\.?\d*", t)
                if nums:
                    p = float(nums[0])
                    st.session_state.cart.append({'bc':'VOICE', 'name':t.upper(), 'price': -p if st.session_state.return_mode else p})
                    st.session_state.mic_key += 1; st.rerun()
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        if st.button("❌ Έξοδος"): st.session_state.logged_in = False; st.rerun()

    if view in ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ"]:
        st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"ph_{st.session_state.ph_key}")
                if ph and len(ph)==10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                if st.button("🛒 ΛΙΑΝΙΚΗ"): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        val = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'bc': bc, 'name': res.data[0]['name'], 'price': val})
                        st.session_state.bc_key += 1; st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ"): payment_popup()
                if st.button("🔄 ΑΚΥΡΩΣΗ"): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            lines = [f"{i['name'][:20]:20} | {i['price']:>6.2f}€" for i in st.session_state.cart]
            st.markdown(f"<div class='cart-area'>{'Είδος':20} | {'Τιμή':>6}\n{'-'*30}\n" + "\n".join(lines) + "</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif view == "📊 MANAGER":
        res_s = supabase.table("sales").select("*").execute()
        if res_s.data:
            df = pd.DataFrame(res_s.data)
            df['s_date_dt'] = pd.to_datetime(df['s_date'])
            df['ΗΜΕΡΟΜΗΝΙΑ'] = df['s_date_dt'].dt.date
            t1, t2, t3 = st.tabs(["📅 ΣΗΜΕΡΑ", "📆 ΠΕΡΙΟΔΟΣ", "📈 INSIGHTS"])
            with t1:
                tdf = df[df['ΗΜΕΡΟΜΗΝΙΑ'] == get_athens_now().date()]
                if not tdf.empty:
                    st.markdown(f"<div class='report-stat'>ΤΖΙΡΟΣ: {tdf['final_item_price'].sum():.2f}€</div>", unsafe_allow_html=True)
                    st.dataframe(tdf, use_container_width=True)
            with t2:
                sd, ed = st.date_input("Από", get_athens_now().date()-timedelta(7)), st.date_input("Έως", get_athens_now().date())
                pdf = df[(df['ΗΜΕΡΟΜΗΝΙΑ'] >= sd) & (df['ΗΜΕΡΟΜΗΝΙΑ'] <= ed)]
                st.markdown(f"<div class='report-stat' style='border:2px solid #3498db;'>ΣΥΝΟΛΟ ΠΕΡΙΟΔΟΥ: {pdf['final_item_price'].sum():.2f}€</div>", unsafe_allow_html=True)
                for d in sorted(pdf['ΗΜΕΡΟΜΗΝΙΑ'].unique(), reverse=True):
                    ddf = pdf[pdf['ΗΜΕΡΟΜΗΝΙΑ'] == d]
                    st.markdown(f"<div class='day-header'>📅 {d.strftime('%d/%m/%Y')}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='report-stat'>ΤΖΙΡΟΣ ΗΜΕΡΑΣ: {ddf['final_item_price'].sum():.2f}€</div>", unsafe_allow_html=True)
                    c1, c2, c3 = st.columns(3)
                    c1.markdown(f"<div class='report-stat'>💵 Μετρητά: {ddf[ddf['method']=='Μετρητά']['final_item_price'].sum():.2f}€</div>", unsafe_allow_html=True)
                    c2.markdown(f"<div class='report-stat'>💳 Κάρτα: {ddf[ddf['method']=='Κάρτα']['final_item_price'].sum():.2f}€</div>", unsafe_allow_html=True)
                    c3.markdown(f"<div class='report-stat'>📉 Εκπτώσεις: {ddf['discount'].sum():.2f}€</div>", unsafe_allow_html=True)
            with t3:
                fig = px.pie(df, values='final_item_price', names='method', title='Τζίρος ανά Μέθοδο')
                st.plotly_chart(fig)

    elif view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Αποθήκη")
        res = supabase.table("inventory").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data), use_container_width=True)

    elif view == "👥 ΠΕΛΑΤΕΣ":
        st.title("👥 Πελάτες")
        res = supabase.table("customers").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data), use_container_width=True)
