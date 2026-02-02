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

# --- 3. CONFIG & STYLE (Version v14.2.35) ---
st.set_page_config(page_title="CHERRY v14.2.35", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; }
    
    .cart-area { 
        font-family: 'Courier New', monospace; 
        background-color: #000000; 
        padding: 15px; 
        border-radius: 10px; 
        white-space: pre-wrap; 
        border: 4px solid #2ecc71 !important; 
        box-shadow: 0 0 15px rgba(46, 204, 113, 0.4); 
        min-height: 300px; 
        font-size: 16px;
        color: #2ecc71; 
    }

    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; margin-top: 10px; text-shadow: 2px 2px 10px rgba(46, 204, 113, 0.5); }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; padding: 10px; border-radius: 10px; background-color: #fff3f0; border: 2px solid #e44d26; }
    
    div.stButton > button { 
        background-color: #d3d3d3 !important; 
        color: #000000 !important; 
        border-radius: 8px !important; 
        font-weight: bold !important; 
        border: 1px solid #808080 !important;
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
    .report-stat { background-color: #262730; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; }
    .stat-desc { font-size: 13px; color: #888; }
    .day-header { background-color: #34495e; color: #f1c40f; padding: 5px 10px; border-radius: 5px; margin-top: 20px; margin-bottom: 10px; font-weight: bold; border-left: 5px solid #f1c40f; }
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

def play_sound(url):
    st.components.v1.html(f'<audio autoplay style="display:none"><source src="{url}" type="audio/mpeg"></audio>', height=0)

@st.dialog("👤 Νέος Πελάτης")
def new_customer_popup(phone):
    st.write(f"Το τηλέφωνο **{phone}** δεν υπάρχει στη βάση.")
    name = st.text_input("Ονοματεπώνυμο Πελάτη")
    if st.button("Καταχώρηση & Συνέχεια", use_container_width=True):
        if name:
            try:
                res = supabase.table("customers").insert({"name": name.upper(), "phone": phone}).execute()
                if res.data:
                    st.session_state.selected_cust_id = res.data[0]['id']
                    st.session_state.cust_name = res.data[0]['name']
                    st.success("Ο πελάτης καταχωρήθηκε!")
                    time.sleep(1); st.rerun()
            except Exception as e: st.error(f"Σφάλμα: {e}")
        else: st.warning("Παρακαλώ δώστε όνομα.")

@st.dialog("📝 Επεξεργασία Πελάτη")
def edit_customer_popup(customer):
    new_name = st.text_input("Όνομα", value=customer['name'])
    new_phone = st.text_input("Τηλέφωνο", value=customer['phone'])
    if st.button("Αποθήκευση Αλλαγών", use_container_width=True):
        try:
            supabase.table("customers").update({"name": new_name.upper(), "phone": new_phone}).eq("id", customer['id']).execute()
            st.success("Οι αλλαγές αποθηκεύτηκαν!")
            time.sleep(1); st.rerun()
        except Exception as e: st.error(f"Σφάλμα: {e}")

@st.dialog("📜 Ιστορικό & Πόντοι")
def customer_history_popup(customer):
    st.subheader(f"Καρτέλα: {customer['name']}")
    try:
        res = supabase.table("sales").select("*").eq("cust_id", customer['id']).order("s_date", desc=True).execute()
        if res.data:
            h_df = pd.DataFrame(res.data)
            h_df['ΗΜΕΡΟΜΗΝΙΑ'] = pd.to_datetime(h_df['s_date']).dt.strftime('%d/%m/%y %H:%M')
            total_spent = h_df['final_item_price'].sum()
            points = int(total_spent // 10)
            st.markdown(f"### ⭐ Πόντοι Loyalty: {points}")
            st.markdown(f"**Συνολικές Αγορές: {total_spent:.2f}€**")
            st.divider()
            st.dataframe(h_df[['ΗΜΕΡΟΜΗΝΙΑ', 'item_name', 'final_item_price', 'method']], 
                         column_config={
                             "item_name": "Είδος",
                             "final_item_price": st.column_config.NumberColumn("Τιμή €", format="%.2f"),
                             "method": "Πληρωμή"
                         }, use_container_width=True, hide_index=True)
        else: st.info("Δεν βρέθηκαν αγορές.")
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
    st.write("Θέλετε έκπτωση;")
    opt = st.radio("Επιλογή", ["ΟΧΙ", "ΝΑΙ"], horizontal=True, label_visibility="collapsed")
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή ποσοστό %", placeholder="π.χ. 5 ή 10%")
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
                num_map = {"ένα":1, "δυο":2, "δύο":2, "τρία":3, "τέσσερα":4, "πέντε":5, "δέκα":10, "είκοσι":20, "τριάντα":30, "σαράντα":40, "πενήντα":50, "εκατό":100}
                found_price = float(numbers[0]) if numbers else next((float(v) for k, v in num_map.items() if k in raw_query), None)
                if found_price:
                    clean_name = raw_query
                    if numbers: clean_name = clean_name.replace(numbers[0], "")
                    for w in ["ευρώ", "ευρω", "τιμή", "τιμη"] + list(num_map.keys()): clean_name = clean_name.replace(w, "")
                    price_to_add = -found_price if st.session_state.return_mode else found_price
                    st.session_state.cart.append({'bc': 'VOICE', 'name': clean_name.strip().upper() or "ΦΩΝΗΤΙΚΗ ΠΩΛΗΣΗ", 'price': price_to_add})
                    st.session_state.mic_key += 1; time.sleep(0.4); st.rerun()
                else:
                    speak_text("Δεν κατάλαβα")
                    st.warning("Σφάλμα: Δεν βρέθηκε το ποσό")

        st.divider()
        menu_options = ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ", "⚙️ SYSTEM"]
        def_idx = 1 if st.session_state.return_mode else 0
        view = st.radio("Μενού", menu_options, index=def_idx, key="sidebar_nav")
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        current_view = view if view != "🔄 ΕΠΙΣΤΡΟΦΗ" else "🛒 ΤΑΜΕΙΟ"

        if st.button("❌ Έξοδος", use_container_width=True):
            st.session_state.cart = []; st.session_state.is_logged_out = True; st.rerun()

    if current_view == "🛒 ΤΑΜΕΙΟ":
        if st.session_state.return_mode:
            st.button("🔄 ΛΕΙΤΟΥΡΓΙΑ ΕΠΙΣΤΡΟΦΗΣ (ΠΑΤΗΣΤΕ ΓΙΑ ΚΑΝΟΝΙΚΟ ΤΑΜΕΙΟ)", on_click=switch_to_normal, use_container_width=True)
            st.error("⚠️ ΤΩΡΑ ΣΚΑΝΑΡΕΤΕ ΤΗΝ ΕΠΙΣΤΡΟΦΗ (ΑΡΝΗΤΙΚΗ ΤΙΜΗ)")
        else:
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
                            st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                        else: new_customer_popup(clean_ph)
                    else:
                        speak_text("Λάθος τηλέφωνο")
                        st.error("Το τηλέφωνο πρέπει να έχει ακριβώς 10 ψηφία.")
                        time.sleep(1); st.session_state.ph_key += 1; st.rerun()
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name} (Αλλαγή)", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc and supabase:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data: 
                        val = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'bc': res.data[0]['barcode'], 'name': res.data[0]['name'].upper(), 'price': val})
                        st.session_state.bc_key += 1; st.rerun()
                    else:
                        speak_text(f"Barcode {bc} όχι")
                        st.error(f"Barcode {bc} όχι!"); time.sleep(1); st.session_state.bc_key += 1; st.rerun()
                for idx, item in enumerate(st.session_state.cart):
                    if st.button(f"❌ {item['name']} {item['price']}€", key=f"del_{idx}", use_container_width=True): st.session_state.cart.pop(idx); st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
            if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            lines = [f"{i['name'][:20]:<20} | {i['price']:>6.2f}€" for i in st.session_state.cart]
            st.markdown(f"<div class='cart-area'>{'Είδος':<20} | {'Τιμή':>6}\n{'-'*30}\n{chr(10).join(lines)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif current_view == "📊 MANAGER" and supabase:
        st.title("📊 Αναφορές")
        res_s = supabase.table("sales").select("*").execute()
        res_c = supabase.table("customers").select("id, name").execute()
        if res_s.data:
            df = pd.DataFrame(res_s.data)
            cust_dict = {c['id']: c['name'] for c in res_c.data} if res_c.data else {}
            df['ΠΕΛΑΤΗΣ'] = df['cust_id'].map(cust_dict).fillna("Λιανική")
            df['s_date_dt'] = pd.to_datetime(df['s_date'])
            df['ΗΜΕΡΟΜΗΝΙΑ'] = df['s_date_dt'].dt.date
            today_date = get_athens_now().date()
            
            csv_backup = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 BACKUP ALL SALES (CSV)", data=csv_backup, file_name=f"all_sales_{today_date}.csv", mime="text/csv", use_container_width=True)
            st.divider()

            t1, t2 = st.tabs(["📅 ΣΗΜΕΡΑ", "📆 ΑΝΑΦΟΡΑ ΠΕΡΙΟΔΟΥ"])
            
            with t1:
                tdf = df[df['ΗΜΕΡΟΜΗΝΙΑ'] == today_date].copy()
                if not tdf.empty:
                    m_t, c_t = tdf[tdf['method'] == 'Μετρητά'], tdf[tdf['method'] == 'Κάρτα']
                    st.markdown(f"<div class='report-stat' style='border: 2px solid #2ecc71;'><div style='color:#2ecc71; font-weight:bold;'>ΣΥΝΟΛΙΚΟΣ ΤΖΙΡΟΣ ΗΜΕΡΑΣ</div><div class='stat-val' style='font-size:40px;'>{tdf['final_item_price'].sum():.2f}€</div></div>", unsafe_allow_html=True)
                    c1, c2, c3 = st.columns(3)
                    c1.markdown(f"<div class='report-stat'>💵 Μετρητά<div class='stat-val'>{m_t['final_item_price'].sum():.2f}€</div><div class='stat-desc'>({m_t['s_date'].nunique()} πράξεις)</div></div>", unsafe_allow_html=True)
                    c2.markdown(f"<div class='report-stat'>💳 Κάρτα<div class='stat-val'>{c_t['final_item_price'].sum():.2f}€</div><div class='stat-desc'>({c_t['s_date'].nunique()} πράξεις)</div></div>", unsafe_allow_html=True)
                    c3.markdown(f"<div class='report-stat'>📉 Εκπτώσεις<div class='stat-val' style='color:#e74c3c;'>{tdf['discount'].sum():.2f}€</div><div class='stat-desc'>Σύνολο ημέρας</div></div>", unsafe_allow_html=True)
                    tdf['ΠΡΑΞΗ'] = tdf.groupby('s_date').ngroup() + 1
                    st.dataframe(tdf[['ΠΡΑΞΗ', 's_date', 'item_name', 'unit_price', 'discount', 'final_item_price', 'method', 'ΠΕΛΑΤΗΣ']].sort_values('s_date', ascending=False), use_container_width=True, hide_index=True)
                else: st.info("Δεν υπάρχουν πωλήσεις σήμερα.")

            with t2:
                cs, ce = st.columns(2); sd, ed = cs.date_input("Από", today_date-timedelta(days=7)), ce.date_input("Έως", today_date)
                pdf = df[(df['ΗΜΕΡΟΜΗΝΙΑ'] >= sd) & (df['ΗΜΕΡΟΜΗΝΙΑ'] <= ed)].sort_values('s_date_dt', ascending=False).copy()
                if not pdf.empty:
                    st.markdown(f"<div class='report-stat' style='border: 2px solid #3498db;'><div style='color:#3498db; font-weight:bold;'>ΣΥΝΟΛΙΚΟΣ ΤΖΙΡΟΣ ΠΕΡΙΟΔΟΥ</div><div class='stat-val' style='font-size:40px;'>{pdf['final_item_price'].sum():.2f}€</div></div>", unsafe_allow_html=True)
                    pm_all, pc_all = pdf[pdf['method'] == 'Μετρητά'], pdf[pdf['method'] == 'Κάρτα']
                    col1, col2, col3 = st.columns(3)
                    col1.markdown(f"<div class='report-stat' style='background-color:#1e1e1e;'>💵 Μετρητά<div class='stat-val'>{pm_all['final_item_price'].sum():.2f}€</div></div>", unsafe_allow_html=True)
                    col2.markdown(f"<div class='report-stat' style='background-color:#1e1e1e;'>💳 Κάρτα<div class='stat-val'>{pc_all['final_item_price'].sum():.2f}€</div></div>", unsafe_allow_html=True)
                    col3.markdown(f"<div class='report-stat' style='background-color:#1e1e1e;'>📉 Εκπτώσεις<div class='stat-val' style='color:#e74c3c;'>{pdf['discount'].sum():.2f}€</div></div>", unsafe_allow_html=True)
                    
                    all_days = sorted(pdf['ΗΜΕΡΟΜΗΝΙΑ'].unique(), reverse=True)
                    for day in all_days:
                        st.markdown(f"<div class='day-header'>📅 {day.strftime('%d/%m/%Y')}</div>", unsafe_allow_html=True)
                        day_df = pdf[pdf['ΗΜΕΡΟΜΗΝΙΑ'] == day].copy()
                        # Επαναφορά στήλης ΠΡΑΞΗ και στην αναφορά περιόδου
                        day_df['ΠΡΑΞΗ'] = day_df.groupby('s_date').ngroup() + 1
                        st.dataframe(day_df[['ΠΡΑΞΗ', 's_date', 'item_name', 'final_item_price', 'method', 'ΠΕΛΑΤΗΣ']].sort_values('s_date', ascending=False), use_container_width=True, hide_index=True)

    elif current_view == "📦 ΑΠΟΘΗΚΗ" and supabase:
        st.title("📦 Διαχείριση Αποθήκης")
        c1,c2,c3,c4 = st.columns(4)
        b, n = c1.text_input("BC"), c2.text_input("Όνομα")
        p, s = c3.number_input("Τιμή", min_value=0.0), c4.number_input("Stock", min_value=-999)
        if st.button("Προσθήκη", use_container_width=True):
            if b and n:
                try:
                    supabase.table("inventory").upsert({"barcode": str(b), "name": str(n).upper(), "price": float(p), "stock": int(s)}).execute()
                    st.success("Αποθηκεύτηκε!"); time.sleep(0.5); st.rerun()
                except Exception as e: st.error(f"Σφάλμα: {e}")
        st.divider()
        res = supabase.table("inventory").select("*").execute()
        if res.data:
            df_inv = pd.DataFrame(res.data).sort_values(by='name')
            for _, r in df_inv.iterrows():
                col1, col2 = st.columns([5, 1])
                stk_color = "#e74c3c" if r['stock'] <= 0 else "#2ecc71"
                item_text = f"📦 {str(r['barcode']):<8} | {r['name'][:25]:<25} | {float(r['price']):>6.2f}€ | Stock: <span style='color:{stk_color};'>{r['stock']}</span>"
                with col1: st.markdown(f"<div class='data-row'>{item_text}</div>", unsafe_allow_html=True)
                with col2:
                    if st.button("❌", key=f"inv_{r['barcode']}", use_container_width=True):
                        supabase.table("inventory").delete().eq("barcode", r['barcode']).execute(); st.rerun()

    elif current_view == "👥 ΠΕΛΑΤΕΣ" and supabase:
        st.title("👥 Διαχείριση Πελατών")
        res_c = supabase.table("customers").select("*").execute()
        res_s = supabase.table("sales").select("cust_id, final_item_price").execute()
        if res_c.data:
            df_cust = pd.DataFrame(res_c.data).sort_values(by='name')
            sales_data = pd.DataFrame(res_s.data) if res_s.data else pd.DataFrame(columns=['cust_id', 'final_item_price'])
            for _, r in df_cust.iterrows():
                pts = int(sales_data[sales_data['cust_id'] == r['id']]['final_item_price'].sum() // 10)
                col1, col2, col3, col4 = st.columns([4, 0.5, 0.5, 0.5])
                with col1: st.markdown(f"<div class='data-row'>👤 {r['name'][:25]} | 📞 {r['phone']} | ⭐ {pts} pts</div>", unsafe_allow_html=True)
                with col2:
                    if st.button("📜", key=f"h_{r['id']}", use_container_width=True): customer_history_popup(r)
                with col3:
                    if st.button("📝", key=f"e_{r['id']}", use_container_width=True): edit_customer_popup(r)
                with col4:
                    if st.button("❌", key=f"d_{r['id']}", use_container_width=True):
                        supabase.table("customers").delete().eq("id", r['id']).execute(); st.rerun()

    elif current_view == "⚙️ SYSTEM" and supabase:
        st.title("⚙️ Ρυθμίσεις Συστήματος")
        sys_pass = st.text_input("Εισάγετε τον κωδικό πρόσβασης (SYSTEM)", type="password")
        if sys_pass == "999":
            st.success("Πρόσβαση επετράπη.")
            st.warning("ΠΡΟΣΟΧΗ: Οι παρακάτω ενέργειες είναι μη αναστρέψιμες!")
            target = st.selectbox("Επιλέξτε αρχείο για αρχικοποίηση", 
                                   ["--- Επιλέξτε ---", "Πωλήσεις & Ταμείο (Sales)", "Πελατολόγιο (Customers)", "Αποθήκη (Inventory)"])
            if target != "--- Επιλέξτε ---":
                confirm_text = st.text_input(f"Για διαγραφή των {target}, γράψτε τη λέξη 'ΔΙΑΓΡΑΦΗ'")
                if confirm_text == "ΔΙΑΓΡΑΦΗ":
                    if st.button(f"🚀 ΕΚΤΕΛΕΣΗ ΑΡΧΙΚΟΠΟΙΗΣΗΣ {target.upper()}", use_container_width=True):
                        try:
                            table_name = ""
                            if "Sales" in target: table_name = "sales"
                            elif "Customers" in target: table_name = "customers"
                            elif "Inventory" in target: table_name = "inventory"
                            if table_name:
                                supabase.table(table_name).delete().neq("id", -1).execute()
                                st.success(f"Το αρχείο {target} αρχικοποιήθηκε επιτυχώς!")
                                time.sleep(2); st.rerun()
                        except Exception as e: st.error(f"Σφάλμα κατά την αρχικοποίηση: {e}")
        elif sys_pass != "":
            st.error("Λανθασμένος κωδικός πρόσβασης!")
