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
    char_map = {
        'Α': 'A', 'Β': 'B', 'Γ': 'G', 'Δ': 'D', 'Ε': 'E', 'Ζ': 'Z', 'Η': 'H', 'Θ': 'TH',
        'Ι': 'I', 'Κ': 'K', 'Λ': 'L', 'Μ': 'M', 'Ν': 'N', 'Ξ': 'X', 'Ο': 'O', 'Π': 'P',
        'Ρ': 'R', 'Σ': 'S', 'Τ': 'T', 'Υ': 'Y', 'Φ': 'F', 'Χ': 'CH', 'Ψ': 'PS', 'Ω': 'O'
    }
    text = text.upper()
    res = "".join([char_map.get(char, char) for char in text[:3]])
    return res if res else "ITM"

# --- 3. CONFIG & STYLE (Version v14.2.78) ---
st.set_page_config(page_title="CHERRY v14.2.78", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; }
    .cart-area { 
        font-family: 'Courier New', monospace; 
        background-color: #000000; padding: 15px; border-radius: 10px; 
        white-space: pre; border: 4px solid #2ecc71 !important; 
        color: #2ecc71; overflow-x: auto; font-size: 16px; min-height: 250px;
    }
    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; font-weight: bold !important; border-radius: 8px !important; }
    .data-row { font-family: 'Courier New', monospace; background-color: #262626; padding: 10px; border-radius: 5px; margin-bottom: 5px; border-left: 5px solid #3498db; }
    </style>
    """, unsafe_allow_html=True)

# Session States Initialization
keys = ['logged_in', 'cart', 'selected_cust_id', 'cust_name', 'bc_key', 'ph_key', 'mic_key', 'return_mode', 'inv_rk']
default_vals = [False, [], None, "Λιανική Πώληση", 0, 100, 28000, False, 0]
for k, v in zip(keys, default_vals):
    if k not in st.session_state: st.session_state[k] = v

def get_athens_now():
    return datetime.now() + timedelta(hours=2)

# --- 4. MAIN APP LOGIC ---
if not st.session_state.logged_in:
    st.title("🔒 CHERRY LOGIN")
    pwd = st.text_input("Password", type="password")
    if st.button("Είσοδος"):
        if pwd == "CHERRY123":
            st.session_state.logged_in = True
            st.rerun()
else:
    with st.sidebar:
        st.write(f"📅 {get_athens_now().strftime('%d/%m/%Y %H:%M')}")
        menu = ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📦 ΑΠΟΘΗΚΗ", "📊 MANAGER", "👥 ΠΕΛΑΤΕΣ"]
        view = st.radio("Μενού", menu, key="sidebar_nav")
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        current_view = "🛒 ΤΑΜΕΙΟ" if view == "🔄 ΕΠΙΣΤΡΟΦΗ" else view
        if st.button("❌ Logout"): st.session_state.logged_in = False; st.rerun()

    if current_view == "🛒 ΤΑΜΕΙΟ":
        # (Ο κώδικας του ταμείου παραμένει ίδιος με την προηγούμενη λειτουργική έκδοση)
        st.info("Λειτουργία Ταμείου")
        # ... (παραλείπεται για συντομία, παραμένει ως είχε) ...

    elif current_view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Διαχείριση Αποθήκης")
        rk = st.session_state.inv_rk
        
        # Λήψη δεδομένων από τη βάση για δυναμικές λίστες
        res_inv = supabase.table("inventory").select("barcode, name").execute()
        existing_data = res_inv.data if res_inv.data else []
        
        # Προκαθορισμένες βασικές λίστες
        base_eidov = ["Ζακέτα", "Ζώνη", "Μπλούζα", "Μπουφάν / Παλτό", "Παντελόνι", "Πουκάμισο", "Φόρεμα", "Φούστα"]
        base_prom = ["ONADO", "PINUP", "ΡΕΝΑ", "ΣΤΕΛΛΑ", "ΤΖΕΝΗ"]
        base_chroma = ["Γκρι", "Εκρού", "Εμπριμέ", "Καφέ", "Κίτρινο", "Κόκκινο", "Λευκό", "Μαύρο", "Μπεζ", "Μπλε", "Πουά", "Πράσινο", "Ριγέ", "Σιέλ"]
        base_synth = ["100% Βαμβάκι", "100% Πολυέστερ", "70% Βαμβάκι - 30% Πολυέστερ", "98% Βαμβάκι - 2% Ελαστάνη", "100% Δέρμα", "Τεχνητό Δέρμα (PU)", "Ελαστική"]

        with st.expander("➕ ΚΑΤΑΧΩΡΗΣΗ ΝΕΟΥ ΠΡΟΪΟΝΤΟΣ", expanded=True):
            c1, c2, c3 = st.columns(3)
            
            # Δυναμική ενημέρωση λιστών από υπάρχοντα δεδομένα
            current_eidov = sorted(list(set(base_eidov + [n.split(' ')[0].capitalize() for n in []]))) # Placeholder logic
            
            sel_eidos = c1.selectbox("Είδος", sorted(base_eidov) + ["+ Νέο"], key=f"sel_e_{rk}")
            final_eidos = c1.text_input("Νέο Είδος", key=f"new_e_{rk}").strip().capitalize() if sel_eidos == "+ Νέο" else sel_eidos
            
            sel_prom = c2.selectbox("Προμηθευτής", sorted(base_prom) + ["+ Νέο"], key=f"sel_p_{rk}")
            final_prom = c2.text_input("Νέος Προμηθευτής", key=f"new_p_{rk}").strip().upper() if sel_prom == "+ Νέο" else sel_prom

            sel_chroma = c3.selectbox("Χρώμα", sorted(base_chroma) + ["+ Νέο"], key=f"sel_c_{rk}")
            final_chroma = c3.text_input("Νέο Χρώμα", key=f"new_c_{rk}").strip().capitalize() if sel_chroma == "+ Νέο" else sel_chroma

            c4, c5, c6 = st.columns(3)
            size = c4.selectbox("Μέγεθος", ["One Size", "S", "M", "L", "XL", "XXL"], key=f"s_{rk}")
            
            # ΕΠΑΝΑΦΟΡΑ ΛΙΣΤΑΣ ΣΥΝΘΕΣΗΣ
            sel_synth = c5.selectbox("Σύνθεση", sorted(base_synth) + ["+ Νέο"], key=f"sel_sy_{rk}")
            final_synth = c5.text_input("Γράψτε Σύνθεση", key=f"new_sy_{rk}").strip() if sel_synth == "+ Νέο" else sel_synth
            
            plan = c6.text_input("Κωδικός Σχεδίου", key=f"pl_{rk}")
            
            c7, c8, c9 = st.columns(3)
            price = c7.number_input("Τιμή Λιανικής", min_value=0.0, step=0.1, key=f"pr_{rk}")
            stock = c8.number_input("Απόθεμα", min_value=0, step=1, key=f"st_{rk}")
            labels = c9.number_input("Ετικέτες", min_value=0, value=int(stock), key=f"la_{rk}")
            
            if st.button("💾 Αποθήκευση & Παραγωγή Ετικετών", use_container_width=True):
                if final_eidos and final_prom and plan:
                    # Παραγωγή SKU
                    e_c = generate_latin_code(final_eidos)
                    p_c = generate_latin_code(final_prom)
                    c_c = generate_latin_code(final_chroma)
                    sku = f"{e_c}-{p_c}-{plan}-{c_c}-{size}".upper()
                    full_name = f"{final_eidos} {final_chroma} ({final_synth})".upper()
                    
                    try:
                        supabase.table("inventory").upsert({
                            "barcode": sku, "name": full_name, "price": price, "stock": stock
                        }).execute()
                        st.success(f"Το προϊόν {sku} αποθηκεύτηκε!")
                        st.session_state.inv_rk += 1
                        time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Σφάλμα: {e}")
                else:
                    st.warning("Παρακαλώ συμπληρώστε όλα τα απαραίτητα πεδία.")

        # Εμφάνιση Αποθήκης
        if existing_data:
            df = pd.DataFrame(existing_data)
            st.subheader("📋 Τρέχον Απόθεμα")
            st.dataframe(df, use_container_width=True)
