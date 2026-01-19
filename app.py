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
st.set_page_config(page_title="CHERRY v13.1", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    .cart-area { font-family: 'Courier New', monospace; background-color: #2b2b2b; padding: 15px; border-radius: 5px; white-space: pre-wrap; border: 1px solid #3b3b3b; min-height: 200px; font-size: 14px; }
    .total-label { font-size: 60px; font-weight: bold; color: #2ecc71; text-align: center; }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #f1c40f; text-align: center; margin: 10px 0; border: 2px solid #f1c40f; padding: 10px; border-radius: 10px; }
    .report-stat { background-color: #262730; padding: 10px; border-radius: 10px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; margin: 0; }
    .stat-label { font-size: 12px; color: #888; margin: 0; }
    @media (max-width: 640px) {
        .total-label { font-size: 45px; }
        .stButton>button { height: 3.5em; font-size: 16px !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'audio_enabled' not in st.session_state: st.session_state.audio_enabled = False

# --- 3. FUNCTIONS ---
def trigger_alert_sound():
    sound_url = "https://www.soundjay.com/buttons/beep-01a.mp3"
    st.components.v1.html(f"""<script>var audio = new Audio("{sound_url}"); audio.play();</script>""", height=0)

@st.dialog("👤 ΝΕΟΣ ΠΕΛΑΤΗΣ")
def new_customer_popup(phone):
    name = st.text_input("Ονοματεπώνυμο")
    if st.button("ΑΠΟΘΗΚΕΥΣΗ", use_container_width=True):
        res = supabase.table("customers").insert({"name": name, "phone": phone}).execute()
        if res.data:
            st.session_state.selected_cust_id = res.data[0]['id']
            st.session_state.cust_name = name
            st.rerun()

@st.dialog("💰 ΠΛΗΡΩΜΗ")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center; color: #888;'>Σύνολο: {total:.1f}€</h3>", unsafe_allow_html=True)
    opt = st.radio("Έκπτωση;", ["ΕΠΙΛΟΞΤΕ", "ΟΧΙ", "ΝΑΙ"], horizontal=True)
    disc = 0.0
    show_final = False
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή % (π.χ. 10%):")
        if inp:
            try:
                if "%" in inp: disc = round((float(inp.replace("%",""))/100 * total), 1)
                else: disc = round(float(inp or 0), 1)
                show_final = True
            except: pass
    elif opt == "ΟΧΙ": show_final = True
    if show_final:
        trigger_alert_sound()
        final_p = round(total - disc, 1)
        st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {final_p:.1f}€</div>", unsafe_allow_html=True)
        st.divider()
        c1, c2 = st.columns(2)
        if c1.button("💵 ΜΕΤΡΗΤΑ", use_container_width=True): finalize(disc, "Μετρητά")
        if c2.button("💳 ΚΑΡΤΑ", use_container_width=True): finalize(disc, "Κάρτα")

def finalize(disc_val, method):
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for i in st.session_state.cart:
        d = round(i['price'] * ratio, 1)
        f = round(i['price'] - d, 1)
        # Χρησιμοποιούμε None αντί για 0 για την Λιανική για να αποφύγουμε λάθη σύνδεσης
        c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
        supabase.table("sales").insert({
            "barcode": i['bc'], "item_name": i['name'], "unit_price": i['price'],
            "discount": d, "final_item_price": f, "method": method, 
            "s_date": ts, "cust_id": c_id
        }).execute()
        res = supabase.table("inventory").select("stock").eq("barcode", i['bc']).single().execute()
        if res.data:
            new_stock = res.data['stock'] - 1
            supabase.table("inventory").update({"stock": new_stock}).eq("barcode", i['bc']).execute()
    st.success("✅ ΟΛΟΚΛΗΡΩΘΗΚΕ!")
    time.sleep(0.8)
    st.session_state.cart, st.session_state.selected_cust_id, st.session_state.cust_name = [], None, "Λιανική Πώληση"
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.rerun()

# --- 4. MAIN UI ---
with st.sidebar:
    st.title("CHERRY 13.1")
    if not st.session_state.audio_enabled:
        if st.button("🔔 ΕΝΕΡΓΟΠΟΙΗΣΗ ΗΧΟΥ", use_container_width=True):
            st.session_state.audio_enabled = True; trigger_alert_sound(); st.rerun()
    view = st.radio("ΜΕΝΟΥ", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])

if view == "🛒 ΤΑΜΕΙΟ":
    st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
    cl, cr = st.columns([1, 1.5])
    with cl:
        if st.session_state.selected_cust_id is None:
            ph = st.text_input("📞 Τηλέφωνο", key=f"ph_{st.session_state.ph_key}")
            if ph:
                res = supabase.table("customers").select("*").eq("phone", ph.strip()).execute()
                if res.data: 
                    st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']
                    st.rerun()
                else: new_customer_popup(ph.strip())
            if st.button("🛒 ΛΙΑΝΙΚΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
        else:
            st.button(f"👤 {st.session_state.cust_name} (Αλλαγή)", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
            bc = st.text_input("🏷️ Barcode", key=f"bc_{st.session_state.bc_key}")
            if bc:
                res = supabase.table("inventory").select("*").eq("barcode", bc.strip()).execute()
                if res.data:
                    item = res.data[0]
                    st.session_state.cart.append({'bc': item['barcode'], 'name': item['name'], 'price': round(float(item['price']), 1)})
                    if item['stock'] <= 0: trigger_alert_sound(); st.error(f"⚠️ STOCK: {item['stock']}")
                    st.session_state.bc_key += 1; st.rerun()
                else: trigger_alert_sound(); st.session_state.bc_key += 1; st.rerun()
            for idx, item in enumerate(st.session_state.cart):
                if st.button(f"❌ {item['name']} ({item['price']}€)", key=f"del_{idx}", use_container_width=True):
                    st.session_state.cart.pop(idx); st.rerun()
            if st.session_state.cart:
                if st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
        if st.button("🗑️ ΑΚΥΡΩΣΗ", use_container_width=True):
            st.session_state.cart, st.session_state.selected_cust_id, st.session_state.cust_name = [], None, "Λιανική Πώληση"
            st.session_state.bc_key += 1; st.rerun()
    with cr:
        total = sum(i['price'] for i in st.session_state.cart)
        lines = [f"{i['name'][:20]:<20} | {i['price']:>6.1f}€" for i in st.session_state.cart]
        st.markdown(f"<div class='cart-area'>{'ΕΙΔΟΣ':<20} | {'ΤΙΜΗ':>6}\n{'-'*30}\n{chr(10).join(lines)}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='total-label'>{total:.1f}€</div>", unsafe_allow_html=True)

elif view == "📊 MANAGER":
    st.header("📊 Πωλήσεις")
    # Απλοποιημένο query για αποφυγή σφαλμάτων API
    res = supabase.table("sales").select("*").execute()
    if res.data:
        df = pd.DataFrame(res.data)
        df['s_date_dt'] = pd.to_datetime(df['s_date'])
        
        # Φίλτρο Σημερινών
        today_df = df[df['s_date_dt'].dt.date == date.today()]
        m_sum = today_df[today_df['method'] == 'Μετρητά']['final_item_price'].sum()
        k_sum = today_df[today_df['method'] == 'Κάρτα']['final_item_price'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='report-stat'><p class='stat-label'>💵 ΜΕΤΡΗΤΑ (ΣΗΜΕΡΑ)</p><p class='stat-val'>{m_sum:.1f}€</p></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='report-stat'><p class='stat-label'>💳 ΚΑΡΤΑ (ΣΗΜΕΡΑ)</p><p class='stat-val'>{k_sum:.1f}€</p></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='report-stat'><p class='stat-label'>✅ ΣΥΝΟΛΟ (ΣΗΜΕΡΑ)</p><p class='stat-val'>{m_sum+k_sum:.1f}€</p></div>", unsafe_allow_html=True)
        
        st.dataframe(df[['s_date', 'item_name', 'final_item_price', 'method']].sort_values('s_date', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Δεν βρέθηκαν πωλήσεις.")

elif view == "📦 ΑΠΟΘΗΚΗ":
    st.header("📦 Αποθέματα")
    with st.form("inv", clear_on_submit=True):
        b, n, p, s = st.text_input("Barcode"), st.text_input("Όνομα"), st.number_input("Τιμή", step=0.5), st.number_input("Stock", step=1)
        if st.form_submit_button("ΑΠΟΘΗΚΕΥΣΗ", use_container_width=True):
            supabase.table("inventory").upsert({"barcode": b, "name": n, "price": p, "stock": s}).execute()
            st.success("Το προϊόν αποθηκεύτηκε!"); st.rerun()
    res = supabase.table("inventory").select("*").execute()
    if res.data:
        st.dataframe(pd.DataFrame(res.data)[['barcode', 'name', 'price', 'stock']], use_container_width=True, hide_index=True)

elif view == "👥 ΠΕΛΑΤΕΣ":
    st.header("👥 Λίστα Πελατών")
    res = supabase.table("customers").select("*").execute()
    if res.data:
        st.dataframe(pd.DataFrame(res.data)[['name', 'phone']], use_container_width=True, hide_index=True)
