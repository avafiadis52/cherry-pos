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

# --- 3. CONFIG & STYLE (Version v14.2.69) ---
st.set_page_config(page_title="CHERRY v14.2.69", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; }
    
    .cart-area { 
        font-family: 'Courier New', monospace; 
        background-color: #000000; padding: 15px; border-radius: 10px; 
        white-space: pre-wrap; border: 4px solid #2ecc71 !important; 
        box-shadow: 0 0 15px rgba(46, 204, 113, 0.4); min-height: 300px; 
        font-size: 16px; color: #2ecc71; 
    }

    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; margin-top: 10px; }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; padding: 10px; background-color: #fff3f0; border: 2px solid #e44d26; border-radius: 10px; }
    
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; font-weight: bold !important; }
    
    .data-row { font-family: 'Courier New', monospace; background-color: #262626; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; display: block; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; border-bottom: 1px solid #444; padding-bottom: 10px; }
    .report-stat { background-color: #262730; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; }
    .day-header { background-color: #34495e; color: #f1c40f; padding: 10px; border-radius: 5px; margin-top: 25px; font-weight: bold; border-left: 8px solid #f1c40f; }
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

def switch_to_normal():
    st.session_state.return_mode = False
    if 'sidebar_nav' in st.session_state:
        st.session_state.sidebar_nav = "🛒 ΤΑΜΕΙΟ"

def speak_text(text_to_say, play_beep=True):
    beep_js = "var context = new (window.AudioContext || window.webkitAudioContext)(); var osc = context.createOscillator(); osc.type = 'sawtooth'; osc.frequency.setValueAtTime(150, context.currentTime); osc.connect(context.destination); osc.start(); osc.stop(context.currentTime + 0.2);" if play_beep else ""
    speech_js = "var msg = new SpeechSynthesisUtterance('{}'); msg.lang = 'el-GR'; window.speechSynthesis.speak(msg);".format(text_to_say) if text_to_say else ""
    st.components.v1.html("<script>{}{}</script>".format(beep_js, speech_js), height=0)

def play_sound(url):
    st.components.v1.html('<audio autoplay style="display:none"><source src="{}" type="audio/mpeg"></audio>'.format(url), height=0)

@st.dialog("👤 Νέος Πελάτης")
def new_customer_popup(phone):
    st.write(f"Το τηλέφωνο **{phone}** δεν υπάρχει.")
    name = st.text_input("Ονοματεπώνυμο Πελάτη")
    if st.button("Καταχώρηση", use_container_width=True):
        if name:
            try:
                res = supabase.table("customers").insert({"name": name.upper(), "phone": phone}).execute()
                if res.data:
                    st.session_state.selected_cust_id = res.data[0]['id']
                    st.session_state.cust_name = res.data[0]['name']
                    st.success("Έτοιμο!"); time.sleep(1); st.rerun()
            except Exception as e: st.error(f"Σφάλμα: {e}")

@st.dialog("⚠️ Διαγραφή")
def confirm_delete_customer(c_id, c_name):
    st.warning(f"Διαγραφή του {c_name};")
    if st.button("ΝΑΙ, Διαγραφή", use_container_width=True, type="primary"):
        try:
            supabase.table("customers").delete().eq("id", c_id).execute()
            st.success("Διαγράφηκε."); time.sleep(1); st.rerun()
        except Exception as e: st.error(f"Σφάλμα: {e}")

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
                    new_stock = int(res_inv.data[0]['stock']) + change
                    supabase.table("inventory").update({"stock": new_stock}).eq("barcode", i['bc']).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); st.balloons()
        speak_text("Επιτυχής Πληρωμή", play_beep=False)
        play_sound("https://www.soundjay.com/misc/sounds/magic-chime-01.mp3")
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
                if "%" in inp: disc = round((float(inp.replace("%",""))/100 * total), 2)
                else: disc = round(float(inp), 2)
            except: st.error("Σφάλμα")
    st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {total-disc:.2f}€</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

@st.dialog("⭐ Ιστορικό")
def show_customer_history(c_id, c_name):
    st.subheader(f"Καρτέλα: {c_name}")
    res = supabase.table("sales").select("*").eq("cust_id", c_id).order("s_date", desc=True).execute()
    if res.data:
        pdf = pd.DataFrame(res.data)
        st.metric("Σύνολο Αγορών", f"{pdf['final_item_price'].sum():.2f}€")
        st.dataframe(pdf[['s_date', 'item_name', 'final_item_price']], use_container_width=True)

# --- 5. MAIN UI ---
if st.session_state.get('is_logged_out', False):
    st.markdown("<h1 style='text-align:center;'>Αποσυνδεθήκατε</h1>", unsafe_allow_html=True)
    if st.button("Είσοδος"): st.session_state.is_logged_out = False; st.rerun()
else:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-date'>{get_athens_now().strftime('%d/%m/%Y %H:%M')}</div>", unsafe_allow_html=True)
        if HAS_MIC:
            t = speech_to_text(language='el', start_prompt="🔴 VOICE", key=f"v_{st.session_state.mic_key}")
            if t:
                nums = re.findall(r"[-+]?\d*\.\d+|\d+", t)
                if nums:
                    p = float(nums[0])
                    val = -p if st.session_state.return_mode else p
                    st.session_state.cart.append({'bc':'VOICE','name':t.upper(),'price':val})
                    st.session_state.mic_key += 1; time.sleep(0.3); st.rerun()
        st.divider()
        m = ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"]
        view = st.radio("Μενού", m, key="sidebar_nav")
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        curr = view if view != "🔄 ΕΠΙΣΤΡΟΦΗ" else "🛒 ΤΑΜΕΙΟ"

    if curr == "🛒 ΤΑΜΕΙΟ":
        if st.session_state.return_mode: st.error("🔄 ΛΕΙΤΟΥΡΓΙΑ ΕΠΙΣΤΡΟΦΗΣ")
        else: st.markdown(f"<div class='status-header'>{st.session_state.cust_name}</div>", unsafe_allow_html=True)
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"p_{st.session_state.ph_key}")
                if ph and len(ph)==10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                    else: new_customer_popup(ph)
                if st.button("🛒 ΛΙΑΝΙΚΗ"): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name}", on_click=lambda: st.session_state.update({"selected_cust_id":None,"cust_name":"Λιανική Πώληση"}))
                bc = st.text_input("Barcode", key=f"b_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        v = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'bc':bc, 'name':res.data[0]['name'].upper(), 'price':v})
                        st.session_state.bc_key += 1; st.rerun()
                for idx, i in enumerate(st.session_state.cart):
                    if st.button(f"❌ {i['name']} {i['price']}€", key=f"d_{idx}"): st.session_state.cart.pop(idx); st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
            if st.button("🔄 RESET"): reset_app()
        with cr:
            tot = sum(i['price'] for i in st.session_state.cart)
            lines = [f"{i['name'][:15]:15} | {i['price']:>6.2f}€" for i in st.session_state.cart]
            st.markdown(f"<div class='cart-area'>{'Είδος':15} | {'Τιμή':>7}\n{'-'*25}\n" + "\n".join(lines) + "</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{tot:.2f}€</div>", unsafe_allow_html=True)

    elif curr == "📊 MANAGER":
        st.title("📊 Αναφορές")
        res_s = supabase.table("sales").select("*").execute()
        if res_s.data:
            df = pd.DataFrame(res_s.data)
            df['date'] = pd.to_datetime(df['s_date']).dt.date
            today = get_athens_now().date()
            tdf = df[df['date'] == today]
            st.subheader("Σήμερα")
            c1, c2, c3 = st.columns(3)
            c1.metric("Τζίρος", f"{tdf['final_item_price'].sum():.2f}€")
            c2.metric("Μετρητά", f"{tdf[tdf['method']=='Μετρητά']['final_item_price'].sum():.2f}€")
            c3.metric("Κάρτα", f"{tdf[tdf['method']=='Κάρτα']['final_item_price'].sum():.2f}€")
            st.dataframe(tdf[['item_name', 'final_item_price', 'method']].sort_index(ascending=False), use_container_width=True)

    elif curr == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Αποθήκη")
        c1,c2,c3,c4 = st.columns(4)
        b, n = c1.text_input("BC"), c2.text_input("Όνομα")
        p, s = c3.number_input("Τιμή", 0.0), c4.number_input("Stock", 0)
        if st.button("Προσθήκη"):
            supabase.table("inventory").upsert({"barcode":b, "name":n.upper(), "price":p, "stock":s}).execute()
            st.rerun()
        res = supabase.table("inventory").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data)[['barcode','name','price','stock']], use_container_width=True)

    elif curr == "👥 ΠΕΛΑΤΕΣ":
        st.title("👥 Πελάτες")
        res_c = supabase.table("customers").select("*").execute()
        if res_c.data:
            for r in res_c.data:
                col1, col2, col3 = st.columns([4,1,1])
                col1.write(f"👤 {r['name']} | 📞 {r['phone']}")
                if col2.button("⭐", key=f"h_{r['id']}"): show_customer_history(r['id'], r['name'])
                if col3.button("❌", key=f"del_{r['id']}"): confirm_delete_customer(r['id'], r['name'])
