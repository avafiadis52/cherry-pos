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

# --- 3. CONFIG & STYLE (Version v14.3.1) ---
st.set_page_config(page_title="CHERRY v14.3.1", layout="wide", page_icon="🍒")

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
    </style>
    """, unsafe_allow_html=True)

# Session States
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

# --- 4. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def generate_latin_code(text):
    char_map = {'Α':'A','Β':'B','Γ':'G','Δ':'D','Ε':'E','Ζ':'Z','Η':'H','Θ':'TH','Ι':'I','Κ':'K','Λ':'L','Μ':'M','Ν':'N','Ξ':'X','Ο':'O','Π':'P','Ρ':'R','Σ':'S','Τ':'T','Υ':'Y','Φ':'F','Χ':'CH','Ψ':'PS','Ω':'O'}
    return "".join([char_map.get(c, c) for c in str(text).upper()[:3]])

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.return_mode = False
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1
    st.rerun()

def switch_to_normal():
    st.session_state.return_mode = False
    if 'sidebar_nav' in st.session_state:
        st.session_state.sidebar_nav = "🛒 ΤΑΜΕΙΟ"

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
            supabase.table("sales").insert({"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": float(d), "final_item_price": float(f), "method": str(method), "s_date": ts, "cust_id": c_id}).execute()
            if i['bc'] != 'VOICE':
                res_inv = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
                if res_inv.data:
                    change = 1 if i['price'] < 0 else -1
                    new_stock = int(res_inv.data[0]['stock']) + change
                    supabase.table("inventory").update({"stock": new_stock}).eq("barcode", i['bc']).execute()
        st.success("✅ ΟΛΟΚΛΗΡΩΘΗΚΕ"); time.sleep(1); reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

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

# --- 5. MAIN UI ---
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.title("🔒 LOGIN")
        pwd = st.text_input("Password", type="password")
        if st.button("Είσοδος", use_container_width=True):
            if pwd == "CHERRY123": st.session_state.logged_in = True; st.rerun()
            else: st.error("Λάθος κωδικός")
else:
    with st.sidebar:
        now = get_athens_now()
        chosen_date = st.date_input("Ημερομηνία", value=now.date())
        chosen_time = st.time_input("Ώρα", value=now.time())
        st.session_state.manual_ts = datetime.combine(chosen_date, chosen_time)
        
        if HAS_MIC:
            text = speech_to_text(language='el', start_prompt="🎙️ ΦΩΝΗΤΙΚΗ ΕΝΤΟΛΗ", key=f"mic_{st.session_state.mic_key}")
            if text:
                numbers = re.findall(r"[-+]?\d*\.\d+|\d+", text)
                if numbers:
                    p = float(numbers[0])
                    nm = text.replace(str(numbers[0]), "").strip().upper() or "ΦΩΝΗΤΙΚΗ ΠΩΛΗΣΗ"
                    final_p = -p if st.session_state.return_mode else p
                    st.session_state.cart.append({'bc': 'VOICE', 'name': nm, 'price': final_p})
                    st.session_state.mic_key += 1; st.rerun()

        st.divider()
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ", "⚙️ SYSTEM"], key="sidebar_nav")
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        if st.button("❌ Έξοδος"): st.session_state.logged_in = False; st.rerun()

    if view in ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ"]:
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"ph_{st.session_state.ph_key}")
                if len(ph) == 10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data: 
                        st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']
                        st.rerun()
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name} (Αλλαγή)", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        val = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'bc': res.data[0]['barcode'], 'name': res.data[0]['name'], 'price': val})
                        st.session_state.bc_key += 1; st.rerun()
                for idx, i in enumerate(st.session_state.cart):
                    if st.button(f"❌ {i['name']} {i['price']}€", key=f"del_{idx}", use_container_width=True): st.session_state.cart.pop(idx); st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
            if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            lines = [f"{i['name'][:40]:40} | {i['price']:>6.2f}€" for i in st.session_state.cart]
            st.markdown(f"<div class='cart-area'>{'Είδος':40} | {'Τιμή':>7}\n{'-'*50}\n" + "\n".join(lines) + "</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif view == "📦 ΑΠΟΘΗΚΗ":
        tab1, tab2, tab3 = st.tabs(["🆕 ΚΑΤΑΧΩΡΗΣΗ", "⚙️ ΡΥΘΜΙΣΕΙΣ", "📋 ΑΠΟΘΕΜΑ"])
        with tab1:
            with st.form("inv_form", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                e = c1.selectbox("Είδος", sorted(st.session_state.master_lists["Είδη"]))
                p = c2.selectbox("Προμηθευτής", sorted(st.session_state.master_lists["Προμηθευτές"]))
                c = c3.selectbox("Χρώμα", sorted(st.session_state.master_lists["Χρώματα"]))
                pl = st.text_input("Σχέδιο")
                pr = st.number_input("Τιμή", min_value=0.0)
                stk = st.number_input("Stock", min_value=0, value=1)
                if st.form_submit_button("💾 ΑΠΟΘΗΚΕΥΣΗ"):
                    sku = f"{generate_latin_code(e)}-{generate_latin_code(p)}-{pl.upper()}"
                    supabase.table("inventory").upsert({"barcode": sku, "name": f"{e} {c}".upper(), "price": pr, "stock": stk}).execute()
                    st.success(f"Καταχωρήθηκε: {sku}")
        with tab3:
            res = supabase.table("inventory").select("*").execute()
            if res.data:
                for r in res.data: st.markdown(f"<div class='data-row'>📦 {r['barcode']} | {r['name']} | {r['price']}€ | Stock: {r['stock']}</div>", unsafe_allow_html=True)

    elif view == "📊 MANAGER":
        st.title("📊 MANAGER")
        if st.text_input("Κωδικός", type="password") == "999":
            res = supabase.table("sales").select("*").execute()
            if res.data:
                df = pd.DataFrame(res.data)
                df['s_date'] = pd.to_datetime(df['s_date'])
                t1, t2 = st.tabs(["📅 ΣΗΜΕΡΑ", "📈 INSIGHTS"])
                with t1:
                    today = st.session_state.manual_ts.date()
                    tdf = df[df['s_date'].dt.date == today]
                    st.metric("Τζίρος Ημέρας", f"{tdf['final_item_price'].sum():.2f}€")
                    st.dataframe(tdf, use_container_width=True)
                with t2:
                    ix1, ix2 = st.columns(2)
                    i_sd = ix1.date_input("Από", today-timedelta(days=30), key="ins_start")
                    i_ed = ix2.date_input("Έως", today, key="ins_end")
                    idf = df[(df['s_date'].dt.date >= i_sd) & (df['s_date'].dt.date <= i_ed)]
                    if not idf.empty:
                        fig = px.bar(idf.groupby('item_name')['final_item_price'].sum().reset_index(), x='item_name', y='final_item_price')
                        st.plotly_chart(fig, use_container_width=True)
