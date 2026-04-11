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
st.set_page_config(page_title="CHERRY v14.2.90", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; }
    .cart-area { 
        font-family: 'Courier New', monospace; background-color: #000; padding: 15px; border-radius: 10px; 
        white-space: pre; border: 4px solid #2ecc71 !important; color: #2ecc71; min-height: 300px; font-size: 16px;
    }
    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; text-shadow: 2px 2px 10px rgba(46, 204, 113, 0.5); }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; padding: 10px; background-color: #fff3f0; border: 2px solid #e44d26; border-radius: 10px; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000 !important; font-weight: bold !important; border-radius: 8px !important; }
    .data-row { font-family: 'Courier New', monospace; background-color: #262626; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; display: block; white-space: pre; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. SESSION STATE & MASTER LISTS ---
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
        "Συνθέσεις": ["100% Βαμβάκι", "100% Πολυέστερ", "70% Βαμβάκι - 30% Πολυέστερ", "98% Βαμβάκι - 2% Ελαστάνη", "100% Δέρμα", "Τεχνητό Δέρμα (PU)", "Ελαστική"]
    }

# --- 5. HELPER FUNCTIONS ---
def get_athens_now(): return datetime.now() + timedelta(hours=2)

def generate_latin_code(text):
    char_map = {'Α':'A','Β':'B','Γ':'G','Δ':'D','Ε':'E','Ζ':'Z','Η':'H','Θ':'TH','Ι':'I','Κ':'K','Λ':'L','Μ':'M','Ν':'N','Ξ':'X','Ο':'O','Π':'P','Ρ':'R','Σ':'S','Τ':'T','Υ':'Y','Φ':'F','Χ':'CH','Ψ':'PS','Ω':'O'}
    return "".join([char_map.get(c, c) for c in str(text).upper()[:3]])

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.return_mode = False
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1
    st.rerun()

def speak_text(text):
    js = f"var m = new SpeechSynthesisUtterance('{text}'); m.lang = 'el-GR'; window.speechSynthesis.speak(m);"
    st.components.v1.html(f"<script>{js}</script>", height=0)

# --- 6. DIALOGS ---
@st.dialog("👤 Νέος Πελάτης")
def new_customer_popup(phone):
    st.write(f"Το τηλέφωνο **{phone}** είναι νέο.")
    name = st.text_input("Ονοματεπώνυμο")
    if st.button("Αποθήκευση", use_container_width=True) and name:
        res = supabase.table("customers").insert({"name": name.upper(), "phone": phone}).execute()
        if res.data:
            st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']
            st.rerun()

def finalize(disc_val, method):
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = st.session_state.get('manual_ts', get_athens_now()).strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    
    for i in st.session_state.cart:
        d = round(i['price'] * ratio, 2)
        f = round(i['price'] - d, 2)
        supabase.table("sales").insert({
            "barcode": str(i['bc']), "item_name": str(i['name']), 
            "unit_price": float(i['price']), "discount": float(d), 
            "final_item_price": float(f), "method": method, 
            "s_date": ts, "cust_id": c_id
        }).execute()
        
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
    st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {total-disc:.2f}€</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

# --- 7. MAIN INTERFACE ---
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.title("🔒 CHERRY LOGIN")
        pwd = st.text_input("Password", type="password")
        if st.button("Είσοδος", use_container_width=True):
            if pwd == "CHERRY123":
                st.session_state.logged_in = True; st.rerun()
            else: st.error("Λάθος κωδικός")
