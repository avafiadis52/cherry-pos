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

# --- 3. CONFIG & STYLE (Version v14.2.50) ---
st.set_page_config(page_title="CHERRY v14.2.50", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; }
    .cart-area { 
        font-family: 'Courier New', monospace; 
        background-color: #000000; padding: 15px; border-radius: 10px; 
        white-space: pre-wrap; border: 4px solid #2ecc71 !important; 
        box-shadow: 0 0 15px rgba(46, 204, 113, 0.4); min-height: 300px; 
        font-size: 16px; color: #2ecc71; 
    }
    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; margin-top: 10px; text-shadow: 2px 2px 10px rgba(46, 204, 113, 0.5); }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; margin-bottom: 10px; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; padding: 10px; border-radius: 10px; background-color: #fff3f0; border: 2px solid #e44d26; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000000 !important; border-radius: 8px !important; font-weight: bold !important; border: 1px solid #808080 !important; }
    .data-row { font-family: 'Courier New', monospace; background-color: #262626; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; display: block; white-space: pre; }
    .sidebar-date { color: #f1c40f; font-size: 18px; font-weight: bold; margin-bottom: 20px; border-bottom: 1px solid #444; padding-bottom: 10px; }
    .report-stat { background-color: #262730; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; }
    .day-header { background-color: #34495e; color: #f1c40f; padding: 10px; border-radius: 5px; margin-top: 25px; margin-bottom: 10px; font-weight: bold; border-left: 8px solid #f1c40f; }
    </style>
    """, unsafe_allow_html=True)

# Session States
for key, val in {'cart':[], 'selected_cust_id':None, 'cust_name':"Λιανική Πώληση", 'bc_key':0, 'ph_key':100, 'is_logged_out':False, 'mic_key':28000, 'return_mode':False}.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 4. FUNCTIONS ---
def get_athens_now(): return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.return_mode = False
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1
    st.rerun()

def switch_to_normal():
    st.session_state.return_mode = False
    if 'sidebar_nav' in st.session_state: st.session_state.sidebar_nav = "🛒 ΤΑΜΕΙΟ"

def speak_text(text_to_say, play_beep=True):
    b_js = "var ctx=new(window.AudioContext||window.webkitAudioContext)();var o=ctx.createOscillator();o.type='sawtooth';o.frequency.setValueAtTime(150,ctx.currentTime);o.connect(ctx.destination);o.start();o.stop(ctx.currentTime+0.2);" if play_beep else ""
    s_js = f"var m=new SpeechSynthesisUtterance('{text_to_say}');m.lang='el-GR';window.speechSynthesis.speak(m);" if text_to_say else ""
    st.components.v1.html(f"<script>{b_js}{s_js}</script>", height=0)

def play_sound(url): st.components.v1.html(f'<audio autoplay style="display:none"><source src="{url}" type="audio/mpeg"></audio>', height=0)

@st.dialog("👤 Νέος Πελάτης")
def new_customer_popup(phone):
    st.write(f"Το τηλέφωνο **{phone}** δεν υπάρχει.")
    name = st.text_input("Ονοματεπώνυμο")
    if st.button("Καταχώρηση", use_container_width=True):
        if name:
            try:
                res = supabase.table("customers").insert({"name": name.upper(), "phone": phone}).execute()
                if res.data:
                    st.session_state.update({"selected_cust_id": res.data[0]['id'], "cust_name": res.data[0]['name']})
                    st.success("Έτοιμο!"); time.sleep(1); st.rerun()
            except Exception as e: st.error(f"Σφάλμα: {e}")

def finalize(disc_val, method):
    if not supabase: return
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    c_id = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    try:
        for i in st.session_state.cart:
            d, f = round(i['price'] * ratio, 2), round(i['price'] - round(i['price'] * ratio, 2), 2)
            supabase.table("sales").insert({"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": float(d), "final_item_price": float(f), "method": str(method), "s_date": ts, "cust_id": c_id}).execute()
            if i['bc'] != 'VOICE':
                res_inv = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
                if res_inv.data:
                    ch = 1 if i['price'] < 0 else -1
                    supabase.table("inventory").update({"stock": int(res_inv.data[0]['stock']) + ch}).eq("barcode", i['bc']).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); st.balloons(); speak_text("Επιτυχής Πληρωμή", False); time.sleep(1.5); reset_app()
    except Exception as e: st.error(f"Σφάλμα: {e}")

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    opt = st.radio("Έκπτωση;", ["ΟΧΙ", "ΝΑΙ"], horizontal=True)
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή %")
        if inp:
            try: disc = round((float(inp.replace("%",""))/100 * total), 2) if "%" in inp else round(float(inp), 2)
            except: st.error("Σφάλμα")
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
            text = speech_to_text(language='el', key=f"voice_{st.session_state.mic_key}")
            if text:
                nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
                if nums:
                    p = float(nums[0])
                    st.session_state.cart.append({'bc': 'VOICE', 'name': text.upper(), 'price': -p if st.session_state.return_mode else p})
                    st.session_state.mic_key += 1; time.sleep(0.4); st.rerun()
        st.divider()
        menu = ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ", "⚙️ SYSTEM"]
        view = st.radio("Μενού", menu, index=1 if st.session_state.return_mode else 0, key="sidebar_nav")
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        curr = view if view != "🔄 ΕΠΙΣΤΡΟΦΗ" else "🛒 ΤΑΜΕΙΟ"
        if st.button("❌ Έξοδος", use_container_width=True): st.session_state.cart = []; st.session_state.is_logged_out = True; st.rerun()

    if curr == "🛒 ΤΑΜΕΙΟ":
        if st.session_state.return_mode:
            st.button("🔄 ΚΑΝΟΝΙΚΟ ΤΑΜΕΙΟ", on_click=switch_to_normal, use_container_width=True)
            st.error("⚠️ ΛΕΙΤΟΥΡΓΙΑ ΕΠΙΣΤΡΟΦΗΣ")
        else: st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"ph_{st.session_state.ph_key}")
                if ph and len(re.sub(r'\D', '', ph)) == 10:
                    res = supabase.table("customers").select("*").eq("phone", re.sub(r'\D', '', ph)).execute()
                    if res.data: st.session_state.update({"selected_cust_id": res.data[0]['id'], "cust_name": res.data[0]['name']}); st.rerun()
                    else: new_customer_popup(re.sub(r'\D', '', ph))
                if st.button("🛒 ΛΙΑΝΙΚΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name}", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc and supabase:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        val = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'bc': res.data[0]['barcode'], 'name': res.data[0]['name'].upper(), 'price': val})
                        st.session_state.bc_key += 1; st.rerun()
                if st.session_state.cart:
                    if st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
            if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            tot = sum(i['price'] for i in st.session_state.cart)
            lines = [f"{i['name'][:20]:20} | {i['price']:>6.2f}€" for i in st.session_state.cart]
            st.markdown(f"<div class='cart-area'>Είδος                | Τιμή\n{'-'*30}\n" + "\n".join(lines) + "</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{tot:.2f}€</div>", unsafe_allow_html=True)

    elif curr == "📊 MANAGER" and supabase:
        res_s = supabase.table("sales").select("*").execute()
        if res_s.data:
            df = pd.DataFrame(res_s.data)
            df['s_date_dt'] = pd.to_datetime(df['s_date'])
            df['ΗΜΕΡΟΜΗΝΙΑ'] = df['s_date_dt'].dt.date
            today_date = get_athens_now().date()
            t1, t2 = st.tabs(["📅 ΣΗΜΕΡΑ", "📆 ΠΕΡΙΟΔΟΣ"])
            with t1:
                tdf = df[df['ΗΜΕΡΟΜΗΝΙΑ'] == today_date]
                st.metric("Τζίρος Ημέρας", f"{tdf['final_item_price'].sum():.2f}€")
                st.dataframe(tdf[['item_name', 'final_item_price', 'method']].sort_index(ascending=False), use_container_width=True)
            with t2:
                sd, ed = st.date_input("Από", today_date-timedelta(days=7)), st.date_input("Έως", today_date)
                pdf = df[(df['ΗΜΕΡΟΜΗΝΙΑ'] >= sd) & (df['ΗΜΕΡΟΜΗΝΙΑ'] <= ed)].sort_values('s_date_dt', ascending=False)
                for d in sorted(pdf['ΗΜΕΡΟΜΗΝΙΑ'].unique(), reverse=True):
                    ddf = pdf[pdf['ΗΜΕΡΟΜΗΝΙΑ'] == d]
                    st.markdown(f"<div class='day-header'>{d} | {ddf['final_item_price'].sum():.2f}€</div>", unsafe_allow_html=True)
                    st.dataframe(ddf[['item_name', 'final_item_price', 'method']], use_container_width=True, hide_index=True)

    elif curr == "📦 ΑΠΟΘΗΚΗ" and supabase:
        st.title("📦 Αποθήκη")
        c1, c2, c3, c4 = st.columns(4)
        b, n, p, s = c1.text_input("BC"), c2.text_input("Όνομα"), c3.number_input("Τιμή", 0.0), c4.number_input("Stock", 0)
        if st.button("Προσθήκη", use_container_width=True):
            if b and n:
                supabase.table("inventory").upsert({"barcode": str(b), "name": n.upper(), "price": float(p), "stock": int(s)}).execute()
                st.success("Αποθηκεύτηκε!"); time.sleep(0.5); st.rerun()
        res = supabase.table("inventory").select("*").execute()
        if res.data:
            for r in res.data:
                col1, col2 = st.columns([5, 1])
                col1.markdown(f"<div class='data-row'>{r['barcode']} | {r['name']} | {r['price']}€ | Stock: {r['stock']}</div>", unsafe_allow_html=True)
                if col2.button("❌", key=f"inv_{r['barcode']}"):
                    supabase.table("inventory").delete().eq("barcode", r['barcode']).execute(); st.rerun()

    elif curr == "👥 ΠΕΛΑΤΕΣ" and supabase:
        st.title("👥 Πελάτες")
        res_c = supabase.table("customers").select("*").execute()
        if res_c.data:
            for r in res_c.data:
                col1, col2 = st.columns([5, 1])
                col1.markdown(f"<div class='data-row'>👤 {r['name']} | 📞 {r['phone']}</div>", unsafe_allow_html=True)
                if col2.button("❌", key=f"c_{r['id']}"):
                    supabase.table("customers").delete().eq("id", r['id']).execute(); st.rerun()

    elif curr == "⚙️ SYSTEM" and supabase:
        st.title("⚙️ SYSTEM")
        if st.text_input("Κωδικός", type="password") == "999":
            target = st.selectbox("Επιλέξτε Πίνακα", ["---", "Sales", "Customers", "Inventory"])
            if target != "---":
                st.warning(f"⚠️ ΠΡΟΣΟΧΗ: Η διαγραφή του πίνακα {target} είναι οριστική!")
                if st.text_input("Γράψτε ΔΙΑΓΡΑΦΗ") == "ΔΙΑΓΡΑΦΗ":
                    if st.button("🚀 ΕΚΤΕΛΕΣΗ"):
                        supabase.table(target.lower()).delete().neq("id", -1).execute()
                        st.success("Έγινε!"); time.sleep(1); st.rerun()
        else: st.error("🔒 Απαιτείται κωδικός.")
