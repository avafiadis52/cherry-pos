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

# --- 3. CONFIG & STYLE (Version v14.0.91) ---
st.set_page_config(page_title="CHERRY v14.0.91", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; }
    .cart-area { font-family: 'Courier New', monospace; background-color: #2b2b2b; padding: 15px; border-radius: 5px; white-space: pre-wrap; border: 1px solid #3b3b3b; min-height: 200px; font-size: 14px; }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; padding: 10px; border-radius: 10px; background-color: #fff3f0; border: 2px solid #e44d26; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; font-weight: bold !important; }
    .data-row { background-color: #262626; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    .report-stat { background-color: #262730; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; }
    .stat-desc { font-size: 13px; color: #888; }
    .day-header { background-color: #34495e; color: #f1c40f; padding: 8px; border-radius: 5px; margin-top: 20px; margin-bottom: 10px; font-weight: bold; border-left: 10px solid #f1c40f; }
    table { color: white !important; }
    thead tr th { color: white !important; background-color: #333 !important; }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'is_logged_out' not in st.session_state: st.session_state.is_logged_out = False
if 'mic_key' not in st.session_state: st.session_state.mic_key = 29000

# --- 4. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1
    st.rerun()

def speak_text(text_to_say, play_beep=True):
    beep_js = """
    var context = new (window.AudioContext || window.webkitAudioContext)();
    var osc = context.createOscillator();
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(150, context.currentTime);
    osc.connect(context.destination);
    osc.start();
    osc.stop(context.currentTime + 0.2);
    """ if play_beep else ""
    speech_js = f"var msg = new SpeechSynthesisUtterance('{text_to_say}'); msg.lang = 'el-GR'; window.speechSynthesis.speak(msg);" if text_to_say else ""
    st.components.v1.html(f"<script>{beep_js}{speech_js}</script>", height=0)

@st.dialog("👤 Νέος Πελάτης")
def new_customer_popup(phone):
    st.write(f"Το τηλέφωνο **{phone}** δεν υπάρχει.")
    name = st.text_input("Ονοματεπώνυμο Πελάτη")
    if st.button("Καταχώρηση & Συνέχεια", use_container_width=True):
        if name:
            try:
                res = supabase.table("customers").insert({"name": name.upper(), "phone": phone}).execute()
                if res.data:
                    st.session_state.selected_cust_id = res.data[0]['id']
                    st.session_state.cust_name = res.data[0]['name']
                    st.success("Ο πελάτης καταχωρήθηκε!")
                    time.sleep(1)
                    st.rerun()
            except Exception as e: st.error(f"Σφάλμα: {e}")
        else: st.warning("Παρακαλώ δώστε όνομα.")

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    st.write("Θέλετε έκπτωση;")
    opt = st.radio("Επιλογή", ["ΟΧΙ", "ΝΑΙ"], horizontal=True, label_visibility="collapsed")
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή ποσοστό %", label_visibility="collapsed", placeholder="π.χ. 5 ή 10%")
        if inp:
            try:
                if "%" in inp: disc = round((float(inp.replace("%",""))/100 * total), 2)
                else: disc = round(float(inp), 2)
            except: st.error("Λάθος μορφή")
    final_p = round(total - disc, 2)
    st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {final_p:.2f}€</div>", unsafe_allow_html=True)
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

def finalize(disc_val, method):
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    try:
        for i in st.session_state.cart:
            d = round(i['price'] * ratio, 2)
            f = round(i['price'] - d, 2)
            supabase.table("sales").insert({"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": float(d), "final_item_price": float(f), "method": str(method), "s_date": ts, "cust_id": c_id}).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); st.balloons(); speak_text("Επιτυχής Πληρωμή", False)
        time.sleep(1.5); reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

# --- 5. MAIN UI ---
if st.session_state.is_logged_out:
    st.markdown("<h1 style='text-align:center;color:#e74c3c;'>Αποσυνδεθήκατε</h1>", unsafe_allow_html=True)
    if st.button("Επανασύνδεση"): st.session_state.is_logged_out = False; st.rerun()
else:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-date'>{get_athens_now().strftime('%d/%m/%Y %H:%M:%S')}</div>", unsafe_allow_html=True)
        if HAS_MIC:
            text = speech_to_text(language='el', start_prompt="🔴 ΦΩΝΗΤΙΚΗ ΕΝΤΟΛΗ", stop_prompt="🟢 ΕΠΕΞΕΡΓΑΣΙΑ...", just_once=True, key=f"voice_{st.session_state.mic_key}")
            if text:
                raw = text.lower().strip(); nums = re.findall(r"[-+]?\d*\.\d+|\d+", raw)
                num_map = {"ένα":1, "δυο":2, "τρία":3, "τέσσερα":4, "πέντε":5, "δέκα":10, "είκοσι":20, "πενήντα":50, "εκατό":100}
                f_p = float(nums[0]) if nums else next((float(v) for k, v in num_map.items() if k in raw), None)
                if f_p:
                    c_n = raw
                    if nums: c_n = c_n.replace(nums[0], "")
                    for w in ["ευρώ", "τιμή"] + list(num_map.keys()): c_n = c_n.replace(w, "")
                    st.session_state.cart.append({'bc': 'VOICE', 'name': c_n.strip().upper() or "ΦΩΝΗΤΙΚΗ ΠΩΛΗΣΗ", 'price': f_p})
                    st.session_state.mic_key += 1; time.sleep(0.4); st.rerun()
                else: speak_text("Δεν κατάλαβα"); st.warning("Σφάλμα: Δεν βρέθηκε το είδος")
        st.divider()
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])
        if st.button("❌ Έξοδος", use_container_width=True): st.session_state.cart = []; st.session_state.is_logged_out = True; st.rerun()

    if view == "🛒 ΤΑΜΕΙΟ":
        st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο (10 ψηφία)", key=f"ph_{st.session_state.ph_key}", help="Πληκτρολογήστε 10 ψηφία για αυτόματη αναζήτηση")
                # Έλεγχος για ακριβώς 10 ψηφία και μόνο νούμερα
                if ph:
                    clean_ph = ''.join(filter(str.isdigit, ph))
                    if len(clean_ph) == 10:
                        res = supabase.table("customers").select("*").eq("phone", clean_ph).execute()
                        if res.data:
                            st.session_state.selected_cust_id = res.data[0]['id']
                            st.session_state.cust_name = res.data[0]['name']
                            st.rerun()
                        else:
                            new_customer_popup(clean_ph)
                    elif len(clean_ph) > 10:
                        st.error("Το τηλέφωνο δεν μπορεί να έχει πάνω από 10 ψηφία.")
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name} (Αλλαγή)", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        st.session_state.cart.append({'bc': res.data[0]['barcode'], 'name': res.data[0]['name'].upper(), 'price': float(res.data[0]['price'])})
                        st.session_state.bc_key += 1; st.rerun()
                    else: st.error(f"Barcode {bc} όχι!")
                for idx, item in enumerate(st.session_state.cart):
                    if st.button(f"❌ {item['name']} {item['price']}€", key=f"del_{idx}", use_container_width=True): st.session_state.cart.pop(idx); st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
            if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            lines = [f"{i['name'][:20]:<20} | {i['price']:>6.2f}€" for i in st.session_state.cart]
            st.markdown(f"<div class='cart-area'>{'Είδος':<20} | {'Τιμή':>6}\n{'-'*30}\n{chr(10).join(lines)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif view == "📊 MANAGER":
        res = supabase.table("sales").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data); df['s_date_dt'] = pd.to_datetime(df['s_date']); df['ΗΜΕΡΟΜΗΝΙΑ'] = df['s_date_dt'].dt.date
            today = get_athens_now().date()
            t1, t2 = st.tabs(["📅 ΣΗΜΕΡΑ", "📆 ΠΕΡΙΟΔΟΣ"])
            with t1:
                tdf = df[df['ΗΜΕΡΟΜΗΝΙΑ'] == today].sort_values('s_date_dt')
                if not tdf.empty:
                    st.markdown(f"<div class='report-stat'>ΤΖΙΡΟΣ ΗΜΕΡΑΣ: {tdf['final_item_price'].sum():.2f}€</div>", unsafe_allow_html=True)
                    tdf['ΠΡΑΞΗ'] = tdf.groupby('s_date').ngroup() + 1
                    st.dataframe(tdf[['ΠΡΑΞΗ', 's_date', 'item_name', 'final_item_price', 'method']].sort_values('s_date', ascending=False), use_container_width=True, hide_index=True)
            with t2:
                cs, ce = st.columns(2); sd, ed = cs.date_input("Από", today-timedelta(days=7)), ce.date_input("Έως", today)
                pdf = df[(df['ΗΜΕΡΟΜΗΝΙΑ'] >= sd) & (df['ΗΜΕΡΟΜΗΝΙΑ'] <= ed)].sort_values('s_date_dt', ascending=False)
                if not pdf.empty:
                    st.markdown(f"<div class='report-stat'>ΤΖΙΡΟΣ ΠΕΡΙΟΔΟΥ: {pdf['final_item_price'].sum():.2f}€</div>", unsafe_allow_html=True)
                    for d in sorted(pdf['ΗΜΕΡΟΜΗΝΙΑ'].unique(), reverse=True):
                        ddf = pdf[pdf['ΗΜΕΡΟΜΗΝΙΑ'] == d].copy(); st.markdown(f"<div class='day-header'>📅 {d.strftime('%d/%m/%Y')}</div>", unsafe_allow_html=True)
                        ddf['ΠΡΑΞΗ'] = ddf.groupby('s_date').ngroup() + 1
                        st.dataframe(ddf[['ΠΡΑΞΗ', 's_date', 'item_name', 'final_item_price', 'method']].sort_values('s_date', ascending=False), use_container_width=True, hide_index=True)

    elif view == "📦 ΑΠΟΘΗΚΗ":
        with st.form("inv_f", clear_on_submit=True):
            c1,c2,c3,c4 = st.columns(4); b,n,p,s = c1.text_input("BC"), c2.text_input("Όνομα"), c3.number_input("Τιμή"), c4.number_input("Stock")
            if st.form_submit_button("Προσθήκη") and b and n: supabase.table("inventory").upsert({"barcode":b,"name":n,"price":p,"stock":s}).execute(); st.rerun()
        for r in supabase.table("inventory").select("*").execute().data:
            st.markdown(f"<div class='data-row'>{r['barcode']} | {r['name']} | {r['price']}€</div>", unsafe_allow_html=True)
            if st.button("❌", key=f"inv_{r['barcode']}"): supabase.table("inventory").delete().eq("barcode", r['barcode']).execute(); st.rerun()

    elif view == "👥 ΠΕΛΑΤΕΣ":
        for r in supabase.table("customers").select("*").execute().data:
            st.markdown(f"<div class='data-row'>👤 {r['name']} | 📞 {r['phone']}</div>", unsafe_allow_html=True)
            if st.button("❌", key=f"c_{r['id']}"): supabase.table("customers").delete().eq("id", r['id']).execute(); st.rerun()
