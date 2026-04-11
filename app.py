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
st.set_page_config(page_title="CHERRY v14.3.6", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    .report-card {
        padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 10px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.5);
    }
    .cash-card { background-color: #27ae60; color: white; border: 2px solid #2ecc71; }
    .card-card { background-color: #2980b9; color: white; border: 2px solid #3498db; }
    .total-card { background-color: #8e44ad; color: white; border: 2px solid #9b59b6; }
    
    .cart-item-row { 
        background-color: #000; padding: 10px; border-radius: 5px; margin-bottom: 5px; 
        border: 1px solid #2ecc71; display: flex; justify-content: space-between; align-items: center;
        font-family: 'Courier New', monospace; color: #2ecc71; font-size: 14px;
    }
    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000 !important; font-weight: bold !important; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; margin-bottom: 20px; }
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
    st.session_state.cust_name = "Λιανική Πώληση"; st.session_state.return_mode = False
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
        st.markdown(f"<div class='sidebar-date'>{st.session_state.manual_ts.strftime('%d/%m/%Y %H:%M')}</div>", unsafe_allow_html=True)
        
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

    # --- ΤΑΜΕΙΟ ---
    if view in ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ"]:
        st.markdown(f"### 👤 {st.session_state.cust_name}")
        cl, cr = st.columns([1, 1.3])
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
                c_i.markdown(f"<div class='cart-item-row'>{item['name'][:30]:30} | {item['price']:.2f}€</div>", unsafe_allow_html=True)
                if c_d.button("❌", key=f"del_{item.get('id', i)}_{i}"): st.session_state.cart.pop(i); st.rerun()
            total = sum(i['price'] for i in st.session_state.cart)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    # --- MANAGER (ΑΝΑΦΟΡΕΣ) ---
    elif view == "📊 MANAGER":
        st.title("📊 MANAGER REPORT")
        if st.text_input("Κωδικός", type="password") == "999":
            res_s = supabase.table("sales").select("*").execute()
            if res_s.data:
                df = pd.DataFrame(res_s.data)
                df['s_date_dt'] = pd.to_datetime(df['s_date'])
                df['ΗΜΕΡΟΜΗΝΙΑ'] = df['s_date_dt'].dt.date
                today = st.session_state.manual_ts.date()
                
                tdf = df[df['ΗΜΕΡΟΜΗΝΙΑ'] == today]
                
                # --- ΕΝΟΤΗΤΑ ΠΡΑΞΕΙΣ (ΚΑΡΤΕΣ) ---
                st.subheader("📋 ΠΡΑΞΕΙΣ ΗΜΕΡΑΣ")
                cash_total = tdf[tdf['method'] == 'Μετρητά']['final_item_price'].sum()
                card_total = tdf[tdf['method'] == 'Κάρτα']['final_item_price'].sum()
                grand_total = tdf['final_item_price'].sum()
                
                m1, m2, m3 = st.columns(3)
                m1.markdown(f"<div class='report-card cash-card'><h3>💵 ΜΕΤΡΗΤΑ</h3><h1>{cash_total:.2f}€</h1></div>", unsafe_allow_html=True)
                m2.markdown(f"<div class='report-card card-card'><h3>💳 ΚΑΡΤΑ</h3><h1>{card_total:.2f}€</h1></div>", unsafe_allow_html=True)
                m3.markdown(f"<div class='report-card total-card'><h3>ΣΥΝΟΛΟ</h3><h1>{grand_total:.2f}€</h1></div>", unsafe_allow_html=True)
                
                tab_a, tab_b = st.tabs(["🕒 ΣΥΝΑΛΛΑΓΕΣ", "📈 INSIGHTS"])
                with tab_a:
                    st.dataframe(tdf[['s_date', 'item_name', 'final_item_price', 'method']], use_container_width=True)
                with tab_b:
                    fig = px.pie(df, values='final_item_price', names='method', title="Συνολικός Τρόπος Πληρωμής")
                    st.plotly_chart(fig, use_container_width=True)

    # --- ΑΠΟΘΗΚΗ ---
    elif view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 ΑΠΟΘΗΚΗ")
        t1, t3 = st.tabs(["🆕 ΚΑΤΑΧΩΡΗΣΗ", "📋 ΑΠΟΘΕΜΑ"])
        with t1:
            with st.form("inv_form", clear_on_submit=True):
                c1,c2,c3 = st.columns(3); e = c1.selectbox("Είδος", sorted(st.session_state.master_lists["Είδη"])); p = c2.selectbox("Προμηθευτής", sorted(st.session_state.master_lists["Προμηθευτές"])); c = c3.selectbox("Χρώμα", sorted(st.session_state.master_lists["Χρώματα"]))
                c4,c5,c6 = st.columns(3); sz = c4.selectbox("Μέγεθος", ["One Size", "S", "M", "L", "XL", "XXL"]); sy = c5.selectbox("Σύνθεση", sorted(st.session_state.master_lists["Συνθέσεις"])); pl = c6.text_input("Σχέδιο")
                pr = st.number_input("Τιμή", min_value=0.0); stk = st.number_input("Stock", min_value=0, value=1)
                if st.form_submit_button("💾 ΑΠΟΘΗΚΕΥΣΗ") and pl:
                    sku = f"{generate_latin_code(e)}-{generate_latin_code(p)}-{pl}-{generate_latin_code(c)}-{sz}".upper()
                    supabase.table("inventory").upsert({"barcode": sku, "name": f"{e} {c} ({sy})".upper(), "price": pr, "stock": stk}).execute()
                    st.success(f"Αποθηκεύτηκε: {sku}")
        with t3:
            res = supabase.table("inventory").select("*").execute()
            if res.data:
                for r in sorted(res.data, key=lambda x: x['name']):
                    c1, c2, c3 = st.columns([5,1,1])
                    c1.markdown(f"<div class='data-row'>📦 {r['barcode']} | {r['name']} | {r['price']}€ | Stock: {r['stock']}</div>", unsafe_allow_html=True)
                    if c2.button("🏷️", key=f"pr_{r['barcode']}"): print_label_popup(r['name'], r['barcode'], r['price'])
                    if c3.button("❌", key=f"del_{r['barcode']}"): supabase.table("inventory").delete().eq("barcode", r['barcode']).execute(); st.rerun()

    elif view == "👥 ΠΕΛΑΤΕΣ":
        res = supabase.table("customers").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data), use_container_width=True)

    elif view == "⚙️ SYSTEM":
        if st.text_input("Κωδικός", type="password") == "999":
            target = st.selectbox("Πίνακας", ["sales", "customers", "inventory"])
            if st.text_input("Γράψτε ΔΙΑΓΡΑΦΗ") == "ΔΙΑΓΡΑΦΗ" and st.button("ΕΚΤΕΛΕΣΗ"):
                supabase.table(target).delete().neq("id", -1).execute(); st.success("OK"); st.rerun()
