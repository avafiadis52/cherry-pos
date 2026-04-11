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
    res = ""
    for char in text[:3]:
        res += char_map.get(char, char)
    return res if res else "ITEM"

# --- 3. CONFIG & STYLE (Version v14.2.76) ---
st.set_page_config(page_title="CHERRY v14.2.76", layout="wide", page_icon="🍒")

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

# Session States
keys = ['logged_in', 'cart', 'selected_cust_id', 'cust_name', 'bc_key', 'ph_key', 'mic_key', 'return_mode', 'inv_rk']
default_vals = [False, [], None, "Λιανική Πώληση", 0, 100, 28000, False, 0]
for k, v in zip(keys, default_vals):
    if k not in st.session_state: st.session_state[k] = v

def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart = []
    st.session_state.selected_cust_id = None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1; st.session_state.ph_key += 1
    st.rerun()

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
        st.write(f"📅 {get_athens_now().strftime('%d/%m/%Y %H:%M')}")
        menu = ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📦 ΑΠΟΘΗΚΗ", "📊 MANAGER", "👥 ΠΕΛΑΤΕΣ"]
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
                    if res.data: 
                        st.session_state.selected_cust_id = res.data[0]['id']
                        st.session_state.cust_name = res.data[0]['name']
                        st.rerun()
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ"): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.subheader(f"👤 {st.session_state.cust_name}")
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        p = float(res.data[0]['price'])
                        st.session_state.cart.append({'bc': bc, 'name': res.data[0]['name'], 'price': -p if st.session_state.return_mode else p})
                        st.session_state.bc_key += 1; st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ"): reset_app() # Απλοποιημένο για το παράδειγμα
                if st.button("🔄 ΑΚΥΡΩΣΗ"): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            st.markdown("<div class='cart-area'>" + "\n".join([f"{i['name'][:30]:30} | {i['price']:.2f}€" for i in st.session_state.cart]) + "</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif current_view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Διαχείριση Αποθήκης")
        rk = st.session_state.inv_rk
        
        with st.expander("➕ ΚΑΤΑΧΩΡΗΣΗ ΝΕΟΥ ΠΡΟΪΟΝΤΟΣ", expanded=True):
            c1, c2, c3 = st.columns(3)
            
            # --- ΕΙΔΟΣ ---
            list_eidos = ["Ζακέτα", "Μπλούζα", "Παντελόνι", "Φόρεμα", "Φούστα"]
            sel_eidos = c1.selectbox("Είδος", list_eidos + ["+ Νέο"], key=f"sel_e_{rk}")
            if sel_eidos == "+ Νέο":
                final_eidos = c1.text_input("Πληκτρολογήστε το νέο Είδος", key=f"new_e_{rk}").upper()
            else:
                final_eidos = sel_eidos.upper()
            
            # --- ΠΡΟΜΗΘΕΥΤΗΣ ---
            list_prom = ["ONADO", "PINUP", "ΡΕΝΑ"]
            sel_prom = c2.selectbox("Προμηθευτής", list_prom + ["+ Νέο"], key=f"sel_p_{rk}")
            if sel_prom == "+ Νέο":
                final_prom = c2.text_input("Πληκτρολογήστε τον νέο Προμηθευτή", key=f"new_p_{rk}").upper()
            else:
                final_prom = sel_prom.upper()

            # --- ΧΡΩΜΑ ---
            list_chroma = ["Μαύρο", "Λευκό", "Μπλε", "Κόκκινο", "Πράσινο"]
            sel_chroma = c3.selectbox("Χρώμα", list_chroma + ["+ Νέο"], key=f"sel_c_{rk}")
            if sel_chroma == "+ Νέο":
                final_chroma = c3.text_input("Πληκτρολογήστε το νέο Χρώμα", key=f"new_c_{rk}").upper()
            else:
                final_chroma = sel_chroma.upper()

            c4, c5, c6 = st.columns(3)
            size = c4.selectbox("Μέγεθος", ["One Size", "S", "M", "L", "XL", "XXL"], key=f"s_{rk}")
            synth = c5.text_input("Σύνθεση (π.χ. 100% Cotton)", key=f"sy_{rk}")
            plan = c6.text_input("Κωδικός Σχεδίου (π.χ. 1022)", key=f"pl_{rk}")
            
            c7, c8, c9 = st.columns(3)
            price = c7.number_input("Τιμή Λιανικής", min_value=0.0, step=0.1, key=f"pr_{rk}")
            stock = c8.number_input("Απόθεμα", min_value=0, step=1, key=f"st_{rk}")
            labels = c9.number_input("Ετικέτες προς εκτύπωση", min_value=0, value=int(stock), key=f"la_{rk}")
            
            if st.button("💾 Αποθήκευση & Παραγωγή Ετικετών", use_container_width=True):
                if final_eidos and final_prom and plan:
                    e_code = generate_latin_code(final_eidos)
                    p_code = generate_latin_code(final_prom)
                    c_code = generate_latin_code(final_chroma)
                    sku = f"{e_code}-{p_code}-{plan}-{c_code}-{size}".upper()
                    full_name = f"{final_eidos} {final_chroma} ({synth})".upper()
                    
                    try:
                        supabase.table("inventory").upsert({
                            "barcode": sku, "name": full_name, "price": price, "stock": stock
                        }).execute()
                        st.success(f"Το προϊόν {sku} αποθηκεύτηκε!")
                        st.session_state.inv_rk += 1 # Initialize fields
                        time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Σφάλμα: {e}")
                else:
                    st.warning("Παρακαλώ συμπληρώστε Είδος, Προμηθευτή και Κωδικό Σχεδίου.")

        # Εμφάνιση Λίστας Αποθήκης
        res = supabase.table("inventory").select("*").execute()
        if res.data:
            st.dataframe(pd.DataFrame(res.data), use_container_width=True)
