import pandas as pd
from datetime import datetime, date, timedelta
import time
import streamlit as st
from supabase import create_client, Client
import re

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

# --- 3. CONFIG & STYLE (Version v14.2.71) ---
st.set_page_config(page_title="CHERRY v14.2.71", layout="wide", page_icon="🍒")

# Σπάσιμο του CSS σε μικρότερα κομμάτια για αποφυγή σφαλμάτων
css_code = """
<style>
.stApp { background-color: #1a1a1a; color: white; }
label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; }
.cart-area { 
    font-family: monospace; background-color: #000; padding: 15px; border-radius: 10px; 
    border: 4px solid #2ecc71; color: #2ecc71; min-height: 300px; 
}
.total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; }
.report-stat { background-color: #262730; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #444; }
.stat-val { font-size: 22px; font-weight: bold; color: #2ecc71; }
.data-row { background-color: #262626; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; }
</style>
"""
st.markdown(css_code, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'is_logged_out' not in st.session_state: st.session_state.is_logged_out = False
if 'mic_key' not in st.session_state: st.session_state.mic_key = 28000
if 'return_mode' not in st.session_state: st.session_state.return_mode = False

# --- 4. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.return_mode = False
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1
    st.rerun()

@st.dialog("👤 Νέος Πελάτης")
def new_customer_popup(phone):
    st.write(f"Το τηλέφωνο **{phone}** δεν υπάρχει.")
    name = st.text_input("Ονοματεπώνυμο")
    if st.button("Καταχώρηση", use_container_width=True):
        if name:
            try:
                res = supabase.table("customers").insert({"name": name.upper(), "phone": phone}).execute()
                if res.data:
                    st.session_state.selected_cust_id = res.data[0]['id']
                    st.session_state.cust_name = res.data[0]['name']
                    st.success("Έτοιμο!"); time.sleep(1); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

@st.dialog("⚠️ Διαγραφή")
def confirm_delete_customer(c_id, c_name):
    st.subheader("⚠️ Διαγραφή")
    st.write(f"Διαγραφή του ΠΕΛΑΤΗ: **{c_name}**;")
    if st.button("ΝΑΙ, Διαγραφή", use_container_width=True, type="primary"):
        try:
            supabase.table("customers").delete().eq("id", c_id).execute()
            st.success("Διαγράφηκε"); time.sleep(1); st.rerun()
        except Exception as e: st.error(f"Σφάλμα: {e}")

def finalize(disc_val, method):
    if not supabase: return
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    try:
        for i in st.session_state.cart:
            d = round(i['price'] * ratio, 2)
            f = round(i['price'] - d, 2)
            data = {"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), 
                    "discount": float(d), "final_item_price": float(f), "method": str(method), 
                    "s_date": ts, "cust_id": c_id}
            supabase.table("sales").insert(data).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); time.sleep(1); reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.write(f"Σύνολο: {total:.2f}€")
    inp = st.text_input("Έκπτωση (ποσό ή %)")
    disc = 0.0
    if inp:
        try:
            if "%" in inp: disc = round((float(inp.replace("%",""))/100 * total), 2)
            else: disc = round(float(inp), 2)
        except: pass
    st.subheader(f"ΠΛΗΡΩΤΕΟ: {total-disc:.2f}€")
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

# --- 5. MAIN UI ---
if st.session_state.get('is_logged_out', False):
    if st.button("Είσοδος"): st.session_state.is_logged_out = False; st.rerun()
else:
    with st.sidebar:
        st.write(get_athens_now().strftime('%d/%m/%Y %H:%M'))
        if HAS_MIC:
            t = speech_to_text(language='el', start_prompt="🎙️ ΦΩΝΗ", key=f"v_{st.session_state.mic_key}")
            if t:
                nums = re.findall(r"\d+\.?\d*", t)
                if nums:
                    p = float(nums[0])
                    v = -p if st.session_state.return_mode else p
                    st.session_state.cart.append({'bc':'VOICE','name':t.upper(),'price':v})
                    st.session_state.mic_key += 1; time.sleep(0.3); st.rerun()
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        curr = view if view != "🔄 ΕΠΙΣΤΡΟΦΗ" else "🛒 ΤΑΜΕΙΟ"

    if curr == "🛒 ΤΑΜΕΙΟ":
        st.write(f"👤 {st.session_state.cust_name}")
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"p_{st.session_state.ph_key}")
                if ph and len(ph)==10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data: 
                        st.session_state.selected_cust_id = res.data[0]['id']
                        st.session_state.cust_name = res.data[0]['name']; st.rerun()
                    else: new_customer_popup(ph)
                if st.button("🛒 ΛΙΑΝΙΚΗ"): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                bc = st.text_input("Barcode", key=f"b_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        v = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'bc':bc, 'name':res.data[0]['name'].upper(), 'price':v})
                        st.session_state.bc_key += 1; st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
                if st.button("🔄 ΑΚΥΡΩΣΗ"): reset_app()
        with cr:
            tot = sum(i['price'] for i in st.session_state.cart)
            st.markdown(f"<div class='cart-area'>{len(st.session_state.cart)} είδη στο καλάθι</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{tot:.2f}€</div>", unsafe_allow_html=True)

    elif curr == "📊 MANAGER":
        st.title("📊 Αναφορές")
        res = supabase.table("sales").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            st.metric("Τζίρος", f"{df['final_item_price'].sum():.2f}€")
            st.dataframe(df.sort_index(ascending=False), use_container_width=True)

    elif curr == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Αποθήκη")
        res = supabase.table("inventory").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data), use_container_width=True)

    elif curr == "👥 ΠΕΛΑΤΕΣ":
        st.title("👥 Πελάτες")
        res_c = supabase.table("customers").select("*").execute()
        if res_c.data:
            for r in res_c.data:
                col1, col2 = st.columns([5,1])
                col1.write(f"👤 {r['name']} | 📞 {r['phone']}")
                if col2.button("❌", key=f"del_{r['id']}"): confirm_delete_customer(r['id'], r['name'])
