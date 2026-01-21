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
st.set_page_config(page_title="CHERRY v14.0.49", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { 
        color: #000000 !important; 
        font-family: 'Courier New', monospace !important; 
        font-size: 1.5rem !important; 
        font-weight: bold !important;
    }
    .cart-area { font-family: 'Courier New', monospace; background-color: #2b2b2b; padding: 15px; border-radius: 5px; white-space: pre-wrap; border: 1px solid #3b3b3b; min-height: 250px; font-size: 16px; }
    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; margin-top: 10px; }
    .status-header { font-size: 22px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; border-bottom: 1px solid #333; padding-bottom: 5px; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; border: 1px solid #ffffff !important; font-weight: bold !important; height: 3em !important; }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'is_logged_out' not in st.session_state: st.session_state.is_logged_out = False

# --- 3. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart = []
    st.session_state.selected_cust_id = None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1
    st.session_state.ph_key += 1
    st.rerun()

def play_sound(url):
    st.components.v1.html(f'<audio autoplay style="display:none"><source src="{url}" type="audio/mpeg"></audio>', height=0)

@st.dialog("👤 Νέος Πελάτης")
def new_customer_popup(phone=""):
    st.write(f"📞 Τηλέφωνο: {phone}")
    name = st.text_input("Ονοματεπώνυμο Πελάτη")
    if st.button("Αποθήκευση & Επιλογή", use_container_width=True):
        if name:
            res = supabase.table("customers").insert({"name": name, "phone": phone}).execute()
            if res.data:
                st.session_state.selected_cust_id = res.data[0]['id']
                st.session_state.cust_name = res.data[0]['name']
                st.success("Ο πελάτης αποθηκεύτηκε!")
                time.sleep(0.5)
                st.rerun()

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center; color: #111;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize("Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize("Κάρτα")

def finalize(method):
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    try:
        for i in st.session_state.cart:
            supabase.table("sales").insert({
                "barcode": str(i['bc']), "item_name": str(i['name']), 
                "unit_price": float(i['price']), "discount": 0, 
                "final_item_price": float(i['price']), "method": str(method), 
                "s_date": ts, "cust_id": c_id
            }).execute()
        st.balloons()
        play_sound("https://www.soundjay.com/misc/sounds/magic-chime-01.mp3")
        time.sleep(1.5)
        reset_app()
    except Exception as e:
        st.error(f"Σφάλμα: {e}")

# --- 4. MAIN UI ---
if st.session_state.is_logged_out:
    st.warning("Είστε αποσυνδεδεμένοι από το σύστημα.")
    if st.button("Είσοδος"):
        st.session_state.is_logged_out = False
        st.rerun()
else:
    with st.sidebar:
        st.title("🍒 CHERRY POS")
        st.write(get_athens_now().strftime("%d/%m/%Y %H:%M"))
        view = st.radio("ΜΕΝΟΥ", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "👥 ΠΕΛΑΤΕΣ"])
        if st.button("❌ ΕΞΟΔΟΣ", use_container_width=True):
            st.session_state.is_logged_out = True
            st.rerun()

    if view == "🛒 ΤΑΜΕΙΟ":
        st.markdown(f"<div class='status-header'>ΠΕΛΑΤΗΣ: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
        cl, cr = st.columns([1, 1.5])
        
        with cl:
            if st.session_state.selected_cust_id is None:
                # Τηλέφωνο με 10 παύλες στο Placeholder
                ph_input = st.text_input("Τηλέφωνο Πελάτη", placeholder="----------", key=f"ph_in_{st.session_state.ph_key}")
                
                if ph_input:
                    clean_phone = "".join([c for c in ph_input if c.isdigit()])
                    if len(clean_phone) == 10:
                        res = supabase.table("customers").select("*").eq("phone", clean_phone).execute()
                        if res.data: 
                            st.session_state.selected_cust_id = res.data[0]['id']
                            st.session_state.cust_name = res.data[0]['name']
                            st.rerun()
                        else:
                            new_customer_popup(clean_phone)
                    else:
                        play_sound("https://www.soundjay.com/buttons/beep-10.mp3")
                        st.error("⚠️ Απαιτούνται ακριβώς 10 ψηφία!")
                
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True):
                    st.session_state.selected_cust_id = 0
                    st.rerun()
            else:
                if st.button(f"👤 {st.session_state.cust_name} (Αλλαγή)", use_container_width=True):
                    st.session_state.selected_cust_id = None
                    st.session_state.cust_name = "Λιανική Πώληση"
                    st.rerun()

                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc.strip()).execute()
                    if res.data:
                        st.session_state.cart.append({
                            'bc': res.data[0]['barcode'], 'name': res.data[0]['name'], 'price': float(res.data[0]['price'])
                        })
                        st.session_state.bc_key += 1
                        st.rerun()
                    else:
                        play_sound("https://www.soundjay.com/buttons/beep-10.mp3")
                        st.error("Το προϊόν δεν βρέθηκε!")

                if st.session_state.cart:
                    if st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True):
                        payment_popup()
                
                if st.button("🗑️ ΑΚΥΡΩΣΗ", use_container_width=True):
                    reset_app()

        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            cart_display = "\n".join([f"{i['name'][:20]:<20} | {i['price']:>7.2f}€" for i in st.session_state.cart])
            if not cart_display: cart_display = "Το καλάθι είναι άδειο..."
            
            st.markdown(f"<div class='cart-area'>{cart_display}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif view == "📊 MANAGER":
        st.header("Ιστορικό Πωλήσεων")
        res = supabase.table("sales").select("*").order("s_date", desc=True).execute()
        if res.data: st.dataframe(pd.DataFrame(res.data), use_container_width=True)

    elif view == "👥 ΠΕΛΑΤΕΣ":
        st.header("Πελάτες")
        res = supabase.table("customers").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data), use_container_width=True)
