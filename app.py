import pandas as pd
from datetime import datetime, date, timedelta
import time
import streamlit as st
from supabase import create_client, Client
import re

# --- 1. CONFIG & SUPABASE ---
st.set_page_config(page_title="CHERRY v14.2.80", layout="wide", page_icon="🍒")

SUPABASE_URL = "https://hnwynihjkdkryrfepenh.supabase.co"
SUPABASE_KEY = "sb_publishable_ualF72lJKgUQA4TzjPQ-OA_zih7zJ-s"

@st.cache_resource
def init_supabase():
    try: return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception: return None

supabase = init_supabase()

# --- 2. INITIALIZE PERSISTENT LISTS IN SESSION STATE ---
# Αυτές οι λίστες θα "ζουν" όσο η εφαρμογή είναι ανοιχτή και θα εμπλουτίζονται
if 'list_eidov' not in st.session_state:
    st.session_state.list_eidov = ["Ζακέτα", "Ζώνη", "Μπλούζα", "Μπουφάν / Παλτό", "Παντελόνι", "Πουκάμισο", "Φόρεμα", "Φούστα"]

if 'list_prom' not in st.session_state:
    st.session_state.list_prom = ["ONADO", "PINUP", "ΡΕΝΑ", "ΣΤΕΛΛΑ", "ΤΖΕΝΗ"]

if 'list_chroma' not in st.session_state:
    st.session_state.list_chroma = ["Γκρι", "Εκρού", "Εμπριμέ", "Καφέ", "Κίτρινο", "Κόκκινο", "Λευκό", "Μαύρο", "Μπεζ", "Μπλε", "Πουά", "Πράσινο", "Ριγέ", "Σιέλ"]

if 'list_synth' not in st.session_state:
    st.session_state.list_synth = ["100% Βαμβάκι", "100% Πολυέστερ", "70% Βαμβάκι - 30% Πολυέστερ", "98% Βαμβάκι - 2% Ελαστάνη", "100% Δέρμα", "Τεχνητό Δέρμα (PU)", "Ελαστική"]

if 'inv_rk' not in st.session_state: st.session_state.inv_rk = 0
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

# --- HELPER FOR SKU ---
def generate_latin_code(text):
    char_map = {'Α':'A','Β':'B','Γ':'G','Δ':'D','Ε':'E','Ζ':'Z','Η':'H','Θ':'TH','Ι':'I','Κ':'K','Λ':'L','Μ':'M','Ν':'N','Ξ':'X','Ο':'O','Π':'P','Ρ':'R','Σ':'S','Τ':'T','Υ':'Y','Φ':'F','Χ':'CH','Ψ':'PS','Ω':'O'}
    text = text.upper()
    res = "".join([char_map.get(char, char) for char in text[:3]])
    return res if res else "ITM"

# --- 3. LOGIN & UI ---
if not st.session_state.logged_in:
    st.title("🍒 CHERRY POS - LOGIN")
    pwd = st.text_input("Κωδικός", type="password")
    if st.button("Είσοδος"):
        if pwd == "CHERRY123":
            st.session_state.logged_in = True
            st.rerun()
