import pandas as pd
from datetime import datetime, timedelta
import time
import streamlit as st
from supabase import create_client, Client
import re

# --- 1. CONFIG & SUPABASE ---
st.set_page_config(page_title="CHERRY v14.2.82", layout="wide", page_icon="🍒")

SUPABASE_URL = "https://hnwynihjkdkryrfepenh.supabase.co"
SUPABASE_KEY = "sb_publishable_ualF72lJKgUQA4TzjPQ-OA_zih7zJ-s"

@st.cache_resource
def init_supabase():
    try: return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception: return None

supabase = init_supabase()

# --- 2. ΕΠΑΝΑΦΟΡΑ ΟΛΩΝ ΤΩΝ ΕΠΙΛΟΓΩΝ (MASTER LISTS) ---
if 'master_lists' not in st.session_state:
    st.session_state.master_lists = {
        "Είδη": ["Ζακέτα", "Ζώνη", "Μπλούζα", "Μπουφάν / Παλτό", "Παντελόνι", "Πουκάμισο", "Φόρεμα", "Φούστα"],
        "Προμηθευτές": ["ONADO", "PINUP", "ΡΕΝΑ", "ΣΤΕΛΛΑ", "ΤΖΕΝΗ"],
        "Χρώματα": ["Γκρι", "Εκρού", "Εμπριμέ", "Καφέ", "Κίτρινο", "Κόκκινο", "Λευκό", "Μαύρο", "Μπεζ", "Μπλε", "Πουά", "Πράσινο", "Ριγέ", "Σιέλ"],
        "Συνθέσεις": ["100% Βαμβάκι", "100% Πολυέστερ", "70% Βαμβάκι - 30% Πολυέστερ", "98% Βαμβάκι - 2% Ελαστάνη", "100% Δέρμα", "Τεχνητό Δέρμα (PU)", "Ελαστική"]
    }

# --- HELPERS ---
def get_athens_now(): return datetime.now() + timedelta(hours=2)

def generate_latin_code(text):
    char_map = {'Α':'A','Β':'B','Γ':'G','Δ':'D','Ε':'E','Ζ':'Z','Η':'H','Θ':'TH','Ι':'I','Κ':'K','Λ':'L','Μ':'M','Ν':'N','Ξ':'X','Ο':'O','Π':'P','Ρ':'R','Σ':'S','Τ':'T','Υ':'Y','Φ':'F','Χ':'CH','Ψ':'PS','Ω':'O'}
    text = str(text).upper()
    res = "".join([char_map.get(char, char) for char in text[:3]])
    return res if res else "ITM"

