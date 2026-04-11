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
st.set_page_config(page_title="CHERRY v14.2.82", layout="wide", page_icon="🍒")

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

    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; margin-top: 10px; text-shadow: 2px 2px 10px rgba(46, 204, 113, 0.5); }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; padding: 10px; border-radius: 10px; background-color: #fff3f0; border: 2px solid #e44d26; }
    
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; font-weight: bold !important; border: 1px solid #808080 !important; }
    
    .data-row { font-family: 'Courier New', monospace; background-color: #262626; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; display: block; white-space: pre; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    .report-stat { background-color: #262730; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; }
    .day-header { background-color: #34495e; color: #f1c40f; padding: 10px; border-radius: 5px; margin-top: 25px; margin-bottom: 10px; font-weight: bold; border-left: 8px solid #f1c40f; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'mic_key' not in st.session_state: st.session_state.mic_key = 28000
if 'return_mode' not in st.session_state: st.session_state.return_mode = False
if 'inv_rk' not in st.session_state: st.session_state.inv_rk = 0

# Επαναφορά Master Lists
if 'master_lists' not in st.session_state:
    st.session_state.master_lists = {
        "Είδη": ["Ζακέτα", "Ζώνη", "Μπλούζα", "Μπουφάν / Παλτό", "Παντελόνι", "Πουκάμισο", "Φόρεμα", "Φούστα"],
        "Προμηθευτές": ["ONADO", "PINUP", "ΡΕΝΑ", "ΣΤΕΛΛΑ", "ΤΖΕΝΗ"],
        "Χρώματα": ["Γκρι", "Εκρού", "Εμπριμέ", "Καφέ", "Κίτρινο", "Κόκκινο", "Λευκό", "Μαύρο", "Μπεζ", "Μπλε", "Πουά", "Πράσινο", "Ριγέ", "Σιέλ"],
        "Συνθέσεις": ["100% Βαμβάκι", "100% Πολυέστερ", "70% Βαμβάκι - 30% Πολυέστερ", "98% Βαμβάκι - 2% Ελαστάνη", "100% Δέρμα", "Τεχνητό Δέρμα (PU)", "Ελαστική"]
    }

# --- 5. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.return_mode = False
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1
    st.rerun()

def generate_latin_code(text):
    char_map = {'Α':'A','Β':'B','Γ':'G','Δ':'D','Ε':'E','Ζ':'Z','Η':'H','Θ':'TH','Ι':'I','Κ':'K','Λ':'L','Μ':'M','Ν':'N','Ξ':'X','Ο':'O','Π':'P','Ρ':'R','Σ':'S','Τ':'T','Υ':'Y','Φ':'F','Χ':'CH','Ψ':'PS','Ω':'O'}
    text = str(text).upper()
    res = "".join([char_map.get(char, char) for char in text[:3]])
    return res if res else "ITM"

def speak_text(text_to_say, play_beep=True):
    beep_js = "var context = new (window.AudioContext || window.webkitAudioContext)(); var osc = context.createOscillator(); osc.type = 'sawtooth'; osc.frequency.setValueAtTime(150, context.currentTime); osc.connect(context.destination); osc.start(); osc.stop(context.currentTime + 0.2);" if play_beep else ""
    speech_js = "var msg = new SpeechSynthesisUtterance('{}'); msg.lang = 'el-GR'; window.speechSynthesis.speak(msg);".format(text_to_say) if text_to_say else ""
    st.components.v1.html("<script>{}{}</script>".format(beep_js, speech_js), height=0)

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
        time.sleep(1.5); reset_app()
    except Exception as e: st.error("Σφάλμα: {}".format(e))

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown("<h3 style='text-align:center;'>Σύνολο: {:.2f}€</h3>".format(total), unsafe_allow_html=True)
    st.write("Θέλετε έκπτωση;")
    opt = st.radio("Επιλογή", ["ΟΧΙ", "ΝΑΙ"], horizontal=True, label_visibility="collapsed")
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή ποσοστό %", placeholder="π.χ. 5 ή 10%")
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

# --- 6. MAIN ROUTING ---
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<h1 style='text-align:center;'>🔒 CHERRY LOGIN</h1>", unsafe_allow_html=True)
        pwd = st.text_input("Password", type="password")
        if st.button("Είσοδος", use_container_width=True):
            if pwd == "CHERRY123":
                st.session_state.logged_in = True
                st.rerun()
else:
    with st.sidebar:
        st.markdown("<div class='sidebar-date'>{}</div>".format(get_athens_now().strftime('%d/%m/%Y %H:%M')), unsafe_allow_html=True)
        menu_options = ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ", "⚙️ SYSTEM"]
        view = st.radio("Μενού", menu_options, key="sidebar_nav")
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        current_view = view if view != "🔄 ΕΠΙΣΤΡΟΦΗ" else "🛒 ΤΑΜΕΙΟ"
        if st.button("❌ Έξοδος / Κλείδωμα", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

    # --- ΤΑΜΕΙΟ VIEW ---
    if current_view == "🛒 ΤΑΜΕΙΟ":
        st.markdown("<div class='status-header'>Πελάτης: {}</div>".format(st.session_state.cust_name), unsafe_allow_html=True)
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο (10 ψηφία)", key=f"ph_{st.session_state.ph_key}")
                if ph and len(ph) == 10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                    else: new_customer_popup(ph)
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        val = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'bc': bc, 'name': res.data[0]['name'], 'price': val})
                        st.session_state.bc_key += 1; st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
                if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            lines = ["{:45} | {:>4.2f}€".format(i['name'][:45], i['price']) for i in st.session_state.cart]
            st.markdown("<div class='cart-area'>{:45} | {:>4}\n{}\n{}</div>".format('Είδος', 'Τιμή', '-'*56, '\n'.join(lines)), unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    # --- NEW ΑΠΟΘΗΚΗ MODULE ---
    elif current_view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Διαχείριση Αποθήκης")
        t1, t2 = st.tabs(["🆕 ΚΑΤΑΧΩΡΗΣΗ", "⚙️ ΡΥΘΜΙΣΕΙΣ ΛΙΣΤΩΝ"])

        with t1:
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
                            time.sleep(1); st.rerun()
                        except Exception as ex: st.error(f"Σφάλμα: {ex}")
                    else: st.warning("Ο κωδικός σχεδίου είναι υποχρεωτικός.")

        with t2:
            st.subheader("🛠️ Διαχείριση Επιλογών")
            cat = st.selectbox("Επιλέξτε Λίστα για επεξεργασία", ["Είδη", "Προμηθευτές", "Χρώματα", "Συνθέσεις"])
            col_list, col_edit = st.columns([2, 1])
            with col_list:
                st.write(f"**Τρέχουσες εγγραφές ({cat}):**")
                for item in sorted(st.session_state.master_lists[cat]):
                    cx, cy = st.columns([4, 1])
                    cx.text(f"• {item}")
                    if cy.button("🗑️", key=f"del_{cat}_{item}"):
                        st.session_state.master_lists[cat].remove(item)
                        st.rerun()
            with col_edit:
                new_entry = st.text_input(f"Όνομα νέου {cat}")
                if st.button(f"➕ Προσθήκη"):
                    if new_entry and new_entry not in st.session_state.master_lists[cat]:
                        st.session_state.master_lists[cat].append(new_entry)
                        st.rerun()

        res = supabase.table("inventory").select("*").execute()
        if res.data:
            st.subheader("📋 Τρέχον Απόθεμα")
            st.dataframe(pd.DataFrame(res.data).sort_values(by='name'), use_container_width=True, hide_index=True)

    # --- ΛΟΙΠΑ MODULES (MANAGER, ΠΕΛΑΤΕΣ, SYSTEM) ---
    elif current_view == "📊 MANAGER":
        st.title("📊 Στατιστικά")
        # ... (Ο κώδικας του Manager που υπήρχε ήδη)
        st.info("Ενότητα Αναφορών")

    elif current_view == "👥 ΠΕΛΑΤΕΣ":
        st.title("👥 Πελατολόγιο")
        res = supabase.table("customers").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data), use_container_width=True)

    elif current_view == "⚙️ SYSTEM":
        st.title("⚙️ Ρυθμίσεις")
        # ... (Ο κώδικας του System)
