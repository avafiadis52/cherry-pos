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

# --- 3. CONFIG & STYLE (Version v14.3.01) ---
st.set_page_config(page_title="CHERRY v14.3.01", layout="wide", page_icon="🍒")

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
    .data-row { background-color: #262626; padding: 15px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; display: flex; justify-content: space-between; align-items: center; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    .report-stat { background-color: #262730; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; }
    .day-header { background-color: #34495e; color: #f1c40f; padding: 5px 10px; border-radius: 5px; margin-top: 20px; margin-bottom: 10px; font-weight: bold; border-left: 5px solid #f1c40f; }
    </style>
    """, unsafe_allow_html=True)

# Session States
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'is_logged_out' not in st.session_state: st.session_state.is_logged_out = False
if 'mic_key' not in st.session_state: st.session_state.mic_key = 28000

# --- 4. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1
    st.rerun()

def speak_text(text_to_say, play_beep=True):
    beep_js = """
    var context = new (window.AudioContext || window.webkitAudioContext)();
    var osc = context.createOscillator();
    osc.type = 'sawtooth'; osc.frequency.setValueAtTime(150, context.currentTime);
    osc.connect(context.destination); osc.start(); osc.stop(context.currentTime + 0.2);
    """ if play_beep else ""
    speech_js = f"var msg = new SpeechSynthesisUtterance('{text_to_say}'); msg.lang = 'el-GR'; window.speechSynthesis.speak(msg);" if text_to_say else ""
    st.components.v1.html(f"<script>{beep_js}{speech_js}</script>", height=0)

@st.dialog("👤 Νέος Πελάτης")
def new_customer_popup(phone):
    st.write(f"Το τηλέφωνο **{phone}** δεν υπάρχει στη βάση.")
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
            except Exception as e: st.error(f"Σφάλμα: {e}")
        else: st.warning("Παρακαλώ δώστε όνομα.")

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
            data = {"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": float(d), "final_item_price": float(f), "method": str(method), "s_date": ts, "cust_id": c_id}
            supabase.table("sales").insert(data).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); st.balloons()
        speak_text("Επιτυχής Πληρωμή", play_beep=False)
        time.sleep(1.5); reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    opt = st.radio("Έκπτωση;", ["ΟΧΙ", "ΝΑΙ"], horizontal=True)
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή % (π.χ. 5 ή 10%)")
        if inp:
            try:
                if "%" in inp: disc = round((float(inp.replace("%",""))/100 * total), 2)
                else: disc = round(float(inp), 2)
            except: st.error("Λάθος μορφή")
    st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {total-disc:.2f}€</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

# --- 5. MAIN UI ---
if st.session_state.is_logged_out:
    st.markdown("<h1 style='text-align:center;color:#e74c3c;'>Αποσυνδεθήκατε</h1>", unsafe_allow_html=True)
    if st.button("Επανασύνδεση"): st.session_state.is_logged_out = False; st.rerun()
else:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-date'>{get_athens_now().strftime('%d/%m/%Y %H:%M:%S')}</div>", unsafe_allow_html=True)
        if HAS_MIC:
            text = speech_to_text(language='el', start_prompt="🔴 ΦΩΝΗΤΙΚΗ ΠΩΛΗΣΗ", just_once=True, key=f"voice_{st.session_state.mic_key}")
            if text:
                nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
                if nums:
                    st.session_state.cart.append({'bc': 'VOICE', 'name': text.upper(), 'price': float(nums[0])})
                    st.session_state.mic_key += 1; time.sleep(0.4); st.rerun()
        st.divider()
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ"])
        if st.button("❌ Έξοδος", use_container_width=True): st.session_state.cart = []; st.session_state.is_logged_out = True; st.rerun()

    if view == "🛒 ΤΑΜΕΙΟ":
        st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
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
                st.button(f"👤 {st.session_state.cust_name}", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data: 
                        st.session_state.cart.append({'bc': res.data[0]['barcode'], 'name': res.data[0]['name'], 'price': float(res.data[0]['price'])})
                        st.session_state.bc_key += 1; st.rerun()
                    else: speak_text("Όχι"); st.error("Δεν βρέθηκε!"); time.sleep(1); st.session_state.bc_key += 1; st.rerun()
                for idx, item in enumerate(st.session_state.cart):
                    if st.button(f"❌ {item['name']} {item['price']}€", key=f"del_{idx}", use_container_width=True): st.session_state.cart.pop(idx); st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
            if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            lines = [f"{i['name'][:20]:<20} | {i['price']:>6.2f}€" for i in st.session_state.cart]
            st.markdown(f"<div class='cart-area'>{'Είδος':<20} | {'Τιμή':>6}\n{'-'*30}\n{chr(10).join(lines)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif view == "📦 ΑΠΟΘΗΚΗ":
        st.title("📦 Διαχείριση Αποθήκης (Re-engineered)")
        
        # 1. Φόρμα Καταχώρησης (Upsert)
        with st.expander("🆕 Προσθήκη / Ενημέρωση Είδους", expanded=True):
            with st.form("inv_form", clear_on_submit=True):
                c1, c2, c3, c4 = st.columns([2,3,1,1])
                new_bc = c1.text_input("Barcode *")
                new_name = c2.text_input("Όνομα Είδους *")
                new_price = c3.number_input("Τιμή €", min_value=0.0, step=0.1)
                new_stock = c4.number_input("Stock", min_value=0, step=1)
                
                if st.form_submit_button("ΑΠΟΘΗΚΕΥΣΗ ΣΤΗ ΒΑΣΗ", use_container_width=True):
                    if new_bc and new_name:
                        try:
                            # Χρήση upsert: Αν υπάρχει το barcode, κάνει update. Αν όχι, κάνει insert.
                            supabase.table("inventory").upsert({
                                "barcode": str(new_bc).strip(),
                                "name": str(new_name).upper().strip(),
                                "price": float(new_price),
                                "stock": int(new_stock)
                            }).execute()
                            st.success(f"✅ Το είδος '{new_name}' αποθηκεύτηκε επιτυχώς!")
                            time.sleep(1); st.rerun()
                        except Exception as e:
                            st.error(f"❌ Σφάλμα κατά την αποθήκευση: {e}")
                    else:
                        st.warning("⚠️ Τα πεδία Barcode και Όνομα είναι υποχρεωτικά!")

        st.divider()

        # 2. Αναζήτηση & Λίστα
        res = supabase.table("inventory").select("*").execute()
        if res.data:
            df_inv = pd.DataFrame(res.data)
            
            # Φίλτρα Αναζήτησης
            sc1, sc2 = st.columns(2)
            search_name = sc1.text_input("🔍 Αναζήτηση με Όνομα", placeholder="π.χ. ΠΑΝΤΕΛΟΝΙ...")
            search_bc = sc2.text_input("🔢 Αναζήτηση με Barcode", placeholder="π.χ. 520...")

            # Εφαρμογή Φίλτρων
            filtered_df = df_inv.copy()
            if search_name:
                filtered_df = filtered_df[filtered_df['name'].str.contains(search_name.upper(), na=False)]
            if search_bc:
                filtered_df = filtered_df[filtered_df['barcode'].str.contains(search_bc, na=False)]
            
            filtered_df = filtered_df.sort_values(by='name')

            st.write(f"Εμφανίζονται **{len(filtered_df)}** είδη")
            
            # Προβολή Λίστας
            for _, r in filtered_df.iterrows():
                with st.container():
                    st.markdown(f"""
                        <div class='data-row'>
                            <div>
                                <b>{r['name']}</b><br>
                                <small>BC: {r['barcode']} | Stock: {r['stock']}</small>
                            </div>
                            <div style='font-size: 1.2rem; font-weight: bold; color: #2ecc71;'>{r['price']:.2f}€</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Κουμπί Διαγραφής (κάτω από κάθε row για ευκολία)
                    if st.button(f"Διαγραφή {r['barcode']}", key=f"del_bc_{r['barcode']}", type="secondary", use_container_width=False):
                        try:
                            supabase.table("inventory").delete().eq("barcode", r['barcode']).execute()
                            st.toast(f"Διαγράφηκε το {r['barcode']}")
                            time.sleep(0.5); st.rerun()
                        except Exception as e:
                            st.error(f"Σφάλμα διαγραφής: {e}")
        else:
            st.info("Η αποθήκη είναι άδεια. Καταχωρήστε το πρώτο σας προϊόν!")

    elif view == "📊 MANAGER" and supabase:
        st.title("📊 Αναφορές")
        res_s = supabase.table("sales").select("*").execute()
        if res_s.data:
            df = pd.DataFrame(res_s.data)
            df['s_date_dt'] = pd.to_datetime(df['s_date'])
            df['ΗΜΕΡΟΜΗΝΙΑ'] = df['s_date_dt'].dt.date
            today = get_athens_now().date()
            tdf = df[df['ΗΜΕΡΟΜΗΝΙΑ'] == today]
            st.markdown(f"<div class='report-stat'>ΤΖΙΡΟΣ ΣΗΜΕΡΑ<div class='stat-val'>{tdf['final_item_price'].sum():.2f}€</div></div>", unsafe_allow_html=True)
            st.dataframe(tdf, use_container_width=True)

    elif view == "👥 ΠΕΛΑΤΕΣ" and supabase:
        st.title("👥 Πελάτες")
        res = supabase.table("customers").select("*").execute()
        if res.data:
            st.dataframe(pd.DataFrame(res.data), use_container_width=True)