else:
    with st.sidebar:
        current_athens = get_athens_now()
        chosen_date = st.date_input("Ημερομηνία", value=current_athens.date())
        chosen_time = st.time_input("Ώρα", value=current_athens.time())
        st.session_state.manual_ts = datetime.combine(chosen_date, chosen_time)
        
        st.markdown(f"<div class='sidebar-date'>{st.session_state.manual_ts.strftime('%d/%m/%Y %H:%M')}</div>", unsafe_allow_html=True)
        
        if HAS_MIC:
            voice = speech_to_text(language='el', start_prompt="🎙️ ΦΩΝΗΤΙΚΗ ΠΩΛΗΣΗ", key=f"mic_{st.session_state.mic_key}")
            if voice:
                nums = re.findall(r"\d+", voice)
                if nums:
                    p = float(nums[0])
                    st.session_state.cart.append({'bc': 'VOICE', 'name': voice.upper(), 'price': -p if st.session_state.return_mode else p})
                    st.session_state.mic_key += 1; st.rerun()

        st.divider()
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ", "📊 MANAGER"])
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        
        if st.button("❌ Έξοδος"): 
            st.session_state.logged_in = False; st.rerun()

    # --- VIEW ROUTING ---
    
    # 🛒 ΤΑΜΕΙΟ & 🔄 ΕΠΙΣΤΡΟΦΗ
    if view in ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ"]:
        st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name} {'(ΕΠΙΣΤΡΟΦΗ)' if st.session_state.return_mode else ''}</div>", unsafe_allow_html=True)
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο (10 ψηφία)", key=f"ph_{st.session_state.ph_key}")
                if len(ph) == 10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                    else: new_customer_popup(ph)
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name} (Αλλαγή)", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}))
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        val = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'bc': bc, 'name': res.data[0]['name'], 'price': val})
                        st.session_state.bc_key += 1; st.rerun()
                    else: st.error("Το Barcode δεν βρέθηκε")
                
                if st.session_state.cart:
                    if st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
                if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            cart_text = "\n".join([f"{i['name'][:35]:35} | {i['price']:>6.2f}€" for i in st.session_state.cart])
            st.markdown(f"<div class='cart-area'>{'ΠΕΡΙΓΡΑΦΗ':35} | {'ΤΙΜΗ':>7}\n{'-'*45}\n{cart_text}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    # 📦 ΑΠΟΘΗΚΗ (Νέο Module)
    elif view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Διαχείριση Αποθήκης & Ρυθμίσεις")
        t1, t2, t3 = st.tabs(["🆕 ΚΑΤΑΧΩΡΗΣΗ", "⚙️ ΡΥΘΜΙΣΕΙΣ ΛΙΣΤΩΝ", "📋 ΑΠΟΘΕΜΑ"])
        
        with t1:
            with st.form("inv_form", clear_on_submit=True):
                c1,c2,c3 = st.columns(3)
                e = c1.selectbox("Είδος", sorted(st.session_state.master_lists["Είδη"]))
                p = c2.selectbox("Προμηθευτής", sorted(st.session_state.master_lists["Προμηθευτές"]))
                c = c3.selectbox("Χρώμα", sorted(st.session_state.master_lists["Χρώματα"]))
                
                c4,c5,c6 = st.columns(3)
                sz = c4.selectbox("Μέγεθος", ["One Size", "S", "M", "L", "XL", "XXL", "36", "38", "40", "42"])
                sy = c5.selectbox("Σύνθεση", sorted(st.session_state.master_lists["Συνθέσεις"]))
                pl = c6.text_input("Κωδικός Σχεδίου")
                
                pr = st.number_input("Τιμή", min_value=0.0)
                stk = st.number_input("Απόθεμα", min_value=0, value=1)
                
                if st.form_submit_button("💾 ΑΠΟΘΗΚΕΥΣΗ") and pl:
                    sku = f"{generate_latin_code(e)}-{generate_latin_code(p)}-{pl}-{generate_latin_code(c)}-{sz}".upper()
                    supabase.table("inventory").upsert({
                        "barcode": sku, "name": f"{e} {c} ({sy})".upper(), 
                        "price": pr, "stock": stk
                    }).execute()
                    st.success(f"OK: {sku}"); time.sleep(1); st.rerun()

        with t2:
            cat = st.selectbox("Λίστα", ["Είδη", "Προμηθευτές", "Χρώματα", "Συνθέσεις"])
            for item in sorted(st.session_state.master_lists[cat]):
                col_a, col_b = st.columns([4, 1])
                col_a.text(item)
                if col_b.button("🗑️", key=f"d_{cat}_{item}"): 
                    st.session_state.master_lists[cat].remove(item); st.rerun()
            new_v = st.text_input("Νέο στοιχείο")
            if st.button("➕ Προσθήκη"):
                if new_v: st.session_state.master_lists[cat].append(new_v); st.rerun()

        with t3:
            res = supabase.table("inventory").select("*").execute()
            if res.data:
                df_inv = pd.DataFrame(res.data).sort_values(by='name')
                for _, r in df_inv.iterrows():
                    c_st, c_del = st.columns([5, 1])
                    stk_color = "#2ecc71" if r['stock'] > 0 else "#e74c3c"
                    c_st.markdown(f"<div class='data-row'>📦 {r['barcode']} | {r['name']} | {r['price']}€ | Stock: <span style='color:{stk_color}'>{r['stock']}</span></div>", unsafe_allow_html=True)
                    if c_del.button("❌", key=f"del_inv_{r['barcode']}"):
                        supabase.table("inventory").delete().eq("barcode", r['barcode']).execute(); st.rerun()

    # 📊 MANAGER
    elif view == "📊 MANAGER":
        st.title("📊 Αναφορές")
        if st.text_input("Κωδικός Manager", type="password") == "999":
            res = supabase.table("sales").select("*").execute()
            if res.data:
                df = pd.DataFrame(res.data)
                st.metric("Συνολικός Τζίρος", f"{df['final_item_price'].sum():.2f}€")
                st.dataframe(df, use_container_width=True)
            else: st.info("Δεν υπάρχουν πωλήσεις.")

    # 👥 ΠΕΛΑΤΕΣ
    elif view == "👥 ΠΕΛΑΤΕΣ":
        st.title("👥 Πελατολόγιο")
        res = supabase.table("customers").select("*").execute()
        if res.data:
            df_cust = pd.DataFrame(res.data)
            for _, r in df_cust.iterrows():
                c1, c2 = st.columns([5, 1])
                c1.markdown(f"<div class='data-row'>👤 {r['name']} | 📞 {r['phone']}</div>", unsafe_allow_html=True)
                if c2.button("❌", key=f"c_del_{r['id']}"):
                    supabase.table("customers").delete().eq("id", r['id']).execute(); st.rerun()
