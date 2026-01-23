import pandas as pd
from datetime import datetime, date, timedelta
import time
import streamlit as st
import re
from supabase import create_client, Client

# --- 1. EXPERIMENTAL COMPONENT LOAD ---
try:
    from streamlit_mic_recorder import speech_to_text
    HAS_MIC = True
except ImportError:
    HAS_MIC = False

# --- 2. SUPABASE SETUP ---
SUPABASE_URL = "https://hnwynihjkdkryrfepenh.supabase.co"
SUPABASE_KEY = "sb_publishable_ualF72lJKgUQA4TzjPQ-OA_zih7zJ-s"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# --- 3. CONFIG & STYLE ---
st.set_page_config(page_title="CHERRY v14.0.79", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; }
    .cart-area { font-family: 'Courier New', monospace; background-color: #2b2b2b; padding: 15px; border-radius: 5px; white-space: pre-wrap; border: 1px solid #3b3b3b; min-height: 200px; font-size: 14px; }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; padding: 10px; border-radius: 10px; background-color: #fff3f0; border: 2px solid #e44d26; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; font-weight: bold !important; }
    .data-row { background-color: #262626; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    .report-stat { background-color: #262730; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 5px; }
    .stat-val { font-size: 20px; font-weight: bold; color: #2ecc71; margin: 0; }
    .stat-label { font-size: 11px; color: #888; margin: 0; font-weight: bold; text-transform: uppercase; }
    .day-container { background-color: #212121; padding: 15px; border-radius: 10px; border: 1px solid #333; margin-bottom: 25px; }
    .day-title { color: #f1c40f; font-size: 22px; font-weight: bold; border-bottom: 2px solid #f1c40f; margin-bottom: 15px; padding-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'is_logged_out' not in st.session_state: st.session_state.is_logged_out = False
if 'last_speech' not in st.session_state: st.session_state.last_speech = None
if 'mic_key' not in st.session_state: st.session_state.mic_key = 500

# --- 4. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart = []
    st.session_state.selected_cust_id = None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1
    st.rerun()

def play_sound(url):
    st.components.v1.html(f'<audio autoplay style="display:none"><source src="{url}" type="audio/mpeg"></audio>', height=0)

@st.dialog("➕ Χειροκίνητο Είδος (999)")
def manual_item_popup():
    m_name = st.text_input("Όνομα Είδους")
    m_price = st.number_input("Τιμή (€)", min_value=0.0, format="%.2f", step=0.1)
    if st.button("Προσθήκη", use_container_width=True):
        if m_name:
            st.session_state.cart.append({'bc': '999', 'name': m_name, 'price': round(float(m_price), 2)})
            st.session_state.bc_key += 1; st.rerun()

@st.dialog("🆕 Νέος Πελάτης")
def new_customer_popup(phone=""):
    name = st.text_input("Ονοματεπώνυμο")
    phone_val = st.text_input("Τηλέφωνο", value=phone)
    if st.button("Αποθήκευση", use_container_width=True):
        res = supabase.table("customers").insert({"name": name, "phone": phone_val}).execute()
        if res.data:
            st.session_state.selected_cust_id = res.data[0]['id']
            st.session_state.cust_name = res.data[0]['name']
            st.success("Αποθηκεύτηκε!"); time.sleep(0.5); st.rerun()

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    opt = st.radio("Έκπτωση;", ["ΟΧΙ", "ΝΑΙ"], horizontal=True)
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή % (π.χ. 10%)")
        if inp:
            try:
                if "%" in inp: disc = round((float(inp.replace("%",""))/100 * total), 2)
                else: disc = round(float(inp), 2)
            except: st.error("Λάθος μορφή")
    final_p = round(total - disc, 2)
    st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {final_p:.2f}€</div>", unsafe_allow_html=True)
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

def finalize(disc_val, method):
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    action_id = int(time.time())
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    try:
        for i in st.session_state.cart:
            d = round(i['price'] * ratio, 2)
            f = round(i['price'] - d, 2)
            data = {"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": float(d), "final_item_price": float(f), "method": str(method), "s_date": ts, "cust_id": c_id, "action_id": action_id}
            try: supabase.table("sales").insert(data).execute()
            except: 
                data.pop("action_id", None)
                supabase.table("sales").insert(data).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); play_sound("https://www.soundjay.com/misc/sounds/magic-chime-01.mp3"); time.sleep(1); reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

# --- 5. MAIN UI ---
if st.session_state.is_logged_out:
    st.markdown("<h1 style='text-align: center; color: #e74c3c;'>Αποσυνδεθήκατε</h1>", unsafe_allow_html=True)
    if st.button("Επανασύνδεση"): st.session_state.is_logged_out = False; st.rerun()
else:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-date'>{get_athens_now().strftime('%d/%m/%Y %H:%M:%S')}</div>", unsafe_allow_html=True)
        st.title("CHERRY 14.0.79")
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])
        if st.button("❌ Έξοδος", use_container_width=True): st.session_state.cart = []; st.session_state.is_logged_out = True; st.rerun()

    if view == "🛒 ΤΑΜΕΙΟ":
        st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", placeholder="----------", key=f"ph_{st.session_state.ph_key}")
                if ph and len(ph) == 10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                    else: new_customer_popup(ph)
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name}", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    if bc == "999": manual_item_popup()
                    else:
                        res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                        if res.data: st.session_state.cart.append({'bc': res.data[0]['barcode'], 'name': res.data[0]['name'], 'price': float(res.data[0]['price'])}); st.session_state.bc_key += 1; st.rerun()
                for idx, item in enumerate(st.session_state.cart):
                    if st.button(f"❌ {item['name']} {item['price']}€", key=f"del_{idx}", use_container_width=True): st.session_state.cart.pop(idx); st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
            if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            st.markdown(f"<div class='cart-area'>{'Είδος':<20} | {'Τιμή':>6}\n{'-'*30}\n" + "\n".join([f"{i['name'][:20]:<20} | {i['price']:>6.2f}€" for i in st.session_state.cart]) + "</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif view == "📊 MANAGER":
        st.header("📊 Manager")
        t1, t2 = st.tabs(["📅 ΤΑΜΕΙΟ ΗΜΕΡΑΣ", "📆 ΠΕΡΙΟΔΟΥ"])
        
        res = supabase.table("sales").select("*").execute()
        if res.data:
            all_df = pd.DataFrame(res.data)
            all_df['s_date_dt'] = pd.to_datetime(all_df['s_date'])
            all_df['date_only'] = all_df['s_date_dt'].dt.date
            
            def render_day_report(df, date_label):
                with st.container():
                    st.markdown(f"<div class='day-title'>📅 Ημερομηνία: {date_label}</div>", unsafe_allow_html=True)
                    
                    # Υπολογισμοί για την ημέρα
                    group_col = 'action_id' if 'action_id' in df.columns and df['action_id'].notnull().any() else 's_date'
                    m_df = df[df['method'] == 'Μετρητά']
                    k_df = df[df['method'] == 'Κάρτα']
                    
                    m_sum, k_sum = m_df['final_item_price'].sum(), k_df['final_item_price'].sum()
                    m_count, k_count = m_df[group_col].nunique(), k_df[group_col].nunique()
                    
                    c1, c2, c3 = st.columns(3)
                    c1.markdown(f"<div class='report-stat'><p class='stat-label'>Μετρητά ({m_count})</p><p class='stat-val'>{m_sum:.2f}€</p></div>", unsafe_allow_html=True)
                    c2.markdown(f"<div class='report-stat'><p class='stat-label'>Κάρτα ({k_count})</p><p class='stat-val'>{k_sum:.2f}€</p></div>", unsafe_allow_html=True)
                    c3.markdown(f"<div class='report-stat'><p class='stat-label'>Σύνολο ({m_count+k_count})</p><p class='stat-val'>{m_sum+k_sum:.2f}€</p></div>", unsafe_allow_html=True)
                    
                    # Αρίθμηση πράξεων ημέρας
                    day_df = df.sort_values('s_date', ascending=True)
                    u_groups = day_df[group_col].unique()
                    mapping = {v: i+1 for i, v in enumerate(u_groups)}
                    day_df['ΠΡΑΞΗ'] = day_df[group_col].map(mapping)
                    
                    disp = day_df.rename(columns={'s_date':'Ημ/νία','item_name':'Είδος','unit_price':'Αρχική','discount':'Έκπτωση','final_item_price':'Τελική','method':'Τρόπος'})
                    st.dataframe(disp.sort_values(['ΠΡΑΞΗ', 'Ημ/νία'], ascending=[False, False])[['ΠΡΑΞΗ', 'Ημ/νία', 'Είδος', 'Αρχική', 'Έκπτωση', 'Τελική', 'Τρόπος']], use_container_width=True, hide_index=True)
                    st.markdown("---")

            with t1:
                today = get_athens_now().date()
                render_day_report(all_df[all_df['date_only'] == today].copy(), today.strftime('%d/%m/%Y'))
                
            with t2:
                c1, c2 = st.columns(2)
                d_f, d_t = c1.date_input("Από", get_athens_now().date()), c2.date_input("Έως", get_athens_now().date())
                period_df = all_df[(all_df['date_only'] >= d_f) & (all_df['date_only'] <= d_t)].copy()
                if not period_df.empty:
                    days = sorted(period_df['date_only'].unique(), reverse=True)
                    for d in days:
                        render_day_report(period_df[period_df['date_only'] == d].copy(), d.strftime('%d/%m/%Y'))
                else:
                    st.info("Δεν βρέθηκαν πωλήσεις για αυτή την περίοδο.")

    elif view == "📦 ΑΠΟΘΗΚΗ":
        with st.form("inv_f", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            b, n, p, s = c1.text_input("BC"), c2.text_input("Όνομα"), c3.number_input("Τιμή", step=0.01), c4.number_input("Stock", step=1)
            if st.form_submit_button("Προσθήκη") and b and n: supabase.table("inventory").upsert({"barcode": b, "name": n, "price": p, "stock": s}).execute(); st.rerun()
        for r in supabase.table("inventory").select("*").execute().data:
            st.markdown(f"<div class='data-row'>{r['barcode']} | {r['name']} | {r['price']}€ | Stock: {r['stock']}</div>", unsafe_allow_html=True)
            if st.button("❌", key=f"inv_{r['barcode']}"): supabase.table("inventory").delete().eq("barcode", r['barcode']).execute(); st.rerun()

    elif view == "👥 ΠΕΛΑΤΕΣ":
        for r in supabase.table("customers").select("*").execute().data:
            st.markdown(f"<div class='data-row'>👤 {r['name']} | 📞 {r['phone']}</div>", unsafe_allow_html=True)
            if st.button("❌", key=f"c_{r['id']}"): supabase.table("customers").delete().eq("id", r['id']).execute(); st.rerun()
