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
except Exception: HAS_MIC = False

# --- 2. SUPABASE SETUP ---
SUPABASE_URL = "https://hnwynihjkdkryrfepenh.supabase.co"
SUPABASE_KEY = "sb_publishable_ualF72lJKgUQA4TzjPQ-OA_zih7zJ-s"

@st.cache_resource
def init_supabase():
    try: return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception: return None

supabase = init_supabase()

# --- 3. CONFIG & STYLE (Version v14.2.48) ---
st.set_page_config(page_title="CHERRY v14.2.48", layout="wide", page_icon="🍒")
st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; }
    .cart-area { font-family: 'Courier New', monospace; background-color: #000; padding: 15px; border-radius: 10px; white-space: pre-wrap; border: 4px solid #2ecc71 !important; box-shadow: 0 0 15px rgba(46,204,113,0.4); min-height: 300px; font-size: 16px; color: #2ecc71; }
    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; margin-top: 10px; text-shadow: 2px 2px 10px rgba(46,204,113,0.5); }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; padding: 10px; border-radius: 10px; background-color: #fff3f0; border: 2px solid #e44d26; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000 !important; border-radius: 8px !important; font-weight: bold !important; border: 1px solid #808080 !important; }
    .data-row { font-family: 'Courier New', monospace; background-color: #262626; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; display: block; white-space: pre; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    .report-stat { background-color: #262730; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; }
    .day-header { background-color: #34495e; color: #f1c40f; padding: 10px; border-radius: 5px; margin-top: 25px; margin-bottom: 10px; font-weight: bold; border-left: 8px solid #f1c40f; }
    </style>
    """, unsafe_allow_html=True)

# Session States
for k, v in {'cart':[], 'selected_cust_id':None, 'cust_name':"Λιανική Πώληση", 'bc_key':0, 'ph_key':100, 'is_logged_out':False, 'mic_key':28000, 'return_mode':False}.items():
    if k not in st.session_state: st.session_state[k] = v

def get_athens_now(): return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.update({'cart':[], 'selected_cust_id':None, 'cust_name':"Λιανική Πώληση", 'return_mode':False})
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1; st.rerun()

def speak_text(text, play_beep=True):
    b_js = "var ctx = new (window.AudioContext || window.webkitAudioContext)(); var osc = ctx.createOscillator(); osc.type = 'sawtooth'; osc.frequency.setValueAtTime(150, ctx.currentTime); osc.connect(ctx.destination); osc.start(); osc.stop(ctx.currentTime + 0.2);" if play_beep else ""
    s_js = f"var m = new SpeechSynthesisUtterance('{text}'); m.lang = 'el-GR'; window.speechSynthesis.speak(m);" if text else ""
    st.components.v1.html(f"<script>{b_js}{s_js}</script>", height=0)

def finalize(disc, method):
    if not supabase: return
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc/sub if sub > 0 else 0
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    try:
        for i in st.session_state.cart:
            d = round(i['price']*ratio, 2); f = round(i['price']-d, 2)
            supabase.table("sales").insert({"barcode":str(i['bc']), "item_name":str(i['name']), "unit_price":float(i['price']), "discount":float(d), "final_item_price":float(f), "method":str(method), "s_date":ts, "cust_id":c_id}).execute()
            if i['bc'] != 'VOICE':
                res = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
                if res.data:
                    ch = 1 if i['price'] < 0 else -1
                    supabase.table("inventory").update({"stock": int(res.data[0]['stock'])+ch}).eq("barcode", i['bc']).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); st.balloons(); speak_text("Επιτυχής Πληρωμή", False); time.sleep(1.5); reset_app()
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
            try: disc = round((float(inp.replace("%",""))/100 * total),2) if "%" in inp else round(float(inp),2)
            except: st.error("Σφάλμα")
    st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {total-disc:.2f}€</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

if st.session_state.is_logged_out:
    if st.button("Επανασύνδεση"): st.session_state.is_logged_out = False; st.rerun()
else:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-date'>{get_athens_now().strftime('%d/%m/%Y %H:%M:%S')}</div>", unsafe_allow_html=True)
        if HAS_MIC:
            t = speech_to_text(language='el', key=f"v_{st.session_state.mic_key}")
            if t:
                nums = re.findall(r"\d+\.?\d*", t)
                if nums:
                    p = float(nums[0]); val = -p if st.session_state.return_mode else p
                    st.session_state.cart.append({'bc':'VOICE', 'name':t.upper(), 'price':val})
                    st.session_state.mic_key += 1; st.rerun()
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ", "⚙️ SYSTEM"], index=1 if st.session_state.return_mode else 0)
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        if st.button("❌ Έξοδος"): st.session_state.is_logged_out = True; st.rerun()

    cv = view if view != "🔄 ΕΠΙΣΤΡΟΦΗ" else "🛒 ΤΑΜΕΙΟ"
    if cv == "🛒 ΤΑΜΕΙΟ":
        if st.session_state.return_mode: st.error("⚠️ ΛΕΙΤΟΥΡΓΙΑ ΕΠΙΣΤΡΟΦΗΣ")
        else: st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"p_{st.session_state.ph_key}")
                if ph and len(ph)==10:
                    r = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if r.data: st.session_state.update({'selected_cust_id':r.data[0]['id'], 'cust_name':r.data[0]['name']}); st.rerun()
                if st.button("🛒 ΛΙΑΝΙΚΗ"): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                bc = st.text_input("Barcode", key=f"b_{st.session_state.bc_key}")
                if bc:
                    r = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if r.data:
                        v = -float(r.data[0]['price']) if st.session_state.return_mode else float(r.data[0]['price'])
                        st.session_state.cart.append({'bc':r.data[0]['barcode'], 'name':r.data[0]['name'].upper(), 'price':v})
                        st.session_state.bc_key += 1; st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ"): payment_popup()
                if st.button("🔄 ΑΚΥΡΩΣΗ"): reset_app()
        with cr:
            tot = sum(i['price'] for i in st.session_state.cart)
            txt = "\n".join([f"{i['name'][:15]:15} | {i['price']:>6.2f}€" for i in st.session_state.cart])
            st.markdown(f"<div class='cart-area'>Είδος           | Τιμή\n{'-'*28}\n{txt}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{tot:.2f}€</div>", unsafe_allow_html=True)

    elif cv == "📊 MANAGER":
        res = supabase.table("sales").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data); df['dt'] = pd.to_datetime(df['s_date']); df['D'] = df['dt'].dt.date
            today = get_athens_now().date()
            t1, t2 = st.tabs(["📅 ΣΗΜΕΡΑ", "📆 ΠΕΡΙΟΔΟΣ"])
            with t1:
                tdf = df[df['D'] == today]
                st.metric("Τζίρος", f"{tdf['final_item_price'].sum():.2f}€")
                st.dataframe(tdf[['item_name','final_item_price','method']].sort_index(ascending=False), use_container_width=True)
            with t2:
                sd = st.date_input("Από", today-timedelta(days=7))
                pdf = df[df['D'] >= sd].sort_values('dt', ascending=False)
                for d in sorted(pdf['D'].unique(), reverse=True):
                    ddf = pdf[pdf['D'] == d]
                    st.markdown(f"<div class='day-header'>{d} | {ddf['final_item_price'].sum():.2f}€</div>", unsafe_allow_html=True)
                    st.dataframe(ddf[['item_name','final_item_price','method']], hide_index=True)

    elif cv == "📦 ΑΠΟΘΗΚΗ":
        c1,c2,c3 = st.columns(3)
        nb, nn, np = c1.text_input("BC"), c2.text_input("Όνομα"), c3.number_input("Τιμή")
        if st.button("Προσθήκη"):
            supabase.table("inventory").upsert({"barcode":nb, "name":nn.upper(), "price":np, "stock":100}).execute(); st.rerun()
        r = supabase.table("inventory").select("*").execute()
        if r.data: st.dataframe(pd.DataFrame(r.data)[['barcode','name','price','stock']])

    elif cv == "⚙️ SYSTEM":
        st.title("⚙️ SYSTEM")
        if st.text_input("Pass", type="password") == "999":
            tbl = st.selectbox("Πίνακας", ["---", "Sales", "Customers", "Inventory"])
            if tbl != "---" and st.text_input("Γράψε ΔΙΑΓΡΑΦΗ") == "ΔΙΑΓΡΑΦΗ":
                if st.button("🚀 ΕΚΤΕΛΕΣΗ"):
                    supabase.table(tbl.lower()).delete().neq("id", -1).execute()
                    st.success(f"✅ {tbl} ΔΙΑΓΡΑΦΗΚΕ"); time.sleep(1); st.rerun()
