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

# --- HELPER FOR AUTO-LATIN CODE ---
def generate_latin_code(text):
    """Μετατρέπει τα 3 πρώτα γράμματα σε Λατινικά για το SKU"""
    char_map = {
        'Α': 'A', 'Β': 'B', 'Γ': 'G', 'Δ': 'D', 'Ε': 'E', 'Ζ': 'Z', 'Η': 'H', 'Θ': 'TH',
        'Ι': 'I', 'Κ': 'K', 'Λ': 'L', 'Μ': 'M', 'Ν': 'N', 'Ξ': 'X', 'Ο': 'O', 'Π': 'P',
        'Ρ': 'R', 'Σ': 'S', 'Τ': 'T', 'Υ': 'Y', 'Φ': 'F', 'Χ': 'CH', 'Ψ': 'PS', 'Ω': 'O'
    }
    text = text.upper()
    res = ""
    for char in text[:3]:
        res += char_map.get(char, char)
    return res

# --- 3. CONFIG & STYLE (Version v14.2.75) ---
st.set_page_config(page_title="CHERRY v14.2.75", layout="wide", page_icon="🍒")

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
        color: #2ecc71; overflow-x: auto; font-size: 16px;
    }
    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; margin-top: 10px; }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; font-weight: bold !important; }
    .data-row { font-family: 'Courier New', monospace; background-color: #262626; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; display: block; white-space: pre; }
    .report-stat { background-color: #262730; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; }
    .day-header { background-color: #34495e; color: #f1c40f; padding: 10px; border-radius: 5px; margin-top: 25px; margin-bottom: 10px; font-weight: bold; border-left: 8px solid #f1c40f; }
    </style>
    """, unsafe_allow_html=True)

# Session States Initialization
keys = ['logged_in', 'cart', 'selected_cust_id', 'cust_name', 'bc_key', 'ph_key', 'mic_key', 'return_mode']
default_vals = [False, [], None, "Λιανική Πώληση", 0, 100, 28000, False]
for k, v in zip(keys, default_vals):
    if k not in st.session_state: st.session_state[k] = v

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
    if 'sidebar_nav' in st.session_state: st.session_state.sidebar_nav = "🛒 ΤΑΜΕΙΟ"

def speak_text(text_to_say, play_beep=True):
    beep_js = "var context = new (window.AudioContext || window.webkitAudioContext)(); var osc = context.createOscillator(); osc.type = 'sawtooth'; osc.frequency.setValueAtTime(150, context.currentTime); osc.connect(context.destination); osc.start(); osc.stop(context.currentTime + 0.2);" if play_beep else ""
    speech_js = "var msg = new SpeechSynthesisUtterance('{}'); msg.lang = 'el-GR'; window.speechSynthesis.speak(msg);".format(text_to_say) if text_to_say else ""
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
                    st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']
                    st.success("Ο πελάτης καταχωρήθηκε!"); time.sleep(1); st.rerun()
            except Exception as e: st.error(f"Σφάλμα: {e}")

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
                    supabase.table("inventory").update({"stock": int(res_inv.data[0]['stock']) + change}).eq("barcode", i['bc']).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); st.balloons(); time.sleep(1.5); reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    opt = st.radio("Έκπτωση;", ["ΟΧΙ", "ΝΑΙ"], horizontal=True)
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή % (π.χ. 5 ή 10%)")
        if inp:
            try:
                disc = round((float(inp.replace("%",""))/100 * total), 2) if "%" in inp else round(float(inp), 2)
            except: st.error("Λάθος μορφή")
    st.markdown(f"<h2 style='text-align:center; color:red;'>ΠΛΗΡΩΤΕΟ: {total-disc:.2f}€</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

# --- 5. LOGIN ---
if not st.session_state.logged_in:
    st.title("🔒 CHERRY LOGIN")
    pwd = st.text_input("Password", type="password")
    if st.button("Είσοδος"):
        if pwd == "CHERRY123":
            st.session_state.logged_in = True
            st.rerun()
else:
    # --- 6. MAIN APP ---
    with st.sidebar:
        now = get_athens_now()
        chosen_date = st.date_input("Ημερομηνία", value=now.date())
        chosen_time = st.time_input("Ώρα", value=now.time())
        st.session_state.manual_ts = datetime.combine(chosen_date, chosen_time)
        
        if HAS_MIC:
            text = speech_to_text(language='el', key=f"v_{st.session_state.mic_key}")
            if text:
                nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
                if nums:
                    p = float(nums[0])
                    st.session_state.cart.append({'bc': 'VOICE', 'name': text.upper(), 'price': -p if st.session_state.return_mode else p})
                    st.session_state.mic_key += 1; st.rerun()

        menu = ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"]
        view = st.radio("Μενού", menu, key="sidebar_nav")
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        current_view = "🛒 ΤΑΜΕΙΟ" if view == "🔄 ΕΠΙΣΤΡΟΦΗ" else view
        if st.button("❌ Logout"): st.session_state.logged_in = False; st.rerun()

    if current_view == "🛒 ΤΑΜΕΙΟ":
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"ph_{st.session_state.ph_key}")
                if ph and len(ph) == 10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                    else: new_customer_popup(ph)
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ"): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.write(f"👤 {st.session_state.cust_name}")
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        p = float(res.data[0]['price'])
                        st.session_state.cart.append({'bc': bc, 'name': res.data[0]['name'], 'price': -p if st.session_state.return_mode else p})
                        st.session_state.bc_key += 1; st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ"): payment_popup()
                if st.button("🔄 ΑΚΥΡΩΣΗ"): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            st.markdown("<div class='cart-area'>" + "\n".join([f"{i['name'][:30]:30} | {i['price']:.2f}€" for i in st.session_state.cart]) + "</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif current_view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Αποθήκη")
        if 'inv_rk' not in st.session_state: st.session_state.inv_rk = 0
        rk = st.session_state.inv_rk
        
        with st.expander("➕ ΝΕΟ ΠΡΟΪΟΝ", expanded=True):
            c1, c2, c3 = st.columns(3)
            # Λίστες
            e_dict = {"Ζακέτα":"ZAK", "Μπλούζα":"MPL", "Παντελόνι":"PAN", "Φόρεμα":"FOR", "Φούστα":"FOU"}
            p_dict = {"ONADO":"ONA", "PINUP":"PIN", "ΡΕΝΑ":"REN"}
            c_dict = {"Μαύρο":"BLK", "Λευκό":"WHT", "Μπλε":"BLU", "Κόκκινο":"RED"}
            
            eidos = c1.selectbox("Είδος", list(e_dict.keys()) + ["+ Νέο"], key=f"e_{rk}")
            prom = c2.selectbox("Προμηθευτής", list(p_dict.keys()) + ["+ Νέο"], key=f"p_{rk}")
            chroma = c3.selectbox("Χρώμα", list(c_dict.keys()) + ["+ Νέο"], key=f"c_{rk}")
            
            c4, c5, c6 = st.columns(3)
            size = c4.selectbox("Μέγεθος", ["One Size", "S", "M", "L", "XL", "XXL"], key=f"s_{rk}")
            synth = c5.selectbox("Σύνθεση", ["100% Βαμβάκι", "100% Πολυέστερ", "Σύμμεικτο"], key=f"sy_{rk}")
            plan = c6.text_input("Κωδικός Σχεδίου", key=f"pl_{rk}")
            
            c7, c8, c9 = st.columns(3)
            price = c7.number_input("Τιμή", min_value=0.0, step=0.1, key=f"pr_{rk}")
            stock = c8.number_input("Απόθεμα", min_value=0, step=1, key=f"st_{rk}")
            labels = c9.number_input("Ετικέτες", min_value=0, value=int(stock), key=f"la_{rk}")
            
            if st.button("💾 Αποθήκευση & Παραγωγή Ετικετών"):
                if plan:
                    sku = f"{e_dict.get(eidos,'INV')}-{p_dict.get(prom,'PRM')}-{plan}-{c_dict.get(chroma,'COL')}-{size}".upper()
                    full_n = f"{eidos} {chroma} ({synth})".upper()
                    supabase.table("inventory").upsert({"barcode": sku, "name": full_n, "price": price, "stock": stock}).execute()
                    st.success("Αποθηκεύτηκε!"); st.session_state.inv_rk += 1; time.sleep(1); st.rerun()

        res = supabase.table("inventory").select("*").execute()
        if res.data:
            df_inv = pd.DataFrame(res.data)
            st.dataframe(df_inv, use_container_width=True)

    elif current_view == "📊 MANAGER":
        st.title("📊 Αναφορές")
        res = supabase.table("sales").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            st.metric("Συνολικός Τζίρος", f"{df['final_item_price'].sum():.2f}€")
            st.dataframe(df, use_container_width=True)
            
    elif current_view == "👥 ΠΕΛΑΤΕΣ":
        st.title("👥 Πελάτες")
        res = supabase.table("customers").select("*").execute()
        if res.data:
            st.dataframe(pd.DataFrame(res.data), use_container_width=True)
