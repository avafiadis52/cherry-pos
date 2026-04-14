import pandas as pd
from datetime import datetime, date, timedelta
import time
import streamlit as st
from supabase import create_client, Client
import re
import plotly.express as px
import barcode
from barcode.writer import ImageWriter
import io
import base64

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
st.set_page_config(page_title="CHERRY v14.8.0", layout="wide", page_icon="🍒")

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
        color: #2ecc71;
        overflow-x: auto;
        font-size: 16px;
    }

    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; margin-top: 10px; text-shadow: 2px 2px 10px rgba(46, 204, 113, 0.5); }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; padding: 10px; border-radius: 10px; background-color: #fff3f0; border: 2px solid #e44d26; }
    
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; font-weight: bold !important; border: 1px solid #808080 !important; }
    
    .data-row { font-family: 'Courier New', monospace; background-color: #262626; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; display: block; white-space: pre; }
    .report-stat { background-color: #262730; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; }
    .stat-desc { font-size: 13px; color: #888; }
    </style>
    """, unsafe_allow_html=True)

# Default Lists
DEFAULT_LISTS = {
    "Είδη": ["Ζακέτα", "Ζώνη", "Μπλούζα", "Μπουφάν / Παλτό", "Παντελόνι", "Πουκάμισο", "Φόρεμα", "Φούστα"],
    "Προμηθευτές": ["ONADO", "PINUP", "ΡΕΝΑ", "ΣΤΕΛΛΑ", "ΤΖΕΝΗ"],
    "Χρώματα": ["Γκρι", "Εκρού", "Εμπριμέ", "Καφέ", "Κίτρινο", "Κόκκινο", "Λευκό", "Μαύρο", "Μπεζ", "Μπλε", "Πουά", "Πράσινο", "Ριγέ", "Σιέλ"],
    "Μεγέθη": ["One Size", "Small", "Medium", "Large", "XL", "XXL", "36", "38", "40", "42", "44"],
    "Συνθέσεις": ["100% Βαμβάκι", "100% Πολυέστερ", "70% Βαμβάκι - 30% Πολυέστερ", "98% Βαμβάκι - 2% Ελαστάνη", "100% Δέρμα", "Τεχνητό Δέρμα (PU)"]
}

# --- Sync Lists Logic ---
def save_master_lists():
    if supabase and 'master_lists' in st.session_state:
        try:
            supabase.table("inventory_settings").upsert({"config_name": "master_lists", "config_value": st.session_state.master_lists}).execute()
            return True
        except: return False

def sync_master_lists():
    if 'master_lists' not in st.session_state:
        if supabase:
            try:
                res = supabase.table("inventory_settings").select("config_value").eq("config_name", "master_lists").execute()
                if res.data:
                    st.session_state.master_lists = res.data[0]['config_value']
                else:
                    st.session_state.master_lists = DEFAULT_LISTS.copy()
                    save_master_lists()
            except: st.session_state.master_lists = DEFAULT_LISTS.copy()

# Session States
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'mic_key' not in st.session_state: st.session_state.mic_key = 28000
if 'form_reset_key' not in st.session_state: st.session_state.form_reset_key = 0

sync_master_lists()

# --- HELPER FUNCTIONS ---
def get_athens_now(): return datetime.now() + timedelta(hours=2)

def generate_latin_code(text):
    char_map = {'Α':'A','Β':'B','Γ':'G','Δ':'D','Ε':'E','Ζ':'Z','Η':'H','Θ':'TH','Ι':'I','Κ':'K','Λ':'L','Μ':'M','Ν':'N','Ξ':'X','Ο':'O','Π':'P','Ρ':'R','Σ':'S','Τ':'T','Υ':'Y','Φ':'F','Χ':'CH','Ψ':'PS','Ω':'O','Ά':'A','Έ':'E','Ή':'H','Ί':'I','Ό':'O','Ύ':'Y','Ώ':'O','Ϊ':'I','Ϋ':'Y'}
    res = "".join([char_map.get(c, c) for c in str(text).upper()])
    return res[:3]

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1
    st.rerun()

# --- DIALOGS ---
@st.dialog("🏷️ Ετικέτα")
def print_label_popup(bc, name, price):
    label_html = f"""<div style='text-align:center; background:white; color:black; padding:10px; border:1px solid #000; font-family:Arial;'>
        <b>CHERRY</b><br><small>{name}</small><br><h3>{price:.2f}€</h3><br><small>{bc}</small></div>"""
    st.markdown(label_html, unsafe_allow_html=True)
    if st.button("ΕΚΤΥΠΩΣΗ"):
        st.components.v1.html(f"<script>window.print();</script>", height=0)

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    inp = st.text_input("Έκπτωση (ποσό ή %)")
    disc = 0.0
    if inp:
        try: disc = (float(inp.replace("%",""))/100 * total) if "%" in inp else float(inp)
        except: pass
    final = total - disc
    st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {final:.2f}€</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize_sale(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize_sale(disc, "Κάρτα")

def finalize_sale(disc_val, method):
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = st.session_state.get('manual_ts', get_athens_now()).strftime("%Y-%m-%d %H:%M:%S")
    for i in st.session_state.cart:
        d = round(i['price'] * ratio, 2)
        f = round(i['price'] - d, 2)
        supabase.table("sales").insert({"barcode":i['bc'], "item_name":i['name'], "unit_price":i['price'], "discount":d, "final_item_price":f, "method":method, "s_date":ts, "cust_id":st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None}).execute()
        if i['bc'] != 'VOICE':
            res = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
            if res.data: supabase.table("inventory").update({"stock": res.data[0]['stock'] - 1}).eq("barcode", i['bc']).execute()
    st.success("✅ ΕΠΙΤΥΧΙΑ"); time.sleep(1); reset_app()

# --- MAIN APP ---
if not st.session_state.logged_in:
    st.title("🔒 CHERRY LOGIN")
    if st.text_input("Password", type="password") == "CHERRY123":
        if st.button("Είσοδος"): st.session_state.logged_in = True; st.rerun()
else:
    with st.sidebar:
        chosen_date = st.date_input("Ημερομηνία", value=get_athens_now().date())
        chosen_time = st.time_input("Ώρα", value=get_athens_now().time())
        st.session_state.manual_ts = datetime.combine(chosen_date, chosen_time)
        if HAS_MIC:
            text = speech_to_text(language='el', start_prompt="🔴 ΠΑΤΑ ΚΑΙ ΜΙΛΑ", key=f"mic_{st.session_state.mic_key}")
            if text:
                nums = re.findall(r"\d+", text)
                if nums:
                    st.session_state.cart.append({'bc':'VOICE','name':text.upper(),'price':float(nums[0])})
                    st.session_state.mic_key += 1; st.rerun()
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])

    if view == "🛒 ΤΑΜΕΙΟ" or view == "🔄 ΕΠΙΣΤΡΟΦΗ":
        is_ret = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        st.subheader("🛒 ΤΑΜΕΙΟ" if not is_ret else "🔄 ΕΠΙΣΤΡΟΦΗ")
        cl, cr = st.columns([1, 1.5])
        with cl:
            bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
            if bc:
                res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                if res.data:
                    p = -float(res.data[0]['price']) if is_ret else float(res.data[0]['price'])
                    st.session_state.cart.append({'bc':res.data[0]['barcode'], 'name':res.data[0]['name'], 'price':p})
                    st.session_state.bc_key += 1; st.rerun()
            if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
            if st.button("❌ ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            st.markdown("<div class='cart-area'>" + "\n".join([f"{i['name']} | {i['price']}€" for i in st.session_state.cart]) + "</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{sum(i['price'] for i in st.session_state.cart):.2f}€</div>", unsafe_allow_html=True)

    elif view == "📊 MANAGER":
        st.title("📊 Manager Insights")
        pwd = st.text_input("Manager Password", type="password")
        if pwd == "999":
            res = supabase.table("sales").select("*").execute()
            if res.data:
                df = pd.DataFrame(res.data)
                df['s_date'] = pd.to_datetime(df['s_date'])
                
                # --- ΦΙΛΤΡΑ ---
                c1, c2 = st.columns(2)
                d1 = c1.date_input("Από", value=get_athens_now().date() - timedelta(days=7))
                d2 = c2.date_input("Έως", value=get_athens_now().date())
                mask = (df['s_date'].dt.date >= d1) & (df['s_date'].dt.date <= d2)
                fdf = df.loc[mask]

                # --- STATS ---
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("Σύνολο", f"{fdf['final_item_price'].sum():.2f}€")
                s2.metric("Μετρητά", f"{fdf[fdf['method']=='Μετρητά']['final_item_price'].sum():.2f}€")
                s3.metric("Κάρτα", f"{fdf[fdf['method']=='Κάρτα']['final_item_price'].sum():.2f}€")
                s4.metric("Πωλήσεις", len(fdf))

                # --- INSIGHTS ---
                st.subheader("📈 Πωλήσεις ανά Ημέρα")
                daily = fdf.groupby(fdf['s_date'].dt.date)['final_item_price'].sum().reset_index()
                fig = px.bar(daily, x='s_date', y='final_item_price', color_discrete_sequence=['#2ecc71'])
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("📝 Αναλυτικές Πράξεις")
                st.dataframe(fdf[['s_date', 'item_name', 'final_item_price', 'method']].sort_values(by='s_date', ascending=False), use_container_width=True)

    elif view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Αποθήκη")
        t_new, t_set, t_inv = st.tabs(["🆕 ΝΕΟ", "⚙️ ΡΥΘΜΙΣΕΙΣ", "📋 LIST"])
        with t_new:
            with st.form(f"inv_{st.session_state.form_reset_key}", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                f_item = c1.selectbox("Είδος", sorted(st.session_state.master_lists["Είδη"]))
                f_prov = c2.selectbox("Προμηθευτής", sorted(st.session_state.master_lists["Προμηθευτές"]))
                f_design = c3.text_input("Σχέδιο")
                c4, c5, c6 = st.columns(3)
                f_color = c4.selectbox("Χρώμα", sorted(st.session_state.master_lists["Χρώματα"]))
                f_size = c5.selectbox("Μέγεθος", sorted(st.session_state.master_lists["Μεγέθη"]))
                f_price = c6.number_input("Τιμή", min_value=0.0)
                if st.form_submit_button("ΑΠΟΘΗΚΕΥΣΗ"):
                    sku = f"{generate_latin_code(f_item)}-{generate_latin_code(f_prov)}-{f_design.upper()}"
                    supabase.table("inventory").upsert({"barcode":sku, "name":f"{f_item} {f_color}", "price":f_price, "stock":1}).execute()
                    st.success(f"OK: {sku}")
                    st.session_state.form_reset_key += 1; time.sleep(1); st.rerun()

        with t_set:
            cat = st.selectbox("Λίστα", list(st.session_state.master_lists.keys()))
            new_v = st.text_input("Νέο στοιχείο")
            if st.button("Προσθήκη"):
                st.session_state.master_lists[cat].append(new_v)
                save_master_lists(); st.rerun()
            for v in sorted(st.session_state.master_lists[cat]):
                col1, col2 = st.columns([4,1])
                col1.write(v)
                if col2.button("🗑️", key=f"del_{v}"):
                    st.session_state.master_lists[cat].remove(v)
                    save_master_lists(); st.rerun()
        
        with t_inv:
            res = supabase.table("inventory").select("*").execute()
            if res.data:
                for r in res.data:
                    c1, c2, c3 = st.columns([5,1,1])
                    c1.write(f"📦 {r['barcode']} | {r['name']} | {r['price']}€")
                    if c2.button("🏷️", key=f"pr_{r['barcode']}"): print_label_popup(r['barcode'], r['name'], r['price'])
                    if c3.button("❌", key=f"dl_{r['barcode']}"): supabase.table("inventory").delete().eq("barcode", r['barcode']).execute(); st.rerun()

    elif view == "👥 ΠΕΛΑΤΕΣ":
        st.title("👥 Πελάτες")
        res = supabase.table("customers").select("*").execute()
        if res.data:
            for r in res.data:
                st.markdown(f"<div class='data-row'>👤 {r['name']} | 📞 {r['phone']}</div>", unsafe_allow_html=True)
