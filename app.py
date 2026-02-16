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
    try: return create_client(SUPABASE_URL, SUPABASE_KEY)
    except: return None

supabase = init_supabase()

# --- 3. CONFIG & STYLE ---
st.set_page_config(page_title="CHERRY v14.2.63", layout="wide", page_icon="🍒")
st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; }
    input { color: #000000 !important; font-weight: bold !important; }
    .cart-area { font-family: monospace; background-color: #000; padding: 15px; border-radius: 10px; border: 4px solid #2ecc71 !important; color: #2ecc71; min-height: 250px; }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    .report-stat { background-color: #262730; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 5px; }
    .stat-val { font-size: 22px; font-weight: bold; color: #2ecc71; }
    .day-header { background-color: #34495e; color: #f1c40f; padding: 8px; border-radius: 5px; margin-top: 20px; font-weight: bold; }
    .data-row { font-family: monospace; background-color: #262626; padding: 10px; border-radius: 5px; margin-bottom: 4px; border-left: 5px solid #3498db; }
    </style>
    """, unsafe_allow_html=True)

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'mic_key' not in st.session_state: st.session_state.mic_key = 28000
if 'return_mode' not in st.session_state: st.session_state.return_mode = False

def get_athens_now(): return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.return_mode = False
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1
    st.rerun()

def speak_text(txt, beep=True):
    b_js = "var c=new (window.AudioContext||window.webkitAudioContext)();var o=c.createOscillator();o.type='sawtooth';o.frequency.setValueAtTime(150,c.currentTime);o.connect(c.destination);o.start();o.stop(c.currentTime+0.2);" if beep else ""
    s_js = f"var m=new SpeechSynthesisUtterance('{txt}');m.lang='el-GR';window.speechSynthesis.speak(m);" if txt else ""
    st.components.v1.html(f"<script>{b_js}{s_js}</script>", height=0)

def finalize(disc_val, method):
    if not supabase: return
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    try:
        for i in st.session_state.cart:
            d, f = round(i['price'] * ratio, 2), round(i['price'] - (i['price'] * ratio), 2)
            supabase.table("sales").insert({"barcode":str(i['bc']),"item_name":str(i['name']),"unit_price":float(i['price']),"discount":float(d),"final_item_price":float(f),"method":str(method),"s_date":ts,"cust_id":c_id}).execute()
            if i['bc'] != 'VOICE':
                res = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
                if res.data:
                    ch = 1 if i['price'] < 0 else -1
                    supabase.table("inventory").update({"stock": int(res.data[0]['stock']) + ch}).eq("barcode", i['bc']).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); st.balloons(); time.sleep(1.5); reset_app()
    except Exception as e: st.error(f"Error: {e}")

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.write(f"### Σύνολο: {total:.2f}€")
    opt = st.radio("Έκπτωση;", ["ΟΧΙ", "ΝΑΙ"], horizontal=True)
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή %")
        if inp:
            try: disc = round((float(inp.replace("%",""))/100 * total), 2) if "%" in inp else round(float(inp), 2)
            except: pass
    st.warning(f"## ΠΛΗΡΩΤΕΟ: {total-disc:.2f}€")
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

@st.dialog("⭐ Loyalty")
def show_customer_history(c_id, c_name):
    res = supabase.table("sales").select("*").eq("cust_id", c_id).order("s_date", desc=True).execute()
    if res.data:
        df = pd.DataFrame(res.data)
        st.metric("Σύνολο Αγορών", f"{df['final_item_price'].sum():.2f}€")
        st.dataframe(df[['s_date', 'item_name', 'final_item_price', 'method']], hide_index=True)

if not st.session_state.logged_in:
    st.title("🔒 CHERRY LOGIN")
    if st.text_input("Password", type="password") == "CHERRY123":
        if st.button("Είσοδος"): st.session_state.logged_in = True; st.rerun()
else:
    with st.sidebar:
        st.write(get_athens_now().strftime('%d/%m/%Y %H:%M:%S'))
        if HAS_MIC:
            t = speech_to_text(language='el', key=f"v_{st.session_state.mic_key}")
            if t:
                nums = re.findall(r"\d+\.?\d*", t)
                if nums:
                    p = float(nums[0])
                    st.session_state.cart.append({'bc':'VOICE','name':t.upper(),'price':-p if st.session_state.return_mode else p})
                    st.session_state.mic_key+=1; st.rerun()
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        if st.button("❌ Έξοδος"): st.session_state.logged_in = False; st.rerun()

    if view in ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ"]:
        st.subheader(f"👤 {st.session_state.cust_name}")
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"p_{st.session_state.ph_key}")
                if ph and len(ph)==10:
                    r = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if r.data: st.session_state.selected_cust_id, st.session_state.cust_name = r.data[0]['id'], r.data[0]['name']; st.rerun()
                if st.button("🛒 ΛΙΑΝΙΚΗ"): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                bc = st.text_input("Barcode", key=f"b_{st.session_state.bc_key}")
                if bc:
                    r = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if r.data:
                        v = -float(r.data[0]['price']) if st.session_state.return_mode else float(r.data[0]['price'])
                        st.session_state.cart.append({'bc':bc, 'name':r.data[0]['name'], 'price':v})
                        st.session_state.bc_key += 1; st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ"): payment_popup()
                if st.button("🔄 ΑΚΥΡΩΣΗ"): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            st.markdown(f"<div class='cart-area'>" + "\n".join([f"{i['name'][:15]}.. | {i['price']:.2f}€" for i in st.session_state.cart]) + "</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif view == "📊 MANAGER":
        res = supabase.table("sales").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['s_date_dt'] = pd.to_datetime(df['s_date'])
            df['date'] = df['s_date_dt'].dt.date
            t1, t2, t3 = st.tabs(["📅 ΣΗΜΕΡΑ", "📆 ΠΕΡΙΟΔΟΣ", "📈 INSIGHTS"])
            with t1:
                tdf = df[df['date'] == get_athens_now().date()]
                st.markdown(f"<div class='report-stat'>ΤΖΙΡΟΣ: {tdf['final_item_price'].sum():.2f}€</div>", unsafe_allow_html=True)
                st.dataframe(tdf[['s_date','item_name','final_item_price','method']], use_container_width=True)
            with t2:
                sd, ed = st.date_input("Από", get_athens_now().date()-timedelta(7)), st.date_input("Έως", get_athens_now().date())
                pdf = df[(df['date'] >= sd) & (df['date'] <= ed)]
                st.write(f"### Σύνολο Περιόδου: {pdf['final_item_price'].sum():.2f}€")
                for d in sorted(pdf['date'].unique(), reverse=True):
                    ddf = pdf[pdf['date'] == d]
                    st.markdown(f"<div class='day-header'>📅 {d} | Τζίρος: {ddf['final_item_price'].sum():.2f}€</div>", unsafe_allow_html=True)
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Μετρητά", f"{ddf[ddf['method']=='Μετρητά']['final_item_price'].sum():.2f}€")
                    c2.metric("Κάρτα", f"{ddf[ddf['method']=='Κάρτα']['final_item_price'].sum():.2f}€")
                    c3.metric("Εκπτώσεις", f"{ddf['discount'].sum():.2f}€")
            with t3:
                st.plotly_chart(px.pie(df, values='final_item_price', names='method', title='Μέθοδος Πληρωμής'))
                df['hour'] = df['s_date_dt'].dt.hour
                st.plotly_chart(px.line(df.groupby('hour')['final_item_price'].sum().reset_index(), x='hour', y='final_item_price', title='Τζίρος ανά Ώρα'))

    elif view == "📦 ΑΠΟΘΗΚΗ":
        res = supabase.table("inventory").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data), use_container_width=True)

    elif view == "👥 ΠΕΛΑΤΕΣ":
        res_c = supabase.table("customers").select("*").execute()
        if res_c.data:
            for r in res_c.data:
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"<div class='data-row'>👤 {r['name']} | {r['phone']}</div>", unsafe_allow_html=True)
                if c2.button("⭐", key=f"s_{r['id']}"): show_customer_history(r['id'], r['name'])
