import pandas as pd
from datetime import datetime, date, timedelta
import time
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client, Client

# --- 1. SUPABASE SETUP ---
SUPABASE_URL = "https://hnwynihjkdkryrfepenh.supabase.co"
SUPABASE_KEY = "sb_publishable_ualF72lJKgUQA4TzjPQ-OA_zih7zJ-s"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# --- 2. CONFIG & STYLE ---
st.set_page_config(page_title="CHERRY v14.1.0", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    div[data-testid="stDialog"] label p, div[data-testid="stDialog"] h3, div[data-testid="stDialog"] .stMarkdown p, div[data-testid="stDialog"] [data-testid="stWidgetLabel"] p { color: #111111 !important; }
    input { color: #000000 !important; }
    .cart-area { font-family: 'Courier New', monospace; background-color: #2b2b2b; padding: 15px; border-radius: 5px; white-space: pre-wrap; border: 1px solid #3b3b3b; min-height: 200px; font-size: 14px; }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; margin: 10px 0; border: 2px solid #e44d26; padding: 10px; border-radius: 10px; background-color: #fff3f0; }
    .report-stat { background-color: #262730; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; margin: 0; }
    .stat-label { font-size: 13px; color: #888; margin: 0; font-weight: bold; text-transform: uppercase; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; border: 1px solid #ffffff !important; font-weight: bold !important; }
    .data-row { background-color: #262626; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; text-align: left; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'is_logged_out' not in st.session_state: st.session_state.is_logged_out = False

# --- 3. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart = []
    st.session_state.selected_cust_id = None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1; st.session_state.ph_key += 1
    st.rerun()

def voice_component():
    # JavaScript για την αναγνώριση φωνής
    components.html("""
        <script>
        const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'el-GR';
        recognition.interimResults = false;

        window.parent.document.addEventListener('startVoice', () => {
            recognition.start();
        });

        recognition.onresult = (event) => {
            const text = event.results[0][0].transcript;
            // Στέλνουμε το κείμενο πίσω στο Streamlit μέσω ενός κρυφού κουμπιού ή απευθείας
            window.parent.postMessage({type: 'voice_result', text: text}, "*");
        };
        </script>
    """, height=0)

@st.dialog("📦 ΕΛΕΥΘΕΡΟ ΕΙΔΟΣ (999)")
def manual_item_popup():
    st.write("Πείτε π.χ.: 'Κούρεμα και δέκα ευρώ'")
    
    # JavaScript για να ακούει το αποτέλεσμα της φωνής
    st.components.v1.html("""
    <script>
    const recognition = new (window.webkitSpeechRecognition || window.SpeechRecognition)();
    recognition.lang = 'el-GR';
    
    function startRec() {
        recognition.start();
    }

    recognition.onresult = function(event) {
        const result = event.results[0][0].transcript;
        const parent = window.parent.document;
        
        // Χωρίζουμε τη φράση στη λέξη "και"
        let parts = result.split(" και ");
        let name = parts[0] || "";
        let priceStr = parts[1] || "";
        
        // Καθαρισμός τιμής (αφαίρεση λέξεων όπως ευρώ, κλπ)
        let price = priceStr.replace(/[^0-9,.]/g, '').replace(',', '.');
        
        // Ενημέρωση των πεδίων του Streamlit (μέσω των selectors)
        const inputs = parent.querySelectorAll('input');
        inputs.forEach(input => {
            if (input.ariaLabel === "Όνομα Είδους") input.value = name;
            if (input.type === "number") input.value = price;
            // Trigger input events
            input.dispatchEvent(new Event('input', { bubbles: true }));
        });
    };
    </script>
    <button onclick="startRec()" style="width:100%; height:40px; border-radius:10px; background:#e74c3c; color:white; font-weight:bold; cursor:pointer;">🎤 ΠΑΤΗΣΤΕ ΓΙΑ ΦΩΝΗΤΙΚΗ ΚΑΤΑΧΩΡΗΣΗ</button>
    """, height=60)

    m_name = st.text_input("Όνομα Είδους", key="v_name")
    m_price = st.number_input("Τιμή (€)", min_value=0.0, format="%.2f", step=0.1, key="v_price")
    
    if st.button("ΠΡΟΣΘΗΚΗ", use_container_width=True):
        if m_name:
            st.session_state.cart.append({'bc': '999', 'name': m_name, 'price': round(float(m_price), 2)})
            st.session_state.bc_key += 1; st.rerun()

def finalize(disc_val, method):
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
        st.success("ΟΛΟΚΛΗΡΩΘΗΚΕ!"); time.sleep(0.5); reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

@st.dialog("💰 ΠΛΗΡΩΜΗ")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center; color: #111;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    opt = st.radio("Έκπτωση;", ["ΟΧΙ", "ΝΑΙ"], horizontal=True)
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή % (π.χ. 10%)")
        if inp:
            try:
                if "%" in inp: disc = round((float(inp.replace("%",""))/100 * total), 2)
                else: disc = round(float(inp), 2)
            except: st.error("Σφάλμα τιμής")
    final_p = round(total - disc, 2)
    st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {final_p:.2f}€</div>", unsafe_allow_html=True)
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("💵 ΜΕΤΡΗΤΑ", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 ΚΑΡΤΑ", use_container_width=True): finalize(disc, "Κάρτα")

def display_report(sales_df):
    if sales_df.empty:
        st.info("Δεν υπάρχουν δεδομένα."); return
    df = sales_df.copy()
    df['s_date_dt'] = pd.to_datetime(df['s_date'])
    df['day_str'] = df['s_date_dt'].dt.strftime('%Y-%m-%d')
    df = df.sort_values('s_date', ascending=True)
    
    unique_trans = df.groupby(['day_str', 's_date']).agg({'final_item_price': 'sum', 'method': 'first'}).reset_index()
    unique_trans['ΠΡΑΞΗ'] = unique_trans.groupby('day_str').cumcount() + 1
    df = df.merge(unique_trans[['s_date', 'ΠΡΑΞΗ']], on='s_date')

    for day, day_data in df.groupby('day_str', sort=True):
        st.subheader(f"📅 {datetime.strptime(day, '%Y-%m-%d').strftime('%d/%m/%Y')}")
        st.dataframe(day_data[['ΠΡΑΞΗ', 's_date', 'item_name', 'unit_price', 'discount', 'final_item_price', 'method']].sort_values('ΠΡΑΞΗ', ascending=True), use_container_width=True, hide_index=True)

# --- 4. MAIN UI ---
with st.sidebar:
    now = get_athens_now()
    st.markdown(f"<div class='sidebar-date'>📅 {now.strftime('%d/%m/%Y')}<br>🕒 {now.strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)
    st.title("CHERRY 14.1.0")
    view = st.radio("ΜΕΝΟΥ", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])

if view == "🛒 ΤΑΜΕΙΟ":
    st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
    cl, cr = st.columns([1, 1.5])
    with cl:
        if st.session_state.selected_cust_id is None:
            ph = st.text_input("Τηλέφωνο Πελάτη", key=f"ph_{st.session_state.ph_key}")
            if ph:
                res = supabase.table("customers").select("*").eq("phone", ph.strip()).execute()
                if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
            if st.button("🛒 ΛΙΑΝΙΚΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
        else:
            bc = st.text_input("Σάρωση Barcode", key=f"bc_{st.session_state.bc_key}")
            if bc:
                if bc.strip() == "999": manual_item_popup()
                else:
                    res = supabase.table("inventory").select("*").eq("barcode", bc.strip()).execute()
                    if res.data:
                        it = res.data[0]
                        st.session_state.cart.append({'bc': it['barcode'], 'name': it['name'], 'price': round(float(it['price']), 2)})
                        st.session_state.bc_key += 1; st.rerun()
            if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
            if st.button("🗑️ ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()

    with cr:
        total = sum(i['price'] for i in st.session_state.cart)
        lines = [f"{i['name'][:20]:<20} | {i['price']:>6.2f}€" for i in st.session_state.cart]
        st.markdown(f"<div class='cart-area'>{'ΕΙΔΟΣ':<20} | {'ΤΙΜΗ':>6}\n{'-'*30}\n{chr(10).join(lines)}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

elif view == "📊 MANAGER":
    res = supabase.table("sales").select("*").execute()
    if res.data:
        df = pd.DataFrame(res.data)
        display_report(df[pd.to_datetime(df['s_date']).dt.date == get_athens_now().date()])
    else: st.info("Δεν υπάρχουν πωλήσεις.")

# (Οι υπόλοιπες σελίδες Αποθήκη/Πελάτες παραμένουν ίδιες)
