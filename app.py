import pandas as pd
from datetime import datetime, timedelta
import time
import streamlit as st
from supabase import create_client, Client
import re

# --- 1. CONFIG & SUPABASE ---
st.set_page_config(page_title="CHERRY v14.2.81", layout="wide", page_icon="🍒")

SUPABASE_URL = "https://hnwynihjkdkryrfepenh.supabase.co"
SUPABASE_KEY = "sb_publishable_ualF72lJKgUQA4TzjPQ-OA_zih7zJ-s"

@st.cache_resource
def init_supabase():
    try: return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception: return None

supabase = init_supabase()

# --- 2. ΣΤΑΘΕΡΕΣ ΛΙΣΤΕΣ (BACKUP) ---
if 'master_lists' not in st.session_state:
    st.session_state.master_lists = {
        "Είδη": ["Ζακέτα", "Ζώνη", "Μπλούζα", "Μπουφάν / Παλτό", "Παντελόνι", "Πουκάμισο", "Φόρεμα", "Φούστα"],
        "Προμηθευτές": ["ONADO", "PINUP", "ΡΕΝΑ", "ΣΤΕΛΛΑ", "ΤΖΕΝΗ"],
        "Χρώματα": ["Γκρι", "Εκρού", "Εμπριμέ", "Καφέ", "Κίτρινο", "Κόκκινο", "Λευκό", "Μαύρο", "Μπεζ", "Μπλε", "Πουά", "Πράσινο", "Ριγέ", "Σιέλ"],
        "Συνθέσεις": ["100% Βαμβάκι", "100% Πολυέστερ", "70% Βαμβάκι - 30% Πολυέστερ", "98% Βαμβάκι - 2% Ελαστάνη", "100% Δέρμα", "Τεχνητό Δέρμα (PU)", "Ελαστική"]
    }

# --- HELPERS ---
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
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #333; border-radius: 5px; color: white; }
    .stTabs [aria-selected="true"] { background-color: #2ecc71 !important; }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'inv_rk' not in st.session_state: st.session_state.inv_rk = 0

if not st.session_state.logged_in:
    st.title("🔒 CHERRY LOGIN")
    pwd = st.text_input("Password", type="password")
    if st.button("Είσοδος"):
        if pwd == "CHERRY123":
            st.session_state.logged_in = True
            st.rerun()
else:
    view = st.sidebar.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "📦 ΑΠΟΘΗΚΗ", "📊 MANAGER"])

    if view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Διαχείριση Αποθήκης")
        
        tab1, tab2 = st.tabs(["🆕 ΚΑΤΑΧΩΡΗΣΗ", "⚙️ ΡΥΘΜΙΣΕΙΣ ΛΙΣΤΩΝ"])

        with tab1:
            rk = st.session_state.inv_rk
            with st.form("new_item_form"):
                c1, c2, c3 = st.columns(3)
                eidos = c1.selectbox("Είδος", sorted(st.session_state.master_lists["Είδη"]), key=f"e_{rk}")
                prom = c2.selectbox("Προμηθευτής", sorted(st.session_state.master_lists["Προμηθευτές"]), key=f"p_{rk}")
                chroma = c3.selectbox("Χρώμα", sorted(st.session_state.master_lists["Χρώματα"]), key=f"c_{rk}")

                c4, c5, c6 = st.columns(3)
                size = c4.selectbox("Μέγεθος", ["One Size", "S", "M", "L", "XL", "XXL"], key=f"s_{rk}")
                synth = c5.selectbox("Σύνθεση", sorted(st.session_state.master_lists["Συνθέσεις"]), key=f"sy_{rk}")
                plan = st.text_input("Κωδικός Σχεδίου", key=f"pl_{rk}")

                c7, c8 = st.columns(2)
                price = c7.number_input("Τιμή", min_value=0.0, step=0.1)
                stock = c8.number_input("Απόθεμα", min_value=0, step=1)

                if st.form_submit_button("💾 ΑΠΟΘΗΚΕΥΣΗ ΠΡΟΪΟΝΤΟΣ", use_container_width=True):
                    if plan:
                        sku = f"{generate_latin_code(eidos)}-{generate_latin_code(prom)}-{plan}-{generate_latin_code(chroma)}-{size}".upper()
                        full_name = f"{eidos.upper()} {chroma.upper()} ({synth})"
                        try:
                            supabase.table("inventory").upsert({"barcode": sku, "name": full_name, "price": price, "stock": stock}).execute()
                            st.success(f"Καταχωρήθηκε: {sku}")
                            st.session_state.inv_rk += 1
                            time.sleep(1)
                            st.rerun()
                        except Exception as e: st.error(f"Σφάλμα: {e}")

        with tab2:
            st.subheader("🛠️ Διαχείριση Επιλογών")
            st.info("Εδώ μπορείτε να προσθέσετε, να αλλάξετε ή να διαγράψετε επιλογές από τις λίστες.")
            
            cat = st.selectbox("Επιλέξτε Λίστα για επεξεργασία", ["Είδη", "Προμηθευτές", "Χρώματα", "Συνθέσεις"])
            
            # Εμφάνιση υφιστάμενων με δυνατότητα διαγραφής
            current_list = st.session_state.master_lists[cat]
            
            col_list, col_edit = st.columns([2, 1])
            
            with col_list:
                st.write(f"**Τρέχουσες εγγραφές ({cat}):**")
                to_delete = []
                for idx, item in enumerate(sorted(current_list)):
                    c_left, c_right = st.columns([3, 1])
                    c_left.text(f"• {item}")
                    if c_right.button("🗑️", key=f"del_{cat}_{idx}"):
                        st.session_state.master_lists[cat].remove(item)
                        st.rerun()

            with col_edit:
                st.write("**Προσθήκη Νέου:**")
                new_entry = st.text_input(f"Όνομα νέου {cat}")
                if st.button(f"➕ Προσθήκη στα {cat}"):
                    if new_entry and new_entry not in st.session_state.master_lists[cat]:
                        st.session_state.master_lists[cat].append(new_entry)
                        st.success("Προστέθηκε!")
                        time.sleep(0.5)
                        st.rerun()

        # Πίνακας Αποθήκης στο κάτω μέρος
        res = supabase.table("inventory").select("*").execute()
        if res.data:
            st.subheader("📋 Τρέχον Απόθεμα")
            st.dataframe(pd.DataFrame(res.data), use_container_width=True)

    elif view == "🛒 ΤΑΜΕΙΟ":
        st.title("🛒 Ταμείο")
        st.write("Το ταμείο είναι έτοιμο για χρήση.")
