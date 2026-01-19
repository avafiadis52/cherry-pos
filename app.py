import pandas as pd
from datetime import datetime, date, timedelta
import time
import streamlit as st
from supabase import create_client, Client

# --- 1. SUPABASE SETUP ---
SUPABASE_URL = "https://hnwynihjkdkryrfepenh.supabase.co"
SUPABASE_KEY = "sb_publishable_ualF72lJKgUQA4TzjPQ-OA_zih7zJ-s"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# --- 2. CONFIG & STYLE ---
st.set_page_config(page_title="CHERRY v13.9.2", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    .stTextInput label { color: white !important; font-weight: bold !important; font-size: 16px !important; }
    .cart-area { font-family: 'Courier New', monospace; background-color: #2b2b2b; padding: 15px; border-radius: 5px; white-space: pre-wrap; border: 1px solid #3b3b3b; min-height: 200px; font-size: 14px; }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #f1c40f; text-align: center; margin: 10px 0; border: 2px solid #f1c40f; padding: 10px; border-radius: 10px; }
    
    /* Report Styles */
    .report-stat { background-color: #262730; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; margin: 0; }
    .stat-label { font-size: 13px; color: #888; margin: 0; font-weight: bold; text-transform: uppercase; }

    div.stButton > button {
        background-color: #d3d3d3 !important;
        color: #000000 !important;
        border-radius: 8px !important;
        border: 1px solid #ffffff !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'is_logged_out' not in st.session_state: st.session_state.is_logged_out = False
if 'audio_enabled' not in st.session_state: st.session_state.audio_enabled = False

if st.session_state.is_logged_out:
    st.markdown("<h1 style='text-align: center; color: #e74c3c; margin-top: 100px;'>🔒 Η ΕΦΑΡΜΟΓΗ ΕΚΛΕΙΣΕ</h1>", unsafe_allow_html=True)
    st.stop()

# --- 3. FUNCTIONS ---
def trigger_alert_sound():
    sound_url = "https://www.soundjay.com/buttons/beep-01a.mp3"
    st.components.v1.html(f"""<script>var audio = new Audio("{sound_url}"); audio.play();</script>""", height=0)

def reset_app():
    st.session_state.cart = []
    st.session_state.selected_cust_id = None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1
    st.session_state.ph_key += 1
    st.rerun()

@st.dialog("📦 ΕΛΕΥΘΕΡΟ ΕΙΔΟΣ (999)")
def manual_item_popup():
    m_name = st.text_input("Όνομα Είδους", key="m_name_in")
    m_price = st.number_input("Τιμή (€)", min_value=0.0, format="%.2f", step=0.1, key="m_price_in")
    if st.button("ΠΡΟΣΘΗΚΗ", use_container_width=True):
        if m_name:
            st.session_state.cart.append({'bc': '999', 'name': m_name, 'price': round(float(m_price), 2)})
            st.session_state.bc_key += 1
            st.rerun()

@st.dialog("👤 ΝΕΟΣ ΠΕΛΑΤΗΣ")
def new_customer_popup(phone):
    name = st.text_input("Ονοματεπώνυμο")
    if st.button("ΑΠΟΘΗΚΕΥΣΗ", use_container_width=True):
        res = supabase.table("customers").insert({"name": name, "phone": phone}).execute()
        if res.data:
            st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], name
            st.rerun()

@st.dialog("💰 ΠΛΗΡΩΜΗ")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center; color: #888;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    
    opt = st.radio("Έκπτωση;", ["ΟΧΙ", "ΝΑΙ"], horizontal=True, key="pay_opt_v2")
    disc = 0.0
    
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή % (π.χ. 10%):", key="p_disc_val_v2")
        if inp:
            try:
                if "%" in inp: disc = round((float(inp.replace("%",""))/100 * total), 2)
                else: disc = round(float(inp), 2)
            except: st.error("Σφάλμα τιμής")
            
    final_p = round(total - disc, 2)
    st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {final_p:.2f}€</div>", unsafe_allow_html=True)
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("💵 ΜΕΤΡΗΤΑ", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 ΚΑΡΤΑ", use_container_width=True): finalize(disc, "Κάρτα")

def finalize(disc_val, method):
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None

    try:
        for i in st.session_state.cart:
            d = round(i['price'] * ratio, 2)
            f = round(i['price'] - d, 2)
            data = {"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": float(d), "final_item_price": float(f), "method": str(method), "s_date": ts, "cust_id": c_id}
            supabase.table("sales").insert(data).execute()
            
            if i['bc'] != '999':
                res = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
                if res.data:
                    supabase.table("inventory").update({"stock": res.data[0]['stock'] - 1}).eq("barcode", i['bc']).execute()
        st.success("ΟΛΟΚΛΗΡΩΘΗΚΕ!")
        time.sleep(0.5)
        reset_app()
    except Exception as e:
        st.error(f"Σφάλμα: {e}")

def display_report(df):
    if df.empty:
        st.info("Δεν υπάρχουν δεδομένα.")
        return
    df = df.sort_values('s_date', ascending=False)
    # Ομαδοποίηση ανά ημερομηνία/ώρα για να βρούμε τις μοναδικές συναλλαγές
    unique_trans = df.groupby('s_date').agg({'final_item_price': 'sum', 'method': 'first'}).reset_index()
    unique_trans['ΠΡΑΞΗ'] = range(len(unique_trans), 0, -1)
    df = df.merge(unique_trans[['s_date', 'ΠΡΑΞΗ']], on='s_date')
    
    m_df = unique_trans[unique_trans['method'] == 'Μετρητά']
    k_df = unique_trans[unique_trans['method'] == 'Κάρτα']
    
    cols = st.columns(5)
    cols[0].markdown(f"<div class='report-stat'><p class='stat-label'>💵 ΜΕΤΡΗΤΑ</p><p class='stat-val'>{m_df['final_item_price'].sum():.2f}€</p></div>", unsafe_allow_html=True)
    cols[1].markdown(f"<div class='report-stat'><p class='stat-label'>💳 ΚΑΡΤΑ</p><p class='stat-val'>{k_df['final_item_price'].sum():.2f}€</p></div>", unsafe_allow_html=True)
    cols[2].markdown(f"<div class='report-stat'><p class='stat-label'>🎁 ΕΚΠΤΩΣΗ</p><p class='stat-val'>{df['discount'].sum():.2f}€</p></div>", unsafe_allow_html=True)
    cols[3].markdown(f"<div class='report-stat'><p class='stat-label'>📦 ΤΕΜΑΧΙΑ</p><p class='stat-val'>{len(df)}</p></div>", unsafe_allow_html=True)
    cols[4].markdown(f"<div class='report-stat'><p class='stat-label'>✅ ΣΥΝΟΛΟ</p><p class='stat-val'>{unique_trans['final_item_price'].sum():.2f}€</p></div>", unsafe_allow_html=True)
    
    st.dataframe(df[['ΠΡΑΞΗ', 's_date', 'item_name', 'unit_price', 'discount', 'final_item_price', 'method']].sort_values('ΠΡΑΞΗ', ascending=False), use_container_width=True, hide_index=True)

# --- 4. MAIN UI ---
with st.sidebar:
    st.title("CHERRY 13.9.2")
    view = st.radio("ΜΕΝΟΥ", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])
    if st.button("❌ ΕΞΟΔΟΣ", use_container_width=True):
        st.session_state.is_logged_out = True; st.rerun()

if view == "🛒 ΤΑΜΕΙΟ":
    st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
    cl, cr = st.columns([1, 1.5])
    with cl:
        if st.session_state.selected_cust_id is None:
            ph = st.text_input("Τηλέφωνο", key=f"ph_{st.session_state.ph_key}")
            if ph:
                res = supabase.table("customers").select("*").eq("phone", ph.strip()).execute()
                if res.data: 
                    st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']
                    st.rerun()
                else: new_customer_popup(ph.strip())
            if st.button("🛒 ΛΙΑΝΙΚΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
        else:
            st.button(f"👤 {st.session_state.cust_name}", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
            bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
            if bc:
                if bc.strip() == "999": manual_item_popup()
                else:
                    res = supabase.table("inventory").select("*").eq("barcode", bc.strip()).execute()
                    if res.data:
                        item = res.data[0]
                        st.session_state.cart.append({'bc': item['barcode'], 'name': item['name'], 'price': round(float(item['price']), 2)})
                        st.session_state.bc_key += 1; st.rerun()
                    else: trigger_alert_sound(); st.session_state.bc_key += 1; st.rerun()
            for idx, item in enumerate(st.session_state.cart):
                if st.button(f"❌ {item['name']} ({item['price']}€)", key=f"del_{idx}", use_container_width=True):
                    st.session_state.cart.pop(idx); st.rerun()
            if st.session_state.cart:
                if st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True, key="pay_trigger"):
                    payment_popup()
        if st.button("🗑️ ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
    with cr:
        total = sum(i['price'] for i in st.session_state.cart)
        lines = [f"{i['name'][:20]:<20} | {i['price']:>6.2f}€" for i in st.session_state.cart]
        st.markdown(f"<div class='cart-area'>{'ΕΙΔΟΣ':<20} | {'ΤΙΜΗ':>6}\n{'-'*30}\n{chr(10).join(lines)}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

elif view == "📊 MANAGER":
    res_all = supabase.table("sales").select("*").execute()
    if res_all.data:
        full_df = pd.DataFrame(res_all.data)
        full_df['s_date_dt'] = pd.to_datetime(full_df['s_date'])
        t1, t2 = st.tabs(["📅 ΣΗΜΕΡΑ", "📆 ΠΕΡΙΟΔΟΣ"])
        with t1:
            display_report(full_df[full_df['s_date_dt'].dt.date == date.today()])
        with t2:
            c1, c2 = st.columns(2)
            d_s, d_e = c1.date_input("Από:", date.today() - timedelta(days=7)), c2.date_input("Έως:", date.today())
            display_report(full_df[(full_df['s_date_dt'].dt.date >= d_s) & (full_df['s_date_dt'].dt.date <= d_e)])
    else: st.info("Δεν υπάρχουν πωλήσεις.")

elif view == "📦 ΑΠΟΘΗΚΗ":
    with st.form("inv", clear_on_submit=True):
        b, n, p, s = st.text_input("Barcode"), st.text_input("Όνομα"), st.number_input("Τιμή", step=0.1), st.number_input("Stock", step=1)
        if st.form_submit_button("ΑΠΟΘΗΚΕΥΣΗ", use_container_width=True):
            supabase.table("inventory").upsert({"barcode": b, "name": n, "price": p, "stock": s}).execute()
            st.rerun()
    res = supabase.table("inventory").select("*").execute()
    if res.data: st.dataframe(pd.DataFrame(res.data)[['barcode', 'name', 'price', 'stock']], use_container_width=True, hide_index=True)

elif view == "👥 ΠΕΛΑΤΕΣ":
    res = supabase.table("customers").select("*").execute()
    if res.data: st.dataframe(pd.DataFrame(res.data)[['name', 'phone']], use_container_width=True, hide_index=True)
