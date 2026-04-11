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

# --- 3. CONFIG & STYLE ---
st.set_page_config(page_title="CHERRY v14.2.72", layout="wide", page_icon="🍒")

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
        color: #2ecc71; font-size: 16px;
    }
    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; margin-top: 10px; }
    .data-row { font-family: 'Courier New', monospace; background-color: #262626; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; color: white; }
    </style>
    """, unsafe_allow_html=True)

# Helper for SKU generation
def gen_prefix(text):
    """Μετατρέπει τα 3 πρώτα γράμματα σε λατινικούς χαρακτήρες για το SKU"""
    gr_to_lat = {
        'Α': 'A', 'Β': 'B', 'Γ': 'G', 'Δ': 'D', 'Ε': 'E', 'Ζ': 'Z', 'Η': 'H', 'Θ': 'TH', 'Ι': 'I', 
        'Κ': 'K', 'Λ': 'L', 'Μ': 'M', 'Ν': 'N', 'Ξ': 'X', 'Ο': 'O', 'Π': 'P', 'Ρ': 'R', 'Σ': 'S', 
        'Τ': 'T', 'Υ': 'Y', 'Φ': 'F', 'Χ': 'CH', 'Ψ': 'PS', 'Ω': 'O'
    }
    text = text.upper()
    res = ""
    for char in text[:3]:
        res += gr_to_lat.get(char, char)
    return res

# Session States
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'return_mode' not in st.session_state: st.session_state.return_mode = False

# Functions
def get_athens_now(): return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1; st.rerun()

def finalize(disc_val, method):
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = st.session_state.get('manual_ts', get_athens_now()).strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    try:
        for i in st.session_state.cart:
            d = round(i['price'] * ratio, 2)
            f = round(i['price'] - d, 2)
            supabase.table("sales").insert({
                "barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), 
                "discount": float(d), "final_item_price": float(f), "method": str(method), 
                "s_date": ts, "cust_id": c_id
            }).execute()
            if i['bc'] != 'VOICE':
                res_inv = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
                if res_inv.data:
                    new_stock = int(res_inv.data[0]['stock']) + (1 if i['price'] < 0 else -1)
                    supabase.table("inventory").update({"stock": new_stock}).eq("barcode", i['bc']).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); time.sleep(1.5); reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    opt = st.radio("Εκπτωση;", ["ΟΧΙ", "ΝΑΙ"], horizontal=True)
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή %")
        if inp:
            try:
                disc = round((float(inp.replace("%",""))/100 * total), 2) if "%" in inp else round(float(inp), 2)
            except: st.error("Λάθος μορφή")
    st.markdown(f"<div style='font-size:30px; color:red; text-align:center;'>ΠΛΗΡΩΤΕΟ: {total-disc:.2f}€</div>", unsafe_allow_html=True)
    if st.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if st.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

# Main Logic
if not st.session_state.logged_in:
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if pwd == "CHERRY123": st.session_state.logged_in = True; st.rerun()
else:
    with st.sidebar:
        st.session_state.manual_ts = datetime.combine(st.date_input("Ημερομηνία"), st.time_input("Ώρα"))
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        if st.button("❌ Έξοδος"): st.session_state.logged_in = False; st.rerun()

    current_view = "🛒 ΤΑΜΕΙΟ" if view == "🔄 ΕΠΙΣΤΡΟΦΗ" else view

    if current_view == "🛒 ΤΑΜΕΙΟ":
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"ph_{st.session_state.ph_key}")
                if len(ph) == 10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ"): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        price = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'bc': bc, 'name': res.data[0]['name'], 'price': price})
                        st.session_state.bc_key += 1; st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ"): payment_popup()

        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            st.markdown(f"<div class='cart-area'>{'Είδος':45} | Τιμή\n{'-'*56}\n" + 
                        "\n".join([f"{i['name'][:45]:45} | {i['price']:.2f}€" for i in st.session_state.cart]) + "</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif current_view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Διαχείριση Αποθήκης")
        
        # Αρχικές Λίστες
        list_eidov = {"Ζακέτα":"ZAK", "Ζώνη":"ZON", "Μπλούζα":"MPL", "Μπουφάν / Παλτό":"MOU", "Παντελόνι":"PAN", "Πουκάμισο":"POU", "Φόρεμα":"FOR", "Φούστα":"FOU"}
        list_prom = {"ONADO":"ONA", "PINUP":"PIN", "ΡΕΝΑ":"REN", "ΣΤΕΛΛΑ":"STE", "ΤΖΕΝΗ":"TZE"}
        list_chroma = {"Γκρι":"GRA", "Εκρού":"EKR", "Εμπριμέ":"EMP", "Καφέ":"KAF", "Κίτρινο":"YEL", "Κόκκινο":"RED", "Λευκό":"WHT", "Μαύρο":"BLK", "Μπεζ":"BEI", "Μπλε":"BLU", "Πράσινο":"GRN"}
        
        with st.expander("➕ ΚΑΤΑΧΩΡΗΣΗ ΝΕΟΥ ΠΡΟΪΟΝΤΟΣ", expanded=True):
            c1, c2, c3 = st.columns(3)
            
            # --- ΕΙΔΟΣ ---
            with c1:
                eidos_opts = sorted(list(list_eidov.keys())) + ["+ Προσθήκη Νέου"]
                sel_eidos = st.selectbox("Είδος", eidos_opts)
                if sel_eidos == "+ Προσθήκη Νέου":
                    new_e = st.text_input("Όνομα Νέου Είδους")
                    final_eidos = new_e.upper()
                    e_code = gen_prefix(new_e)
                else:
                    final_eidos = sel_eidos
                    e_code = list_eidov[sel_eidos]

            # --- ΠΡΟΜΗΘΕΥΤΗΣ ---
            with c2:
                prom_opts = sorted(list(list_prom.keys())) + ["+ Προσθήκη Νέου"]
                sel_prom = st.selectbox("Προμηθευτής", prom_opts)
                if sel_prom == "+ Προσθήκη Νέου":
                    new_p = st.text_input("Όνομα Νέου Προμηθευτή")
                    final_prom = new_p.upper()
                    p_code = gen_prefix(new_p)
                else:
                    final_prom = sel_prom
                    p_code = list_prom[sel_prom]

            # --- ΧΡΩΜΑ ---
            with c3:
                chr_opts = sorted(list(list_chroma.keys())) + ["+ Προσθήκη Νέου"]
                sel_chr = st.selectbox("Χρώμα", chr_opts)
                if sel_chr == "+ Προσθήκη Νέου":
                    new_c = st.text_input("Νέο Χρώμα")
                    final_chr = new_c.upper()
                    c_code = gen_prefix(new_c)
                else:
                    final_chr = sel_chr
                    c_code = list_chroma[sel_chr]

            c4, c5, c6 = st.columns(3)
            size = c4.selectbox("Μέγεθος", ["One Size", "S", "M", "L", "XL", "XXL"])
            synth = c5.selectbox("Σύνθεση", ["100% Βαμβάκι", "100% Πολυέστερ", "Ελαστική", "+ Προσθήκη Νέου"])
            if synth == "+ Προσθήκη Νέου": synth = st.text_input("Νέα Σύνθεση")
            design = c6.text_input("Κωδικός Σχεδίου (π.χ. 001)")

            c7, c8 = st.columns(2)
            price = c7.number_input("Τιμή (€)", min_value=0.0)
            stock = c8.number_input("Απόθεμα", min_value=0)

            if design:
                sku = f"{e_code}-{p_code}-{design}-{c_code}-{size}".upper()
                name = f"{final_eidos} - {final_chr} ({synth})"
                st.info(f"🏷️ SKU: {sku} | Όνομα: {name}")
                if st.button("💾 Αποθήκευση"):
                    supabase.table("inventory").upsert({"barcode": sku, "name": name, "price": price, "stock": stock}).execute()
                    st.success("Αποθηκεύτηκε!"); time.sleep(1); st.rerun()

        # Λίστα Αποθέματος
        res = supabase.table("inventory").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data).sort_values('name')
            for _, r in df.iterrows():
                col1, col2 = st.columns([5, 1])
                col1.markdown(f"<div class='data-row'>📦 {r['barcode']} | {r['name']} | {r['price']:.2f}€ | Stock: {r['stock']}</div>", unsafe_allow_html=True)
                if col2.button("❌", key=f"del_{r['barcode']}"):
                    supabase.table("inventory").delete().eq("barcode", r['barcode']).execute(); st.rerun()
