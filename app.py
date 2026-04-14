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

# --- 3. CONFIG & STYLE (Version v14.7.2) ---
st.set_page_config(page_title="CHERRY v14.7.2", layout="wide", page_icon="🍒")

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
    .stat-desc { font-size: 13px; color: #888; }
    .day-header { background-color: #34495e; color: #f1c40f; padding: 10px; border-radius: 5px; margin-top: 25px; margin-bottom: 10px; font-weight: bold; border-left: 8px solid #f1c40f; }
    </style>
    """, unsafe_allow_html=True)

# Default Lists Definition
DEFAULT_LISTS = {
    "Είδη": ["Ζακέτα", "Ζώνη", "Μπλούζα", "Μπουφάν / Παλτό", "Παντελόνι", "Πουκάμισο", "Φόρεμα", "Φούστα"],
    "Προμηθευτές": ["ONADO", "PINUP", "ΡΕΝΑ", "ΣΤΕΛΛΑ", "ΤΖΕΝΗ"],
    "Χρώματα": ["Γκρι", "Εκρού", "Εμπριμέ", "Καφέ", "Κίτρινο", "Κόκκινο", "Λευκό", "Μαύρο", "Μπεζ", "Μπλε", "Πουά", "Πράσινο", "Ριγέ", "Σιέλ"],
    "Μεγέθη": ["One Size", "Small", "Medium", "Large", "XL", "XXL", "36", "38", "40", "42", "44"],
    "Συνθέσεις": ["100% Βαμβάκι", "100% Πολυέστερ", "70% Βαμβάκι - 30% Πολυέστερ", "98% Βαμβάκι - 2% Ελαστάνη", "100% Δέρμα", "Τεχνητό Δέρμα (PU)"]
}

def save_master_lists():
    if supabase:
        try:
            supabase.table("inventory_settings").upsert({"config_name": "master_lists", "config_value": st.session_state.master_lists}).execute()
            return True
        except: return False

def sync_master_lists(force=False):
    if 'master_lists' in st.session_state and not force: return
    if supabase:
        try:
            res = supabase.table("inventory_settings").select("config_value").eq("config_name", "master_lists").execute()
            if res.data:
                remote_data = res.data[0]['config_value']
                for key, val in DEFAULT_LISTS.items():
                    if key not in remote_data: remote_data[key] = val
                st.session_state.master_lists = remote_data
            else:
                st.session_state.master_lists = DEFAULT_LISTS.copy()
                save_master_lists()
        except:
            if 'master_lists' not in st.session_state: st.session_state.master_lists = DEFAULT_LISTS.copy()

# Session States
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'cart' not in st.session_state: st.session_state.cart = []
if 'selected_cust_id' not in st.session_state: st.session_state.selected_cust_id = None
if 'cust_name' not in st.session_state: st.session_state.cust_name = "Λιανική Πώληση"
if 'bc_key' not in st.session_state: st.session_state.bc_key = 0
if 'ph_key' not in st.session_state: st.session_state.ph_key = 100
if 'mic_key' not in st.session_state: st.session_state.mic_key = 28000
if 'return_mode' not in st.session_state: st.session_state.return_mode = False

sync_master_lists()

def get_athens_now(): return datetime.now() + timedelta(hours=2)

def generate_latin_code(text):
    char_map = {'Α':'A','Β':'B','Γ':'G','Δ':'D','Ε':'E','Ζ':'Z','Η':'H','Θ':'TH','Ι':'I','Κ':'K','Λ':'L','Μ':'M','Ν':'N','Ξ':'X','Ο':'O','Π':'P','Ρ':'R','Σ':'S','Τ':'T','Υ':'Y','Φ':'F','Χ':'CH','Ψ':'PS','Ω':'O','Ά':'A','Έ':'E','Ή':'H','Ί':'I','Ό':'O','Ύ':'Y','Ώ':'O','Ϊ':'I','Ϋ':'Y'}
    res = "".join([char_map.get(c, c) for c in str(text).upper()])
    return res if len(res) <= 3 else res[:3]

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.return_mode = False
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1
    st.rerun()

def switch_to_normal():
    st.session_state.return_mode = False
    if 'sidebar_nav' in st.session_state: st.session_state.sidebar_nav = "🛒 ΤΑΜΕΙΟ"

def play_sound(url):
    st.components.v1.html(f'<audio autoplay style="display:none"><source src="{url}" type="audio/mpeg"></audio>', height=0)

@st.dialog("🏷️ Εκτύπωση Ετικέτας")
def print_label_popup(bc, name, price):
    st.write("Προεπισκόπηση Ετικέτας:")
    try:
        char_map = {'Α':'A','Β':'B','Γ':'G','Δ':'D','Ε':'E','Ζ':'Z','Η':'H','Θ':'TH','Ι':'I','Κ':'K','Λ':'L','Μ':'M','Ν':'N','Ξ':'X','Ο':'O','Π':'P','Ρ':'R','Σ':'S','Τ':'T','Υ':'Y','Φ':'F','Χ':'CH','Ψ':'PS','Ω':'O','Ά':'A','Έ':'E','Ή':'H','Ί':'I','Ό':'O','Ύ':'Y','Ώ':'O','Ϊ':'I','Ϋ':'Y'}
        clean_bc = "".join([char_map.get(c, c) for c in str(bc).upper()])
        CODE128 = barcode.get_barcode_class('code128')
        writer_options = {"write_text": False, "module_height": 5.0}
        my_barcode = CODE128(clean_bc, writer=ImageWriter())
        buffer = io.BytesIO()
        my_barcode.write(buffer, options=writer_options)
        b64 = base64.b64encode(buffer.getvalue()).decode()
        barcode_img_html = f'<img src="data:image/png;base64,{b64}" style="width: 230px; height: 50px;">'
    except Exception as e: barcode_img_html = f'<div style="color:red; font-size:10px;">Σφάλμα: {e}</div>'
    parts = bc.split('-')
    label_html = f"""
    <div id="printable-label" style="width: 280px; border: 1px solid #ccc; padding: 15px; text-align: center; background-color: white; color: black; font-family: Arial;">
        <div style="font-size: 14px; font-weight: bold; margin-bottom: 2px;">CHERRY</div>
        <div style="font-size: 11px; font-weight: bold; margin-bottom: 3px;">{re.sub(r'\(.*?\)', '', name).strip()}</div>
        <div style="font-size: 9px; color: #333; margin-bottom: 5px;">Προμ: {parts[1] if len(parts)>1 else "---"} | Σχέδιο: {parts[2] if len(parts)>2 else "---"}</div>
        <div style="margin: 5px 0;">{barcode_img_html}<div style="font-size: 10px; font-family: monospace; font-weight: bold;">{bc}</div></div>
        <div style="font-size: 22px; font-weight: bold; border-top: 1px solid black; padding-top: 5px;">{price:.2f}€</div>
    </div>
    """
    st.markdown(label_html, unsafe_allow_html=True)
    if st.button("🖨️ ΕΚΤΥΠΩΣΗ", use_container_width=True):
        st.components.v1.html(f"<script>var win = window.open('', '', 'height=500,width=500'); win.document.write('<html><body style=\"margin:0; display:flex; justify-content:center; align-items:center;\">{label_html.replace('border: 1px solid #ccc;', 'border: none;')}</body></html>'); win.document.close(); win.print();</script>", height=0)

@st.dialog("👤 Νέος Πελάτης")
def new_customer_popup(phone):
    st.write(f"Το τηλέφωνο **{phone}** δεν υπάρχει.")
    name = st.text_input("Ονοματεπώνυμο")
    if st.button("Καταχώρηση", use_container_width=True):
        if name:
            try:
                res = supabase.table("customers").insert({"name": name.upper(), "phone": phone}).execute()
                if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
            except Exception as e: st.error(str(e))

def finalize(disc_val, method):
    if not supabase: return
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc_val / sub if sub > 0 else 0
    ts = st.session_state.get('manual_ts', get_athens_now()).strftime("%Y-%m-%d %H:%M:%S")
    try:
        for i in st.session_state.cart:
            d = round(i['price'] * ratio, 2)
            f = round(i['price'] - d, 2)
            supabase.table("sales").insert({"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": float(d), "final_item_price": float(f), "method": str(method), "s_date": ts, "cust_id": st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None}).execute()
            if i['bc'] != 'VOICE':
                res_inv = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
                if res_inv.data: supabase.table("inventory").update({"stock": int(res_inv.data[0]['stock']) + (1 if i['price'] < 0 else -1)}).eq("barcode", i['bc']).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); st.balloons(); play_sound("https://www.soundjay.com/misc/sounds/magic-chime-01.mp3"); time.sleep(1.5); reset_app()
    except Exception as e: st.error(str(e))

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {total:.2f}€</h3>", unsafe_allow_html=True)
    opt = st.radio("Έκπτωση;", ["ΟΧΙ", "ΝΑΙ"], horizontal=True)
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή % (π.χ. 5 ή 10%)")
        if inp:
            try: disc = round((float(inp.replace("%",""))/100 * total), 2) if "%" in inp else round(float(inp), 2)
            except: st.error("Λάθος μορφή")
    st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {round(total - disc, 2):.2f}€</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

@st.dialog("⭐ Loyalty Card")
def show_customer_history(c_id, c_name):
    st.subheader(f"Καρτέλα: {c_name}")
    res = supabase.table("sales").select("*").eq("cust_id", c_id).order("s_date", desc=True).execute()
    if res.data:
        pdf = pd.DataFrame(res.data)
        st.metric("Συνολικές Αγορές", f"{pdf['final_item_price'].sum():.2f}€")
        st.dataframe(pdf[['s_date', 'item_name', 'unit_price', 'final_item_price', 'method']], use_container_width=True, hide_index=True)

# --- LOGIN ---
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<h1 style='text-align:center;'>🔒 CHERRY LOGIN</h1>", unsafe_allow_html=True)
        if st.text_input("Password", type="password") == "CHERRY123":
            if st.button("Είσοδος", use_container_width=True): st.session_state.logged_in = True; st.rerun()
else:
    # --- MAIN UI ---
    with st.sidebar:
        chosen_date = st.date_input("Ημερομηνία", value=get_athens_now().date())
        chosen_time = st.time_input("Ώρα", value=get_athens_now().time())
        st.session_state.manual_ts = datetime.combine(chosen_date, chosen_time)
        st.markdown(f"<div class='sidebar-date'>{st.session_state.manual_ts.strftime('%d/%m/%Y %H:%M:%S')}</div>", unsafe_allow_html=True)
        if HAS_MIC:
            text = speech_to_text(language='el', start_prompt="🔴 ΠΑΤΑ ΚΑΙ ΜΙΛΑ", key=f"v_{st.session_state.mic_key}")
            if text:
                nums = re.findall(r"[-+]?\d*\.\d+|\d+", text)
                if nums:
                    st.session_state.cart.append({'bc': 'VOICE', 'name': text.upper(), 'price': -float(nums[0]) if st.session_state.return_mode else float(nums[0])})
                    st.session_state.mic_key += 1; time.sleep(0.4); st.rerun()
        st.divider()
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ", "⚙️ SYSTEM"], key="sidebar_nav")
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        if st.button("❌ Έξοδος", use_container_width=True): st.session_state.logged_in = False; st.rerun()

    current_view = view if view != "🔄 ΕΠΙΣΤΡΟΦΗ" else "🛒 ΤΑΜΕΙΟ"

    if current_view == "🛒 ΤΑΜΕΙΟ":
        if st.session_state.return_mode: st.button("🔄 ΕΠΙΣΤΡΟΦΗ (ΠΑΤΗΣΤΕ ΓΙΑ ΚΑΝΟΝΙΚΟ)", on_click=switch_to_normal, use_container_width=True)
        else: st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο (10 ψηφία)", key=f"ph_{st.session_state.ph_key}")
                if ph and len(ph) == 10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                    else: new_customer_popup(ph)
                if st.button("🛒 ΛΙΑΝΙΚΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name}", on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data: st.session_state.cart.append({'bc': res.data[0]['barcode'], 'name': res.data[0]['name'].upper(), 'price': -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])}); st.session_state.bc_key += 1; st.rerun()
                for idx, item in enumerate(st.session_state.cart):
                    if st.button(f"❌ {item['name']} {item['price']}€", key=f"del_{idx}", use_container_width=True): st.session_state.cart.pop(idx); st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
            if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            st.markdown("<div class='cart-area'>{}</div>".format('\n'.join(["{:45} | {:>4.2f}€".format(i['name'][:45], i['price']) for i in st.session_state.cart])), unsafe_allow_html=True)
            st.markdown("<div class='total-label'>{:.2f}€</div>".format(sum(i['price'] for i in st.session_state.cart)), unsafe_allow_html=True)

    elif current_view == "📊 MANAGER" and supabase:
        st.title("📊 Αναφορές Διεύθυνσης")
        if st.text_input("Κωδικός MANAGER", type="password") == "999":
            res_s = supabase.table("sales").select("*").execute()
            if res_s.data:
                df = pd.DataFrame(res_s.data)
                df['s_date'] = pd.to_datetime(df['s_date'])
                df['ΗΜΕΡΟΜΗΝΙΑ'] = df['s_date'].dt.date
                c1, c2 = st.columns(2)
                start_d = c1.date_input("Από", value=get_athens_now().date() - timedelta(days=30))
                end_d = c2.date_input("Έως", value=get_athens_now().date())
                mask = (df['ΗΜΕΡΟΜΗΝΙΑ'] >= start_d) & (df['ΗΜΕΡΟΜΗΝΙΑ'] <= end_d)
                fdf = df[mask]
                sc1, sc2, sc3 = st.columns(3)
                sc1.markdown(f"<div class='report-stat'><div class='stat-val'>{fdf['final_item_price'].sum():.2f}€</div><div class='stat-desc'>ΣΥΝΟΛΙΚΟΣ ΤΖΙΡΟΣ</div></div>", unsafe_allow_html=True)
                sc2.markdown(f"<div class='report-stat'><div class='stat-val'>{len(fdf)}</div><div class='stat-desc'>ΠΩΛΗΣΕΙΣ</div></div>", unsafe_allow_html=True)
                cash = fdf[fdf['method'] == 'Μετρητά']['final_item_price'].sum()
                card = fdf[fdf['method'] == 'Κάρτα']['final_item_price'].sum()
                sc3.markdown(f"<div class='report-stat'><div class='stat-val'>{cash:.2f}€ / {card:.2f}€</div><div class='stat-desc'>ΜΕΤΡΗΤΑ / ΚΑΡΤΑ</div></div>", unsafe_allow_html=True)
                st.subheader("📈 Πωλήσεις ανά Ημέρα")
                daily = fdf.groupby('ΗΜΕΡΟΜΗΝΙΑ')['final_item_price'].sum().reset_index()
                st.plotly_chart(px.line(daily, x='ΗΜΕΡΟΜΗΝΙΑ', y='final_item_price', markers=True, template="plotly_dark"), use_container_width=True)
                st.subheader("📋 Αναλυτικό Ημερολόιο")
                for d_val in sorted(fdf['ΗΜΕΡΟΜΗΝΙΑ'].unique(), reverse=True):
                    day_data = fdf[fdf['ΗΜΕΡΟΜΗΝΙΑ'] == d_val]
                    st.markdown(f"<div class='day-header'>{d_val.strftime('%d/%m/%Y')} | Σύνολο: {day_data['final_item_price'].sum():.2f}€</div>", unsafe_allow_html=True)
                    st.table(day_data[['s_date', 'item_name', 'unit_price', 'discount', 'final_item_price', 'method']].rename(columns={'s_date':'Ώρα','item_name':'Είδος','unit_price':'Αρχική','discount':'Έκπτωση','final_item_price':'Τελική','method':'Τρόπος'}))

    elif current_view == "📦 ΑΠΟΘΗΚΗ" and supabase:
        st.title("📦 Διαχείριση Αποθήκης")
        t_new, t_set, t_inv = st.tabs(["🆕 ΚΑΤΑΧΩΡΗΣΗ", "⚙️ ΡΥΘΜΙΣΕΙΣ", "📋 ΑΠΟΘΕΜΑ"])
        
        with t_new:
            # Βελτιωμένη αναζήτηση τελευταίου σχεδίου
            last_design = ""
            try:
                # Δοκιμάζουμε αναζήτηση με βάση το ID (που αυξάνεται πάντα) αν δεν δουλεύει το created_at
                res_last = supabase.table("inventory").select("barcode").order("barcode", desc=True).limit(20).execute()
                if res_last.data:
                    # Παίρνουμε το πιο πρόσφατο που έχει το σωστό format
                    for entry in res_last.data:
                        parts = entry['barcode'].split('-')
                        if len(parts) >= 3:
                            last_design = parts[2]
                            break
            except: pass

            with st.form("inventory_form", clear_on_submit=True):
                # Εμφάνιση της τελευταίας τιμής σε έντονο πλαίσιο
                if last_design:
                    st.info(f"📌 Τελευταία καταχώρηση σχεδίου: **{last_design}**")
                else:
                    st.warning("⚠️ Δεν βρέθηκαν προηγούμενες καταχωρήσεις.")
                
                c1, c2, c3 = st.columns(3)
                f_item = c1.selectbox("Είδος", sorted(st.session_state.master_lists.get("Είδη", [])))
                f_prov = c2.selectbox("Προμηθευτής", sorted(st.session_state.master_lists.get("Προμηθευτές", [])))
                f_color = c3.selectbox("Χρώμα", sorted(st.session_state.master_lists.get("Χρώματα", [])))
                
                c4, c5, c6 = st.columns(3)
                # Χρησιμοποιούμε το last_design ως placeholder
                f_design = c4.text_input("Σχέδιο / Κωδικός", value="", placeholder=str(last_design) if last_design else "π.χ. 001") 
                f_size = c5.selectbox("Μέγεθος", sorted(st.session_state.master_lists.get("Μεγέθη", [])))
                f_comp = c6.selectbox("Σύνθεση", sorted(st.session_state.master_lists.get("Συνθέσεις", [])))
                
                c7, c8 = st.columns(2)
                f_price = c7.number_input("Τιμή Πώλησης (€)", min_value=0.0, step=1.0, value=0.0)
                f_stock = c8.number_input("Αρχικό Απόθεμα", min_value=0, value=1)
                
                if st.form_submit_button("💾 ΑΠΟΘΗΚΕΥΣΗ ΠΡΟΪΟΝΤΟΣ"):
                    if not f_design: st.error("⚠️ Πρέπει να βάλετε Σχέδιο!")
                    elif f_price <= 0: st.error("⚠️ Βάλτε Τιμή!")
                    else:
                        sku = f"{generate_latin_code(f_item)}-{generate_latin_code(f_prov)}-{f_design.upper().strip()}-{generate_latin_code(f_color)}-{generate_latin_code(f_size)}"
                        name = f"{f_item} {f_color} ({f_comp}) [{f_size}]".upper()
                        try:
                            supabase.table("inventory").upsert({"barcode": sku, "name": name, "price": float(f_price), "stock": int(f_stock)}).execute()
                            st.success(f"✅ Καταχωρήθηκε: {sku}"); time.sleep(1); st.rerun()
                        except Exception as e:
                            if "23505" in str(e): st.error(f"⚠️ Ο κωδικός '{f_design}' υπάρχει ήδη για αυτό το συνδυασμό!")
                            else: st.error(str(e))

        with t_set:
            cat = st.selectbox("Λίστα", list(st.session_state.master_lists.keys()))
            new_val = st.text_input("Νέο στοιχείο")
            if st.button("Προσθήκη"):
                if new_val:
                    st.session_state.master_lists[cat].append(new_val); st.session_state.master_lists[cat].sort()
                    if save_master_lists(): sync_master_lists(force=True); st.rerun()
            for v in sorted(st.session_state.master_lists.get(cat, [])):
                col1, col2 = st.columns([5, 1])
                col1.write(v)
                if col2.button("🗑️", key=f"del_{cat}_{v}"):
                    st.session_state.master_lists[cat].remove(v)
                    if save_master_lists(): sync_master_lists(force=True); st.rerun()

        with t_inv:
            res = supabase.table("inventory").select("*").execute()
            if res.data:
                for r in sorted(res.data, key=lambda x: x['name']):
                    col1, col2, col3 = st.columns([5, 1, 1])
                    with col1: st.markdown(f"<div class='data-row'>📦 {r['barcode']} | {r['name']} | {r['price']}€ | Stock: {r['stock']}</div>", unsafe_allow_html=True)
                    if col2.button("🏷️", key=f"l_{r['barcode']}"): print_label_popup(r['barcode'], r['name'], r['price'])
                    if col3.button("❌", key=f"d_{r['barcode']}"): supabase.table("inventory").delete().eq("barcode", r['barcode']).execute(); st.rerun()

    elif current_view == "👥 ΠΕΛΑΤΕΣ" and supabase:
        st.title("👥 Πελάτες")
        res_c = supabase.table("customers").select("*").execute()
        res_s = supabase.table("sales").select("cust_id, final_item_price").execute()
        if res_c.data:
            sales_data = pd.DataFrame(res_s.data) if res_s.data else pd.DataFrame(columns=['cust_id', 'final_item_price'])
            for _, r in pd.DataFrame(res_c.data).sort_values(by='name').iterrows():
                pts = int(sales_data[sales_data['cust_id'] == r['id']]['final_item_price'].sum() // 10)
                col1, col2, col3 = st.columns([5, 1, 1])
                with col1: st.markdown(f"<div class='data-row'>👤 {r['name']} | 📞 {r['phone']} | ⭐ {pts} pts</div>", unsafe_allow_html=True)
                if col2.button("⭐", key=f"pts_{r['id']}", use_container_width=True): show_customer_history(r['id'], r['name'])
                if col3.button("❌", key=f"c_del_{r['id']}", use_container_width=True): supabase.table("customers").delete().eq("id", r['id']).execute(); st.rerun()
    
    elif current_view == "⚙️ SYSTEM" and supabase:
        st.title("⚙️ Ρυθμίσεις Συστήματος")
        if st.text_input("Κωδικός SYSTEM", type="password") == "999":
            target = st.selectbox("Αρχικοποίηση", ["---", "Sales", "Customers", "Inventory"])
            if target != "---" and st.text_input("Γράψτε ΔΙΑΓΡΑΦΗ για επιβεβαίωση") == "ΔΙΑΓΡΑΦΗ":
                if st.button("ΕΚΤΕΛΕΣΗ ΚΑΘΑΡΙΣΜΟΥ"):
                    supabase.table(target.lower()).delete().neq("id", -1).execute()
                    st.success("Καθαρίστηκε."); time.sleep(1); st.rerun()
