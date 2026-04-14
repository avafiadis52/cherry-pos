import pandas as pd
from datetime import datetime, date, timedelta
import time
import streamlit as st
from supabase import create_client, Client
import re
import plotly.express as px
import barcode
from barcode.writer import ImageWriter
import io
import base64

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
st.set_page_config(page_title="CHERRY v14.8.1", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; }
    
    .cart-area { 
        font-family: 'Courier New', monospace;
        background-color: #000000; padding: 15px; border-radius: 10px; 
        white-space: pre; border: 4px solid #2ecc71 !important;
        box-shadow: 0 0 15px rgba(46, 204, 113, 0.4); min-height: 300px; 
        color: #2ecc71;
        overflow-x: auto;
        font-size: 16px;
    }

    @media only screen and (max-width: 600px) {
        .cart-area { font-size: 2.8vw; padding: 8px; }
        .total-label { font-size: 50px !important; }
    }

    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; margin-top: 10px; text-shadow: 2px 2px 10px rgba(46, 204, 113, 0.5); }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; padding: 10px; border-radius: 10px; background-color: #fff3f0; border: 2px solid #e44d26; }
    
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; font-weight: bold !important; border: 1px solid #808080 !important; }
    
    .data-row { font-family: 'Courier New', monospace; background-color: #262626; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; display: block; white-space: pre; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    .report-stat { background-color: #262730; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; }
    .stat-desc { font-size: 13px; color: #888; }
    .day-header { background-color: #34495e; color: #f1c40f; padding: 10px; border-radius: 5px; margin-top: 25px; margin-bottom: 10px; font-weight: bold; border-left: 8px solid #f1c40f; }
    table { color: white !important; }
    thead tr th { color: white !important; background-color: #333 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. DATA LOGIC & DEFAULTS ---
DEFAULT_LISTS = {
    "Είδη": ["Ζακέτα", "Ζώνη", "Μπλούζα", "Μπουφάν / Παλτό", "Παντελόνι", "Πουκάμισο", "Φόρεμα", "Φούστα"],
    "Προμηθευτές": ["ONADO", "PINUP", "ΡΕΝΑ", "ΣΤΕΛΛΑ", "ΤΖΕΝΗ"],
    "Χρώματα": ["Γκρι", "Εκρού", "Εμπριμέ", "Καφέ", "Κίτρινο", "Κόκκινο", "Λευκό", "Μαύρο", "Μπεζ", "Μπλε", "Πουά", "Πράσινο", "Ριγέ", "Σιέλ"],
    "Μεγέθη": ["One Size", "Small", "Medium", "Large", "XL", "XXL", "36", "38", "40", "42", "44"],
    "Συνθέσεις": ["100% Βαμβάκι", "100% Πολυέστερ", "70% Βαμβάκι - 30% Πολυέστερ", "98% Βαμβάκι - 2% Ελαστάνη", "100% Δέρμα", "Τεχνητό Δέρμα (PU)"]
}

def sync_master_lists():
    if supabase:
        try:
            res = supabase.table("inventory_settings").select("config_value").eq("config_name", "master_lists").execute()
            if res.data:
                st.session_state.master_lists = res.data[0]['config_value']
            else:
                st.session_state.master_lists = DEFAULT_LISTS.copy()
                save_master_lists()
        except Exception:
            if 'master_lists' not in st.session_state:
                st.session_state.master_lists = DEFAULT_LISTS.copy()

def save_master_lists():
    if supabase and 'master_lists' in st.session_state:
        try:
            supabase.table("inventory_settings").upsert({"config_name": "master_lists", "config_value": st.session_state.master_lists}).execute()
            return True
        except Exception:
            st.warning("Η αλλαγή έγινε τοπικά (Πρόβλημα σύνδεσης με inventory_settings).")
            return True

# Session States
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'mic_key' not in st.session_state: st.session_state.mic_key = 28000
if 'return_mode' not in st.session_state: st.session_state.return_mode = False
if 'form_reset_key' not in st.session_state: st.session_state.form_reset_key = 0

sync_master_lists()

# --- 5. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def generate_latin_code(text):
    char_map = {
        'Α':'A','Β':'B','Γ':'G','Δ':'D','Ε':'E','Ζ':'Z','Η':'H','Θ':'TH','Ι':'I','Κ':'K','Λ':'L','Μ':'M','Ν':'N','Ξ':'X','Ο':'O','Π':'P','Ρ':'R','Σ':'S','Τ':'T','Υ':'Y','Φ':'F','Χ':'CH','Ψ':'PS','Ω':'O',
        'Ά':'A','Έ':'E','Ή':'H','Ί':'I','Ό':'O','Ύ':'Y','Ώ':'O','Ϊ':'I','Ϋ':'Y'
    }
    res = "".join([char_map.get(c, c) for c in str(text).upper()])
    return res[:3]

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

@st.dialog("🏷️ Ετικέτα")
def print_label_popup(bc, name, price):
    label_html = f"""<div style='text-align:center; background:white; color:black; padding:10px; border:1px solid #000; font-family:Arial;'>
        <b>CHERRY</b><br><small>{name}</small><br><h3>{price:.2f}€</h3><br><small>{bc}</small></div>"""
    st.markdown(label_html, unsafe_allow_html=True)
    if st.button("ΕΚΤΥΠΩΣΗ"):
        st.components.v1.html(f"<script>window.print();</script>", height=0)

@st.dialog("👤 Νέος Πελάτης")
def new_customer_popup(phone):
    st.write("Το τηλέφωνο **{}** δεν υπάρχει στη βάση.".format(phone))
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
            except Exception as e: st.error("Σφάλμα: {}".format(e))
        else: st.warning("Παρακαλώ δώστε όνομα.")

def finalize(disc_val, method):
    if not supabase: return
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = st.session_state.get('manual_ts', get_athens_now()).strftime("%Y-%m-%d %H:%M:%S")
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
    except Exception as e: st.error("Σφάλμα: {}".format(e))

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown("<h3 style='text-align:center;'>Σύνολο: {:.2f}€</h3>".format(total), unsafe_allow_html=True)
    inp = st.text_input("Έκπτωση (ποσό ή %)", placeholder="π.χ. 5 ή 10%")
    disc = 0.0
    if inp:
        try:
            if "%" in inp: disc = round((float(inp.replace("%",""))/100 * total), 2)
            else: disc = round(float(inp), 2)
        except: st.error("Λάθος μορφή")
    final_p = round(total - disc, 2)
    st.markdown("<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {:.2f}€</div>".format(final_p), unsafe_allow_html=True)
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

@st.dialog("⭐ Loyalty Card")
def show_customer_history(c_id, c_name):
    st.subheader(f"Καρτέλα: {c_name}")
    res = supabase.table("sales").select("*").eq("cust_id", c_id).order("s_date", desc=True).execute()
    if res.data:
        pdf = pd.DataFrame(res.data)
        st.metric("Συνολικές Αγορές", f"{pdf['final_item_price'].sum():.2f}€")
        st.dataframe(pdf[['s_date', 'item_name', 'unit_price', 'final_item_price', 'method']], use_container_width=True, hide_index=True)
    else:
        st.info("Δεν βρέθηκαν πωλήσεις για αυτόν τον πελάτη.")

# --- 6. LOGIN LOGIC ---
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<h1 style='text-align:center;'>🔒 CHERRY LOGIN</h1>", unsafe_allow_html=True)
        pwd = st.text_input("Password", type="password")
        if st.button("Είσοδος", use_container_width=True):
            if pwd == "CHERRY123":
                st.session_state.logged_in = True
                st.success("Επιτυχής σύνδεση!")
                time.sleep(0.5); st.rerun()
            else: st.error("❌ Λάθος κωδικός")
else:
    # --- 7. MAIN UI ---
    with st.sidebar:
        current_athens = get_athens_now()
        chosen_date = st.date_input("Ημερομηνία", value=current_athens.date())
        chosen_time = st.time_input("Ώρα", value=current_athens.time())
        st.session_state.manual_ts = datetime.combine(chosen_date, chosen_time)
        st.markdown("<div class='sidebar-date'>{}</div>".format(st.session_state.manual_ts.strftime('%d/%m/%Y %H:%M:%S')), unsafe_allow_html=True)
        
        if HAS_MIC:
            text = speech_to_text(language='el', start_prompt="🔴 ΠΑΤΑ ΚΑΙ ΜΙΛΑ", key="voice_{}".format(st.session_state.mic_key))
            if text:
                raw_query = text.lower().strip()
                numbers = re.findall(r"[-+]?\d*\.\d+|\d+", raw_query)
                if numbers:
                    found_price = float(numbers[0])
                    price_to_add = -found_price if st.session_state.return_mode else found_price
                    st.session_state.cart.append({'bc': 'VOICE', 'name': raw_query.upper(), 'price': price_to_add})
                    st.session_state.mic_key += 1; time.sleep(0.4); st.rerun()

        st.divider()
        menu_options = ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ", "⚙️ SYSTEM"]
        def_idx = 1 if st.session_state.return_mode else 0
        view = st.radio("Μενού", menu_options, index=def_idx, key="sidebar_nav")
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        current_view = view if view != "🔄 ΕΠΙΣΤΡΟΦΗ" else "🛒 ΤΑΜΕΙΟ"
        
        if st.button("❌ Έξοδος / Κλείδωμα", use_container_width=True): 
            st.session_state.logged_in = False
            st.session_state.cart = []
            st.rerun()

    # --- VIEW ROUTING ---
    if current_view == "🛒 ΤΑΜΕΙΟ":
        if st.session_state.return_mode:
            st.button("🔄 ΛΕΙΤΟΥΡΓΙΑ ΕΠΙΣΤΡΟΦΗΣ (ΚΛΙΚ ΓΙΑ ΚΑΝΟΝΙΚΟ)", on_click=switch_to_normal, use_container_width=True)
        else:
            st.markdown("<div class='status-header'>Πελάτης: {}</div>".format(st.session_state.cust_name), unsafe_allow_html=True)
            
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο (10 ψηφία)", key="ph_{}".format(st.session_state.ph_key))
                if ph:
                    clean_ph = ''.join(filter(str.isdigit, ph))
                    if len(clean_ph) == 10:
                        res = supabase.table("customers").select("*").eq("phone", clean_ph).execute()
                        if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                        else: new_customer_popup(clean_ph)
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button("👤 {} (Αλλαγή)".format(st.session_state.cust_name), on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                bc = st.text_input("Barcode", key="bc_{}".format(st.session_state.bc_key))
                if bc and supabase:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data: 
                        val = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'bc': res.data[0]['barcode'], 'name': res.data[0]['name'].upper(), 'price': val})
                        st.session_state.bc_key += 1; st.rerun()
                    else: st.error("⚠️ Το Barcode δεν υπάρχει")
                for idx, item in enumerate(st.session_state.cart):
                    if st.button("❌ {} {}€".format(item['name'], item['price']), key="del_{}".format(idx), use_container_width=True): st.session_state.cart.pop(idx); st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
            if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            lines = ["{:45} | {:>4.2f}€".format(i['name'][:45], i['price']) for i in st.session_state.cart]
            st.markdown("<div class='cart-area'>{:45} | {:>4}\n{}\n{}</div>".format('Είδος', 'Τιμή', '-'*56, '\n'.join(lines)), unsafe_allow_html=True)
            st.markdown("<div class='total-label'>{:.2f}€</div>".format(total), unsafe_allow_html=True)

    elif current_view == "📊 MANAGER" and supabase:
        st.title("📊 Αναφορές")
        if st.text_input("Κωδικός MANAGER", type="password") == "999":
            res_s = supabase.table("sales").select("*").execute()
            if res_s.data:
                df = pd.DataFrame(res_s.data)
                df['s_date_dt'] = pd.to_datetime(df['s_date'])
                df['ΗΜΕΡΟΜΗΝΙΑ'] = df['s_date_dt'].dt.date
                today_date = st.session_state.get('manual_ts', get_athens_now()).date()
                
                t1, t2, t3 = st.tabs(["📅 ΣΗΜΕΡΑ", "📆 ΑΝΑΦΟΡΑ ΠΕΡΙΟΔΟΥ", "📈 INSIGHTS"])
                with t1:
                    tdf = df[df['ΗΜΕΡΟΜΗΝΙΑ'] == today_date].copy()
                    if not tdf.empty:
                        st.metric("Τζίρος Ημέρας", f"{tdf['final_item_price'].sum():.2f}€")
                        st.dataframe(tdf[['s_date', 'item_name', 'final_item_price', 'method']], use_container_width=True)
                    else: st.info("Δεν υπάρχουν πωλήσεις σήμερα.")
                with t2:
                    cs, ce = st.columns(2)
                    sd, ed = cs.date_input("Από", today_date-timedelta(days=7)), ce.date_input("Έως", today_date)
                    pdf = df[(df['ΗΜΕΡΟΜΗΝΙΑ'] >= sd) & (df['ΗΜΕΡΟΜΗΝΙΑ'] <= ed)]
                    st.metric("Τζίρος Περιόδου", f"{pdf['final_item_price'].sum():.2f}€")
                    st.dataframe(pdf, use_container_width=True)
                with t3:
                    fig = px.bar(df.groupby('ΗΜΕΡΟΜΗΝΙΑ')['final_item_price'].sum().reset_index(), x='ΗΜΕΡΟΜΗΝΙΑ', y='final_item_price', title="Πορεία Τζίρου")
                    st.plotly_chart(fig, use_container_width=True)

    elif current_view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Αποθήκη")
        t_new, t_set, t_inv = st.tabs(["🆕 ΝΕΟ", "⚙️ ΡΥΘΜΙΣΕΙΣ", "📋 LIST"])
        with t_new:
            with st.form(f"inv_{st.session_state.form_reset_key}", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                f_item = c1.selectbox("Είδος", sorted(st.session_state.master_lists["Είδη"]))
                f_prov = c2.selectbox("Προμηθευτής", sorted(st.session_state.master_lists["Προμηθευτές"]))
                f_design = c3.text_input("Σχέδιο / Κωδικός")
                c4, c5, c6 = st.columns(3)
                f_color = c4.selectbox("Χρώμα", sorted(st.session_state.master_lists["Χρώματα"]))
                f_size = c5.selectbox("Μέγεθος", sorted(st.session_state.master_lists["Μεγέθη"]))
                f_price = c6.number_input("Τιμή Πώλησης (€)", min_value=0.0)
                if st.form_submit_button("ΑΠΟΘΗΚΕΥΣΗ ΠΡΟΪΟΝΤΟΣ"):
                    if f_design:
                        sku = f"{generate_latin_code(f_item)}-{generate_latin_code(f_prov)}-{f_design.upper()}"
                        full_name = f"{f_item} {f_color} ({f_size})".upper()
                        try:
                            supabase.table("inventory").upsert({"barcode":sku, "name":full_name, "price":float(f_price), "stock":1}).execute()
                            st.success(f"Καταχωρήθηκε: {sku}")
                            st.session_state.form_reset_key += 1; time.sleep(1); st.rerun()
                        except Exception as e: st.error(f"Σφάλμα: {e}")
                    else: st.warning("Δώστε Σχέδιο.")

        with t_set:
            cat = st.selectbox("Επιλέξτε Λίστα", list(st.session_state.master_lists.keys()))
            new_v = st.text_input("Νέα Τιμή")
            if st.button("Προσθήκη"):
                if new_v and new_v not in st.session_state.master_lists[cat]:
                    st.session_state.master_lists[cat].append(new_v)
                    save_master_lists(); st.rerun()
            st.write("---")
            for v in sorted(st.session_state.master_lists[cat]):
                col1, col2 = st.columns([4,1])
                col1.write(v)
                if col2.button("🗑️", key=f"del_{v}"):
                    st.session_state.master_lists[cat].remove(v)
                    save_master_lists(); st.rerun()
        
        with t_inv:
            res = supabase.table("inventory").select("*").execute()
            if res.data:
                for r in sorted(res.data, key=lambda x: x['name']):
                    c1, c2, c3 = st.columns([5,1,1])
                    c1.markdown(f"<div class='data-row'>📦 {r['barcode']} | {r['name']} | {r['price']:.2f}€ | Stock: {r['stock']}</div>", unsafe_allow_html=True)
                    if c2.button("🏷️", key=f"pr_{r['barcode']}"): print_label_popup(r['barcode'], r['name'], r['price'])
                    if c3.button("❌", key=f"dl_{r['barcode']}"): 
                        supabase.table("inventory").delete().eq("barcode", r['barcode']).execute(); st.rerun()

    elif current_view == "👥 ΠΕΛΑΤΕΣ" and supabase:
        st.title("👥 Πελάτες")
        res_c = supabase.table("customers").select("*").execute()
        if res_c.data:
            for r in res_c.data:
                c1, c2, c3 = st.columns([5,1,1])
                c1.markdown(f"<div class='data-row'>👤 {r['name']} | 📞 {r['phone']}</div>", unsafe_allow_html=True)
                if c2.button("⭐", key=f"pts_{r['id']}"): show_customer_history(r['id'], r['name'])
                if c3.button("❌", key=f"d_{r['id']}"): supabase.table("customers").delete().eq("id", r['id']).execute(); st.rerun()

    elif current_view == "⚙️ SYSTEM" and supabase:
        st.title("⚙️ Ρυθμίσεις")
        if st.text_input("Κωδικός SYSTEM", type="password") == "999":
            if st.button("ΔΙΑΓΡΑΦΗ ΠΩΛΗΣΕΩΝ"):
                supabase.table("sales").delete().neq("id", -1).execute()
                st.success("OK"); st.rerun()