# --- 3. UI STYLE ---
st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: bold; }
    .cart-area { 
        font-family: 'Courier New', monospace; background-color: #000; padding: 15px; 
        border: 3px solid #2ecc71; color: #2ecc71; min-height: 250px; border-radius: 10px;
    }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000 !important; font-weight: bold !important; }
    </style>
    """, unsafe_allow_html=True)

# Session States for POS
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100

def reset_pos():
    st.session_state.cart = []
    st.session_state.selected_cust_id = None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1
    st.session_state.ph_key += 1
    st.rerun()

# --- 4. MAIN LOGIC ---
if not st.session_state.logged_in:
    st.title("🔒 CHERRY LOGIN")
    pwd = st.text_input("Password", type="password")
    if st.button("Είσοδος"):
        if pwd == "CHERRY123":
            st.session_state.logged_in = True
            st.rerun()
else:
    with st.sidebar:
        st.header("🍒 CHERRY v14.2")
        menu = ["🛒 ΤΑΜΕΙΟ", "📦 ΑΠΟΘΗΚΗ", "📊 MANAGER", "👥 ΠΕΛΑΤΕΣ"]
        view = st.radio("Επιλογές", menu)
        if st.button("❌ Έξοδος"): st.session_state.logged_in = False; st.rerun()

    # --- ΤΑΜΕΙΟ ---
    if view == "🛒 ΤΑΜΕΙΟ":
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο Πελάτη", key=f"ph_{st.session_state.ph_key}")
                if ph and len(ph) == 10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data:
                        st.session_state.selected_cust_id = res.data[0]['id']
                        st.session_state.cust_name = res.data[0]['name']
                        st.rerun()
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ"): 
                    st.session_state.selected_cust_id = 0
                    st.rerun()
            else:
                st.subheader(f"👤 {st.session_state.cust_name}")
                bc = st.text_input("Barcode Προϊόντος", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        st.session_state.cart.append({'name': res.data[0]['name'], 'price': float(res.data[0]['price'])})
                        st.session_state.bc_key += 1
                        st.rerun()
                
                if st.session_state.cart:
                    if st.button("💰 ΟΛΟΚΛΗΡΩΣΗ ΠΛΗΡΩΜΗΣ", use_container_width=True):
                        st.success("Η πώληση καταγράφηκε!")
                        time.sleep(1); reset_pos()
                if st.button("🔄 ΑΚΥΡΩΣΗ / ΝΕΟΣ ΠΕΛΑΤΗΣ"): reset_pos()

        with cr:
            st.markdown("<div class='cart-area'>" + "\n".join([f"{i['name'][:30]:30} | {i['price']:.2f}€" for i in st.session_state.cart]) + "</div>", unsafe_allow_html=True)
            total = sum(i['price'] for i in st.session_state.cart)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    # --- ΑΠΟΘΗΚΗ ---
    elif view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Διαχείριση Αποθήκης")
        t1, t2 = st.tabs(["🆕 ΚΑΤΑΧΩΡΗΣΗ", "⚙️ ΡΥΘΜΙΣΕΙΣ ΛΙΣΤΩΝ"])

        with t1:
            with st.form("add_form"):
                c1, c2, c3 = st.columns(3)
                e = c1.selectbox("Είδος", sorted(st.session_state.master_lists["Είδη"]))
                p = c2.selectbox("Προμηθευτής", sorted(st.session_state.master_lists["Προμηθευτές"]))
                c = c3.selectbox("Χρώμα", sorted(st.session_state.master_lists["Χρώματα"]))
                
                c4, c5, c6 = st.columns(3)
                sz = c4.selectbox("Μέγεθος", ["One Size", "S", "M", "L", "XL", "XXL"])
                sy = c5.selectbox("Σύνθεση", sorted(st.session_state.master_lists["Συνθέσεις"]))
                pl = c6.text_input("Κωδικός Σχεδίου")
                
                c7, c8 = st.columns(2)
                pr = c7.number_input("Τιμή Λιανικής", min_value=0.0)
                stk = c8.number_input("Απόθεμα", min_value=0, step=1)
                
                if st.form_submit_button("💾 ΑΠΟΘΗΚΕΥΣΗ"):
                    if pl:
                        sku = f"{generate_latin_code(e)}-{generate_latin_code(p)}-{pl}-{generate_latin_code(c)}-{sz}".upper()
                        full = f"{e.upper()} {c.upper()} ({sy})"
                        supabase.table("inventory").upsert({"barcode": sku, "name": full, "price": pr, "stock": stk}).execute()
                        st.success(f"Αποθηκεύτηκε: {sku}"); time.sleep(1); st.rerun()

        with t2:
            cat = st.selectbox("Επεξεργασία Λίστας:", ["Είδη", "Προμηθευτές", "Χρώματα", "Συνθέσεις"])
            col_a, col_b = st.columns([2, 1])
            with col_a:
                for item in sorted(st.session_state.master_lists[cat]):
                    cx, cy = st.columns([4, 1])
                    cx.text(f"• {item}")
                    if cy.button("🗑️", key=f"d_{item}"):
                        st.session_state.master_lists[cat].remove(item)
                        st.rerun()
            with col_b:
                new_val = st.text_input("Προσθήκη Νέου")
                if st.button("➕ Προσθήκη"):
                    if new_val:
                        st.session_state.master_lists[cat].append(new_val)
                        st.rerun()

        # Stock View
        res = supabase.table("inventory").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data), use_container_width=True)

    # --- MANAGER ---
    elif view == "📊 MANAGER":
        st.title("📊 Στατιστικά & Αναφορές")
        st.info("Εδώ θα εμφανίζονται οι πωλήσεις και τα κέρδη.")

    # --- ΠΕΛΑΤΕΣ ---
    elif view == "👥 ΠΕΛΑΤΕΣ":
        st.title("👥 Διαχείριση Πελατολογίου")
        res = supabase.table("customers").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data), use_container_width=True)
