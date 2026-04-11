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
    try: return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception: return None

supabase = init_supabase()

# --- 3. CONFIG & STYLE ---
st.set_page_config(page_title="CHERRY v14.3.8", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    .report-card { padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 10px; box-shadow: 2px 2px 10px rgba(0,0,0,0.5); }
    .cash-card { background-color: #27ae60; color: white; border: 2px solid #2ecc71; }
    .card-card { background-color: #2980b9; color: white; border: 2px solid #3498db; }
    .total-card { background-color: #8e44ad; color: white; border: 2px solid #9b59b6; }
    .cart-item-row { 
        background-color: #000; padding: 10px; border-radius: 5px; margin-bottom: 5px; 
        border: 1px solid #2ecc71; display: flex; justify-content: space-between; align-items: center;
        font-family: 'Courier New', monospace; color: #2ecc71; font-size: 15px;
    }
    .total-label { font-size: 80px; font-weight: bold; color: #2ecc71; text-align: center; line-height: 1; }
    .data-row { font-family: 'Courier New', monospace; background-color: #262626; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; white-space: pre; font-size: 14px; display: block; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000 !important; font-weight: bold !important; border-radius: 8px !important; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'mic_key' not in st.session_state: st.session_state.mic_key = 28000
if 'return_mode' not in st.session_state: st.session_state.return_mode = False

if 'master_lists' not in st.session_state:
    st.session_state.master_lists = {
        "Είδη": ["Ζακέτα", "Ζώνη", "Μπλούζα", "Μπουφάν / Παλτό", "Παντελόνι", "Πουκάμισο", "Φόρεμα", "Φούστα"],
        "Προμηθευτές": ["ONADO", "PINUP", "ΡΕΝΑ", "ΣΤΕΛΛΑ", "ΤΖΕΝΗ"],
        "Χρώματα": ["Γκρι", "Εκρού", "Εμπριμέ", "Καφέ", "Κίτρινο", "Κόκκινο", "Λευκό", "Μαύρο", "Μπεζ", "Μπλε", "Πουά", "Πράσινο", "Ριγέ", "Σιέλ"],
        "Συνθέσεις": ["100% Βαμβάκι", "100% Πολυέστερ", "70% Βαμβάκι - 30% Πολυέστερ", "98% Βαμβάκι - 2% Ελαστάνη", "100% Δέρμα", "Τεχνητό Δέρμα (PU)"]
    }

# --- 5. HELPERS ---
def get_athens_now(): return datetime.now() + timedelta(hours=2)

def generate_latin_code(text):
    char_map = {'Α':'A','Β':'B','Γ':'G','Δ':'D','Ε':'E','Ζ':'Z','Η':'H','Θ':'TH','Ι':'I','Κ':'K','Λ':'L','Μ':'M','Ν':'N','Ξ':'X','Ο':'O','Π':'P','Ρ':'R','Σ':'S','Τ':'T','Υ':'Y','Φ':'F','Χ':'CH','Ψ':'PS','Ω':'O'}
    return "".join([char_map.get(c, c) for c in str(text).upper()[:3]])

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1; st.rerun()

# --- 6. DIALOGS ---
@st.dialog("🏷️ ΕΚΤΥΠΩΣΗ ΕΤΙΚΕΤΩΝ")
def print_label_popup(name, barcode, price):
    st.markdown(f"<div style='background:white; color:black; padding:15px; border:3px solid black; text-align:center;'><h2>CHERRY</h2><hr><b>{name}</b><br>CODE: {barcode}<h1>{price:.2f} €</h1></div>", unsafe_allow_html=True)
    copies = st.number_input("Ποσότητα ετικετών", min_value=1, max_value=100, value=1)
    if st.button(f"🖨️ ΕΚΤΥΠΩΣΗ ({copies})", use_container_width=True):
        st.success(f"Εκτυπώθηκαν {copies} ετικέτες!"); time.sleep(1); st.rerun()

def finalize(disc_val, method):
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = st.session_state.get('manual_ts', get_athens_now()).strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    for i in st.session_state.cart:
        d, f = round(i['price'] * ratio, 2), round(i['price'] - (i['price'] * ratio), 2)
        supabase.table("sales").insert({"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": float(d), "final_item_price": float(f), "method": method, "s_date": ts, "cust_id": c_id}).execute()
        if i['bc'] != 'VOICE':
            res = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
            if res.data:
                new_stk = int(res.data[0]['stock']) + (1 if i['price'] < 0 else -1)
                supabase.table("inventory").update({"stock": new_stk}).eq("barcode", i['bc']).execute()
    st.success("✅ ΟΛΟΚΛΗΡΩΘΗΚΕ"); reset_app()

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    disc_inp = st.text_input("Έκπτωση (π.χ. 5 ή 10%)", value="0")
    disc = 0.0
    try:
        if "%" in disc_inp: disc = round((float(disc_inp.replace("%",""))/100 * total), 2)
        else: disc = round(float(disc_inp), 2)
    except: pass
    st.markdown(f"<div style='font-size:40px; font-weight:bold; color:#e44d26; text-align:center; padding:10px; background-color:#fff3f0; border-radius:10px;'>ΠΛΗΡΩΤΕΟ: {total-disc:.2f}€</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

# --- 7. MAIN INTERFACE ---
if not st.session_state.logged_in:
    c2 = st.columns([1,1,1])[1]
    with c2:
        st.title("🔒 LOGIN")
        if st.text_input("Password", type="password") == "CHERRY123" and st.button("Είσοδος"):
            st.session_state.logged_in = True; st.rerun()
else:
    with st.sidebar:
        ts_now = get_athens_now()
        chosen_date = st.date_input("Ημερομηνία", value=ts_now.date())
        chosen_time = st.time_input("Ώρα", value=ts_now.time())
        st.session_state.manual_ts = datetime.combine(chosen_date, chosen_time)
        
        if HAS_MIC:
            text = speech_to_text(language='el', start_prompt="🎙️ ΦΩΝΗΤΙΚΗ ΠΩΛΗΣΗ", key=f"mic_{st.session_state.mic_key}")
            if text:
                numbers = re.findall(r"[-+]?\d*\.\d+|\d+", text)
                if numbers:
                    price = float(numbers[0])
                    desc = text.replace(str(numbers[0]), "").strip().upper()
                    if not desc: desc = "ΦΩΝΗΤΙΚΗ ΚΑΤΑΧΩΡΗΣΗ"
                    final_p = -price if st.session_state.return_mode else price
                    st.session_state.cart.append({'id': str(time.time()), 'bc': 'VOICE', 'name': desc, 'price': final_p})
                    st.session_state.mic_key += 1; st.rerun()
        
        st.divider()
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ", "⚙️ SYSTEM"])
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        if st.button("❌ Έξοδος"): st.session_state.logged_in = False; st.rerun()

    # --- ΤΑΜΕΙΟ / ΕΠΙΣΤΡΟΦΗ ---
    if view in ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ"]:
        st.subheader(f"👤 {st.session_state.cust_name}")
        cl, cr = st.columns([1, 1.4])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"ph_{st.session_state.ph_key}")
                if len(ph) == 10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button("👤 Αλλαγή Πελάτη", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}))
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        val = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'id': str(time.time()), 'bc': bc, 'name': res.data[0]['name'], 'price': val})
                        st.session_state.bc_key += 1; st.rerun()
                if st.session_state.cart:
                    if st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
                if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            st.markdown("### 🛒 Καλάθι")
            for i, item in enumerate(st.session_state.cart):
                c_i, c_d = st.columns([5, 1])
                c_i.markdown(f"<div class='cart-item-row'><span>{item['name'][:30]}</span><b>{item['price']:.2f}€</b></div>", unsafe_allow_html=True)
                if c_d.button("❌", key=f"del_{item.get('id', i)}_{i}"): st.session_state.cart.pop(i); st.rerun()
            total = sum(i['price'] for i in st.session_state.cart)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    # --- MANAGER (ΠΡΑΞΕΙΣ) ---
    elif view == "📊 MANAGER":
        st.title("📊 ΑΝΑΦΟΡΕΣ")
        if st.text_input("Κωδικός", type="password") == "999":
            res_s = supabase.table("sales").select("*").execute()
            if res_s.data:
                df = pd.DataFrame(res_s.data)
                df['ΗΜΕΡΟΜΗΝΙΑ'] = pd.to_datetime(df['s_date']).dt.date
                today = st.session_state.manual_ts.date()
                tdf = df[df['ΗΜΕΡΟΜΗΝΙΑ'] == today]
                
                st.subheader("📋 ΠΡΑΞΕΙΣ ΗΜΕΡΑΣ")
                cash = tdf[tdf['method'] == 'Μετρητά']['final_item_price'].sum()
                card = tdf[tdf['method'] == 'Κάρτα']['final_item_price'].sum()
                m1, m2, m3 = st.columns(3)
                m1.markdown(f"<div class='report-card cash-card'><h3>💵 ΜΕΤΡΗΤΑ</h3><h1>{cash:.2f}€</h1></div>", unsafe_allow_html=True)
                m2.markdown(f"<div class='report-card card-card'><h3>💳 ΚΑΡΤΑ</h3><h1>{card:.2f}€</h1></div>", unsafe_allow_html=True)
                m3.markdown(f"<div class='report-card total-card'><h3>ΣΥΝΟΛΟ</h3><h1>{cash+card:.2f}€</h1></div>", unsafe_allow_html=True)
                
                st.divider()
                st.subheader("🕒 Αναλυτικές Συναλλαγές")
                st.dataframe(tdf[['s_date', 'item_name', 'final_item_price', 'method']], use_container_width=True)

    # --- NEW UPDATED ΑΠΟΘΗΚΗ MODULE ---
    elif view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 ΔΙΑΧΕΙΡΙΣΗ ΑΠΟΘΗΚΗΣ")
        tab1, tab2, tab3 = st.tabs(["🆕 ΚΑΤΑΧΩΡΗΣΗ", "⚙️ ΡΥΘΜΙΣΕΙΣ ΛΙΣΤΩΝ", "📋 ΑΠΟΘΕΜΑ"])
        
        with tab1:
            with st.form("inv_form", clear_on_submit=True):
                c1,c2,c3 = st.columns(3)
                e = c1.selectbox("Είδος", sorted(st.session_state.master_lists["Είδη"]))
                p = c2.selectbox("Προμηθευτής", sorted(st.session_state.master_lists["Προμηθευτές"]))
                c = c3.selectbox("Χρώμα", sorted(st.session_state.master_lists["Χρώματα"]))
                
                c4,c5,c6 = st.columns(3)
                sz = c4.selectbox("Μέγεθος", ["One Size", "S", "M", "L", "XL", "XXL", "36", "38", "40", "42", "44", "46"])
                sy = c5.selectbox("Σύνθεση", sorted(st.session_state.master_lists["Συνθέσεις"]))
                pl = c6.text_input("Σχέδιο (π.χ. 1022)")
                
                c7, c8 = st.columns(2)
                pr = c7.number_input("Τιμή Πώλησης (€)", min_value=0.0, step=0.1)
                stk = c8.number_input("Απόθεμα (Stock)", min_value=0, value=1)
                
                if st.form_submit_button("💾 ΑΠΟΘΗΚΕΥΣΗ"):
                    if pl:
                        sku = f"{generate_latin_code(e)}-{generate_latin_code(p)}-{pl}-{generate_latin_code(c)}-{sz}".upper()
                        supabase.table("inventory").upsert({"barcode": sku, "name": f"{e} {c} ({sy})".upper(), "price": pr, "stock": stk}).execute()
                        st.success(f"Καταχωρήθηκε επιτυχώς: {sku}")
                    else:
                        st.error("Πρέπει να συμπληρώσετε το Σχέδιο!")

        with tab2:
            st.subheader("⚙️ Διαχείριση Λιστών")
            cat = st.selectbox("Επιλογή Λίστας προς επεξεργασία", ["Είδη", "Προμηθευτές", "Χρώματα", "Συνθέσεις"])
            
            # Εμφάνιση υπαρχόντων με δυνατότητα διαγραφής
            st.write(f"Τρέχοντα στοιχεία στην κατηγορία **{cat}**:")
            for item in sorted(st.session_state.master_lists[cat]):
                col_a, col_b = st.columns([4, 1])
                col_a.text(item)
                if col_b.button("🗑️", key=f"del_list_{cat}_{item}"):
                    st.session_state.master_lists[cat].remove(item)
                    st.rerun()
            
            st.divider()
            new_val = st.text_input(f"Προσθήκη νέου στοιχείου στα {cat}")
            if st.button("➕ Προσθήκη"):
                if new_val and new_val not in st.session_state.master_lists[cat]:
                    st.session_state.master_lists[cat].append(new_val)
                    st.success("Προστέθηκε!")
                    st.rerun()

        with tab3:
            st.subheader("📋 Τρέχον Απόθεμα")
            res = supabase.table("inventory").select("*").execute()
            if res.data:
                # Αναζήτηση στην αποθήκη
                search = st.text_input("🔍 Αναζήτηση με Barcode ή Όνομα")
                filtered_data = [r for r in res.data if search.upper() in r['barcode'].upper() or search.upper() in r['name'].upper()]
                
                for r in sorted(filtered_data, key=lambda x: x['name']):
                    c1, c2, c3 = st.columns([5,1,1])
                    stk_color = "#2ecc71" if r['stock'] > 0 else "#e74c3c"
                    c1.markdown(f"<div class='data-row'>📦 {r['barcode']} | <b>{r['name']}</b> | {r['price']}€ | Stock: <span style='color:{stk_color}'>{r['stock']}</span></div>", unsafe_allow_html=True)
                    if c2.button("🏷️", key=f"print_inv_{r['barcode']}"):
                        print_label_popup(r['name'], r['barcode'], r['price'])
                    if c3.button("🗑️", key=f"del_inv_{r['barcode']}"):
                        if st.warning(f"Διαγραφή του {r['barcode']};"):
                            supabase.table("inventory").delete().eq("barcode", r['barcode']).execute()
                            st.rerun()
            else:
                st.info("Η αποθήκη είναι άδεια.")

    elif view == "👥 ΠΕΛΑΤΕΣ":
        st.title("👥 ΠΕΛΑΤΟΛΟΓΙΟ")
        res = supabase.table("customers").select("*").execute()
        if res.data:
            df_cust = pd.DataFrame(res.data)
            st.dataframe(df_cust[['name', 'phone', 'id']], use_container_width=True)

    elif view == "⚙️ SYSTEM":
        st.title("⚙️ SYSTEM ADMIN")
        if st.text_input("Κωδικός Πρόσβασης", type="password") == "999":
            target = st.selectbox("Πίνακας για Εκκαθάριση", ["sales", "customers", "inventory"])
            if st.text_input("Γράψτε τη λέξη ΔΙΑΓΡΑΦΗ για επιβεβαίωση") == "ΔΙΑΓΡΑΦΗ":
                if st.button("🔥 ΟΡΙΣΤΙΚΗ ΕΚΚΑΘΑΡΙΣΗ"):
                    supabase.table(target).delete().neq("id", -1).execute()
                    st.success(f"Ο πίνακας {target} καθαρίστηκε.")
                    st.rerun()