else:
    view = st.sidebar.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "📦 ΑΠΟΘΗΚΗ"])

    if view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Διαχείριση Αποθήκης")
        rk = st.session_state.inv_rk

        with st.expander("➕ ΚΑΤΑΧΩΡΗΣΗ ΝΕΟΥ ΠΡΟΪΟΝΤΟΣ", expanded=True):
            c1, c2, c3 = st.columns(3)
            
            # ΕΙΔΟΣ
            sel_e = c1.selectbox("Είδος", sorted(st.session_state.list_eidov) + ["+ Νέο"], key=f"sel_e_{rk}")
            if sel_e == "+ Νέο":
                new_val_e = c1.text_input("Πληκτρολογήστε Νέο Είδος", key=f"new_e_{rk}").strip().capitalize()
            else: new_val_e = sel_e

            # ΠΡΟΜΗΘΕΥΤΗΣ
            sel_p = c2.selectbox("Προμηθευτής", sorted(st.session_state.list_prom) + ["+ Νέο"], key=f"sel_p_{rk}")
            if sel_p == "+ Νέο":
                new_val_p = c2.text_input("Πληκτρολογήστε Νέο Προμηθευτή", key=f"new_p_{rk}").strip().upper()
            else: new_val_p = sel_p

            # ΧΡΩΜΑ
            sel_c = c3.selectbox("Χρώμα", sorted(st.session_state.list_chroma) + ["+ Νέο"], key=f"sel_c_{rk}")
            if sel_c == "+ Νέο":
                new_val_c = c3.text_input("Πληκτρολογήστε Νέο Χρώμα", key=f"new_c_{rk}").strip().capitalize()
            else: new_val_c = sel_c

            c4, c5, c6 = st.columns(3)
            size = c4.selectbox("Μέγεθος", ["One Size", "S", "M", "L", "XL", "XXL"], key=f"s_{rk}")
            
            # ΣΥΝΘΕΣΗ
            sel_sy = c5.selectbox("Σύνθεση", sorted(st.session_state.list_synth) + ["+ Νέο"], key=f"sel_sy_{rk}")
            if sel_sy == "+ Νέο":
                new_val_sy = c5.text_input("Πληκτρολογήστε Νέα Σύνθεση", key=f"new_sy_{rk}").strip()
            else: new_val_sy = sel_sy
            
            plan = c6.text_input("Κωδικός Σχεδίου", key=f"pl_{rk}")

            c7, c8 = st.columns(2)
            price = c7.number_input("Τιμή", min_value=0.0, step=0.1, key=f"pr_{rk}")
            stock = c8.number_input("Απόθεμα", min_value=0, step=1, key=f"st_{rk}")

            if st.button("💾 ΟΡΙΣΤΙΚΗ ΑΠΟΘΗΚΕΥΣΗ", use_container_width=True):
                if new_val_e and new_val_p and plan:
                    # 1. ΕΝΗΜΕΡΩΣΗ ΛΙΣΤΩΝ ΣΤΟ SESSION (για να υπάρχουν στην επόμενη καταχώρηση)
                    if new_val_e not in st.session_state.list_eidov:
                        st.session_state.list_eidov.append(new_val_e)
                    if new_val_p not in st.session_state.list_prom:
                        st.session_state.list_prom.append(new_val_p)
                    if new_val_c not in st.session_state.list_chroma:
                        st.session_state.list_chroma.append(new_val_c)
                    if new_val_sy not in st.session_state.list_synth:
                        st.session_state.list_synth.append(new_val_sy)

                    # 2. ΔΗΜΙΟΥΡΓΙΑ SKU & ΟΝΟΜΑΤΟΣ
                    e_code = generate_latin_code(new_val_e)
                    p_code = generate_latin_code(new_val_p)
                    c_code = generate_latin_code(new_val_c)
                    sku = f"{e_code}-{p_code}-{plan}-{c_code}-{size}".upper()
                    full_name = f"{new_val_e.upper()} {new_val_c.upper()} ({new_val_sy})"
                    
                    try:
                        supabase.table("inventory").upsert({
                            "barcode": sku, "name": full_name, "price": price, "stock": stock
                        }).execute()
                        st.success(f"Το προϊόν {sku} αποθηκεύτηκε και οι λίστες ενημερώθηκαν!")
                        # Αυξάνουμε το κλειδί για να καθαρίσουν τα πεδία
                        st.session_state.inv_rk += 1
                        time.sleep(1)
                        st.rerun()
                    except Exception as e: st.error(f"Σφάλμα: {e}")
                else:
                    st.warning("Συμπληρώστε τα υποχρεωτικά πεδία (Είδος, Προμηθευτής, Σχέδιο).")

        # Display Data
        res = supabase.table("inventory").select("*").execute()
        if res.data:
            st.dataframe(pd.DataFrame(res.data), use_container_width=True)
