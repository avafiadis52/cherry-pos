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

# --- 3. CONFIG & STYLE (Version v14.0.83) ---
st.set_page_config(page_title="CHERRY v14.0.83", layout="wide", page_icon="🍒")

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
if 'mic_key' not in st.session_state: st.session_state.mic_key = 21000

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
    
    speech_js = f"""
    var msg = new SpeechSynthesisUtterance('{text_to_say}');
    msg.lang = 'el-GR';
    window.speechSynthesis.speak(msg);
    """ if text_to_say else ""

    js = f"<script>{beep_js}{speech_js}</script>"
    st.components.v1.html(js, height=0)

def play_sound(url):
    st.components.v1.html(f'<audio autoplay style="display:none"><source src="{url}" type="audio/mpeg"></audio>', height=0)

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
        
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ")
        st.balloons()
        speak_text("Επιτυχής Πληρωμή", play_beep=False)
        play_sound("https://www.soundjay.com/misc/sounds/magic-chime-01.mp3")
        
        time.sleep(1.5)
        reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    
    st.write("Θέλετε έκπτωση;")
    opt = st.radio("Επιλογή", ["ΟΧΙ", "ΝΑΙ"], horizontal=True, label_visibility="collapsed")
    disc = 0.0
    if opt == "ΝΑΙ":
        st.write("Δώστε ποσό ή ποσοστό %")
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
    if c1.button("💵 Μετρητά", key="btn_cash", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", key="btn_card", use_container_width=True): finalize(disc, "Κάρτα")

# --- 5. MAIN UI ---
if st.session_state.is_logged_out:
    st.markdown("<h1 style='text-align:center;color:#e74c3c;'>Αποσυνδεθήκατε</h1>", unsafe_allow_html=True)
    if st.button("Επανασύνδεση"): st.session_state.is_logged_out = False; st.rerun()
else:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-date'>{get_athens_now().strftime('%d/%m/%Y %H:%M:%S')}</div>", unsafe_allow_html=True)
        
        st.subheader("🎙️ Φωνητική Εντολή")
        if HAS_MIC:
            text = speech_to_text(language='el', start_prompt="🔴 ΠΑΤΑ ΚΑΙ ΜΙΛΑ", stop_prompt="🟢 ΕΠΕΞΕΡΓΑΣΙΑ...", just_once=True, key=f"voice_{st.session_state.mic_key}")
            if text:
                raw_query = text.lower().strip()
                numbers = re.findall(r"[-+]?\d*\.\d+|\d+", raw_query)
                num_map = {"ένα":1, "δυο":2, "δύο":2, "τρία":3, "τέσσερα":4, "πέντε":5, "δέκα":10, "έντεκα":11, "είκοσι":20, "τριάντα":30, "σαράντα":40, "πενήντα":50, "εξήντα":60, "εβδομήντα":70, "ογδόντα":80, "ενενήντα":90, "εκατό":100}
                found_price = float(numbers[0]) if numbers else next((float(v) for k, v in num_map.items() if k in raw_query), None)
                
                if found_price:
                    clean_name = raw_query
                    if numbers: clean_name = clean_name.replace(numbers[0], "")
                    for w in ["ευρώ", "ευρω", "τιμή", "τιμη"] + list(num_map.keys()): clean_name = clean_name.replace(w, "")
                    final_name = clean_name.strip().upper() if clean_name.strip() else "ΦΩΝΗΤΙΚΗ ΠΩΛΗΣΗ"
                    st.session_state.cart.append({'bc': 'VOICE', 'name': final_name, 'price': found_price})
                    st.session_state.mic_key += 1
                    time.sleep(0.4); st.rerun()
                else:
                    speak_text("Δεν κατάλαβα", play_beep=True)
                    st.warning("Σφάλμα: Δεν βρέθηκε τιμή.")

        st.divider()
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])
        if st.button("❌ Έξοδος", use_container_width=True):
            st.session_state.cart = []; st.session_state.is_logged_out = True; st.rerun()

    if view == "🛒 ΤΑΜΕΙΟ":
        st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"ph_{st.session_state.ph_key}")
                if ph and len(ph) == 10 and supabase:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data: 
                        st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']
                        st.rerun()
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name} (Αλλαγή)", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc and supabase:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        st.session_state.cart.append({'bc': res.data[0]['barcode'], 'name': res.data[0]['name'].upper(), 'price': float(res.data[0]['price'])})
                        st.session_state.bc_key += 1; st.rerun()
                    else:
                        speak_text("", play_beep=True)
                        st.error(f"Το Barcode {bc} δεν βρέθηκε!")
                for idx, item in enumerate(st.session_state.cart):
                    if st.button(f"❌ {item['name']} {item['price']}€", key=f"del_{idx}", use_container_width=True):
                        st.session_state.cart.pop(idx); st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
            if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            lines = [f"{i['name'][:20]:<20} | {i['price']:>6.2f}€" for i in st.session_state.cart]
            st.markdown(f"<div class='cart-area'>{'Είδος':<20} | {'Τιμή':>6}\n{'-'*30}\n{chr(10).join(lines)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif view == "📊 MANAGER" and supabase:
        st.title("📊 Αναφορές")
        res = supabase.table("sales").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['s_date_dt'] = pd.to_datetime(df['s_date'])
            df['ΗΜΕΡΟΜΗΝΙΑ'] = df['s_date_dt'].dt.date
            today_date = get_athens_now().date()
            t1, t2 = st.tabs(["📅 ΣΗΜΕΡΑ", "📆 ΑΝΑΦΟΡΑ ΠΕΡΙΟΔΟΥ"])
            
            with t1:
                today_df = df[df['ΗΜΕΡΟΜΗΝΙΑ'] == today_date].sort_values('s_date_dt')
                if not today_df.empty:
                    m_today = today_df[today_df['method'] == 'Μετρητά']
                    c_today = today_df[today_df['method'] == 'Κάρτα']
                    
                    st.markdown(f"<div class='report-stat' style='border: 2px solid #2ecc71;'><div style='color:#2ecc71; font-weight:bold;'>ΣΥΝΟΛΙΚΟΣ ΤΖΙΡΟΣ ΗΜΕΡΑΣ</div><div class='stat-val' style='font-size:40px;'>{today_df['final_item_price'].sum():.2f}€</div></div>", unsafe_allow_html=True)
                    
                    col1, col2, col3 = st.columns(3)
                    col1.markdown(f"<div class='report-stat'>💵 Μετρητά<div class='stat-val'>{m_today['final_item_price'].sum():.2f}€</div><div class='stat-desc'>({m_today['s_date'].nunique()} πράξεις)</div></div>", unsafe_allow_html=True)
                    col2.markdown(f"<div class='report-stat'>💳 Κάρτα<div class='stat-val'>{c_today['final_item_price'].sum():.2f}€</div><div class='stat-desc'>({c_today['s_date'].nunique()} πράξεις)</div></div>", unsafe_allow_html=True)
                    col3.markdown(f"<div class='report-stat'>📉 Εκπτώσεις<div class='stat-val' style='color:#e74c3c;'>{today_df['discount'].sum():.2f}€</div><div class='stat-desc'>Σύνολο ημέρας</div></div>", unsafe_allow_html=True)
                    
                    today_df['ΠΡΑΞΗ'] = today_df.groupby('s_date').ngroup() + 1
                    st.dataframe(today_df[['ΠΡΑΞΗ', 's_date', 'item_name', 'unit_price', 'discount', 'final_item_price', 'method']].sort_values('s_date', ascending=False), use_container_width=True, hide_index=True)
            
            with t2:
                col_s, col_e = st.columns(2)
                sd, ed = col_s.date_input("Από", today_date-timedelta(days=7)), col_e.date_input("Έως", today_date)
                pdf = df[(df['ΗΜΕΡΟΜΗΝΙΑ'] >= sd) & (df['ΗΜΕΡΟΜΗΝΙΑ'] <= ed)].sort_values('s_date_dt')
                if not pdf.empty:
                    pdf['ΠΡΑΞΗ'] = pdf.groupby('s_date').ngroup() + 1
                    st.dataframe(pdf[['ΠΡΑΞΗ', 's_date', 'item_name', 'unit_price', 'discount', 'final_item_price', 'method']].sort_values('s_date', ascending=False), use_container_width=True, hide_index=True)

    elif view == "📦 ΑΠΟΘΗΚΗ" and supabase:
        with st.form("inv_f", clear_on_submit=True):
            c1,c2,c3,c4 = st.columns(4); b,n,p,s = c1.text_input("BC"), c2.text_input("Όνομα"), c3.number_input("Τιμή"), c4.number_input("Stock")
            if st.form_submit_button("Προσθήκη") and b and n: supabase.table("inventory").upsert({"barcode":b,"name":n,"price":p,"stock":s}).execute(); st.rerun()
        for r in supabase.table("inventory").select("*").execute().data:
            st.markdown(f"<div class='data-row'>{r['barcode']} | {r['name']} | {r['price']}€ | Stock: {r['stock']}</div>", unsafe_allow_html=True)
            if st.button("❌", key=f"inv_{r['barcode']}"): supabase.table("inventory").delete().eq("barcode", r['barcode']).execute(); st.rerun()

    elif view == "👥 ΠΕΛΑΤΕΣ" and supabase:
        for r in supabase.table("customers").select("*").execute().data:
            st.markdown(f"<div class='data-row'>👤 {r['name']} | 📞 {r['phone']}</div>", unsafe_allow_html=True)
            if st.button("❌", key=f"c_{r['id']}"): supabase.table("customers").delete().eq("id", r['id']).execute(); st.rerun()
