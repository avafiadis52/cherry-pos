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

# --- 3. CONFIG & STYLE (Version v14.5.4) ---
st.set_page_config(page_title="CHERRY v14.5.4", layout="wide", page_icon="🍒")

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

    @media only screen and (max-width: 600px) {
        .cart-area { font-size: 2.8vw; padding: 8px; }
        .total-label { font-size: 50px !important; }
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
    table { color: white !important; }
    thead tr th { color: white !important; background-color: #333 !important; }
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

# --- ΛΕΙΤΟΥΡΓΙΑ ΜΟΝΙΜΩΝ ΛΙΣΤΩΝ (Global Persistent Lists) ---
@st.cache_resource
def get_global_lists():
    return {
        "Είδη": ["Ζακέτα", "Ζώνη", "Μπλούζα", "Μπουφάν / Παλτό", "Παντελόνι", "Πουκάμισο", "Φόρεμα", "Φούστα"],
        "Προμηθευτές": ["ONADO", "PINUP", "ΡΕΝΑ", "ΣΤΕΛΛΑ", "ΤΖΕΝΗ"],
        "Χρώματα": ["Γκρι", "Εκρού", "Εμπριμέ", "Καφέ", "Κίτρινο", "Κόκκινο", "Λευκό", "Μαύρο", "Μπεζ", "Μπλε", "Πουά", "Πράσινο", "Ριγέ", "Σιέλ"],
        "Συνθέσεις": ["100% Βαμβάκι", "100% Πολυέστερ", "70% Βαμβάκι - 30% Πολυέστερ", "98% Βαμβάκι - 2% Ελαστάνη", "100% Δέρμα", "Τεχνητό Δέρμα (PU)"]
    }

# Φόρτωση των λιστών στο session state
st.session_state.master_lists = get_global_lists()

# --- 4. FUNCTIONS ---
def get_athens_now():
    return datetime.now() + timedelta(hours=2)

def generate_latin_code(text):
    char_map = {
        'Α':'A','Β':'B','Γ':'G','Δ':'D','Ε':'E','Ζ':'Z','Η':'H','Θ':'TH','Ι':'I','Κ':'K','Λ':'L','Μ':'M','Ν':'N','Ξ':'X','Ο':'O','Π':'P','Ρ':'R','Σ':'S','Τ':'T','Υ':'Y','Φ':'F','Χ':'CH','Ψ':'PS','Ω':'O',
        'Ά':'A','Έ':'E','Ή':'H','Ί':'I','Ό':'O','Ύ':'Y','Ώ':'O','Ϊ':'I','Ϋ':'Y'
    }
    res = "".join([char_map.get(c, c) for c in str(text).upper()])
    return res[:3]

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

def speak_text(text_to_say, play_beep=True):
    beep_js = """
    var context = new (window.AudioContext || window.webkitAudioContext)();
    var osc = context.createOscillator();
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(150, context.currentTime);
    osc.connect(context.destination);
    osc.start();
    osc.stop(context.currentTime + 0.2);
    """ if play_beep else ""
    speech_js = "var msg = new SpeechSynthesisUtterance('{}'); msg.lang = 'el-GR'; window.speechSynthesis.speak(msg);".format(text_to_say) if text_to_say else ""
    st.components.v1.html("<script>{}{}</script>".format(beep_js, speech_js), height=0)

def play_sound(url):
    st.components.v1.html('<audio autoplay style="display:none"><source src="{}" type="audio/mpeg"></audio>'.format(url), height=0)

@st.dialog("🏷️ Εκτύπωση Ετικέτας")
def print_label_popup(bc, name, price):
    st.write("Προεπισκόπηση Ετικέτας:")
    try:
        char_map = {
            'Α':'A','Β':'B','Γ':'G','Δ':'D','Ε':'E','Ζ':'Z','Η':'H','Θ':'TH','Ι':'I','Κ':'K','Λ':'L','Μ':'M','Ν':'N','Ξ':'X','Ο':'O','Π':'P','Ρ':'R','Σ':'S','Τ':'T','Υ':'Y','Φ':'F','Χ':'CH','Ψ':'PS','Ω':'O',
            'Ά':'A','Έ':'E','Ή':'H','Ί':'I','Ό':'O','Ύ':'Y','Ώ':'O','Ϊ':'I','Ϋ':'Y'
        }
        clean_bc = "".join([char_map.get(c, c) for c in str(bc).upper()])
        CODE128 = barcode.get_barcode_class('code128')
        writer_options = {"write_text": False, "module_height": 5.0}
        my_barcode = CODE128(clean_bc, writer=ImageWriter())
        buffer = io.BytesIO()
        my_barcode.write(buffer, options=writer_options)
        b64 = base64.b64encode(buffer.getvalue()).decode()
        barcode_img_html = f'<img src="data:image/png;base64,{b64}" style="width: 230px; height: 50px;">'
    except Exception as e:
        barcode_img_html = f'<div style="color:red; font-size:10px;">Σφάλμα Barcode: {e}</div>'

    parts = bc.split('-')
    prov_code = parts[1] if len(parts) > 1 else "---"
    design_code = parts[2] if len(parts) > 2 else "---"
    comp_match = re.search(r'\((.*?)\)', name)
    comp_text = comp_match.group(1) if comp_match else "---"
    clean_name = re.sub(r'\(.*?\)', '', name).strip()
    
    label_html = f"""
    <div id="printable-label" style="width: 280px; border: 1px solid #ccc; padding: 15px; text-align: center; background-color: white; color: black; font-family: Arial;">
        <div style="font-size: 14px; font-weight: bold; margin-bottom: 2px;">CHERRY</div>
        <div style="font-size: 11px; font-weight: bold; margin-bottom: 3px;">{clean_name}</div>
        <div style="font-size: 9px; color: #333; margin-bottom: 5px;">
            Προμ: {prov_code} | Σχέδιο: {design_code}<br>
            Σύνθεση: {comp_text}
        </div>
        <div style="margin: 5px 0;">
            {barcode_img_html}
            <div style="font-size: 10px; font-family: monospace; font-weight: bold; letter-spacing: 1px;">{bc}</div>
        </div>
        <div style="font-size: 22px; font-weight: bold; border-top: 1px solid black; padding-top: 5px; margin-top: 5px;">{price:.2f}€</div>
    </div>
    """
    st.markdown(label_html, unsafe_allow_html=True)
    st.divider()
    qty = st.number_input("Πλήθος Ετικετών", min_value=1, max_value=50, value=1)
    if st.button("🖨️ ΕΚΤΥΠΩΣΗ ({} {})".format(qty, "ΑΝΤΙΤΥΠΟ" if qty==1 else "ΑΝΤΙΤΥΠΑ"), use_container_width=True):
        st.components.v1.html(f"""
            <script>
                var win = window.open('', '', 'height=500,width=500');
                win.document.write('<html><body style="margin:0; display:flex; justify-content:center; align-items:center;">');
                win.document.write('{label_html.replace("border: 1px solid #ccc;", "border: none;")}');
                win.document.write('</body></html>');
                win.document.close();
                win.print();
            </script>
        """, height=0)
        st.success(f"Η εντολή για {qty} ετικέτες στάλθηκε.")

@st.dialog("👤 Νέος Πελάτης")
def new_customer_popup(phone):
    st.write("Το τηλέφωνο **{}** δεν υπάρχει στη βάση.".format(phone))
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
            except Exception as e: st.error("Σφάλμα: {}".format(e))
        else: st.warning("Παρακαλώ δώστε όνομα.")

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
            data = {"barcode": str(i['bc']), "item_name": str(i['name']), "unit_price": float(i['price']), "discount": float(d), "final_item_price": float(f), "method": str(method), "s_date": ts, "cust_id": c_id}
            supabase.table("sales").insert(data).execute()
            if i['bc'] != 'VOICE':
                res_inv = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
                if res_inv.data:
                    change = 1 if i['price'] < 0 else -1
                    new_stock = int(res_inv.data[0]['stock']) + change
                    supabase.table("inventory").update({"stock": new_stock}).eq("barcode", i['bc']).execute()
        st.success("✅ ΕΠΙΤΥΧΗΣ ΠΛΗΡΩΜΗ"); st.balloons()
        speak_text("Επιτυχής Πληρωμή", play_beep=False)
        play_sound("https://www.soundjay.com/misc/sounds/magic-chime-01.mp3")
        time.sleep(1.5); reset_app()
    except Exception as e: st.error("Σφάλμα: {}".format(e))

@st.dialog("💰 Πληρωμή")
def payment_popup():
    total = sum(i['price'] for i in st.session_state.cart)
    st.markdown("<h3 style='text-align:center;'>Σύνολο: {:.2f}€</h3>".format(total), unsafe_allow_html=True)
    st.write("Θέλετε έκπτωση;")
    opt = st.radio("Επιλογή", ["ΟΧΙ", "ΝΑΙ"], horizontal=True, label_visibility="collapsed")
    disc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή ποσοστό %", placeholder="π.χ. 5 ή 10%")
        if inp:
            try:
                if "%" in inp: disc = round((float(inp.replace("%",""))/100 * total), 2)
                else: disc = round(float(inp), 2)
            except: st.error("Λάθος μορφή")
    final_p = round(total - disc, 2)
    st.markdown("<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {:.2f}€</div>".format(final_p), unsafe_allow_html=True)
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(disc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(disc, "Κάρτα")

# --- 5. LOGIN LOGIC ---
if not st.session_state.logged_in:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("<h1 style='text-align:center;'>🔒 CHERRY LOGIN</h1>", unsafe_allow_html=True)
        pwd = st.text_input("Εισάγετε τον κωδικό πρόσβασης", type="password")
        if st.button("Είσοδος", use_container_width=True):
            if pwd == "CHERRY123":
                st.session_state.logged_in = True
                st.success("Επιτυχής σύνδεση!")
                time.sleep(0.5); st.rerun()
            else:
                st.error("❌ Λάθος κωδικός")
                speak_text("Λάθος κωδικός")
else:
    # --- 6. MAIN UI ---
    with st.sidebar:
        current_athens = get_athens_now()
        chosen_date = st.date_input("Ημερομηνία", value=current_athens.date())
        chosen_time = st.time_input("Ώρα", value=current_athens.time())
        st.session_state.manual_ts = datetime.combine(chosen_date, chosen_time)
        st.markdown("<div class='sidebar-date'>{}</div>".format(st.session_state.manual_ts.strftime('%d/%m/%Y %H:%M:%S')), unsafe_allow_html=True)
        
        st.subheader("🎙️ Φωνητική Εντολή")
        if HAS_MIC:
            text = speech_to_text(language='el', start_prompt="🔴 ΠΑΤΑ ΚΑΙ ΜΙΛΑ", stop_prompt="🟢 ΕΠΕΞΕΡΓΑΣΙΑ...", just_once=True, key="voice_{}".format(st.session_state.mic_key))
            if text:
                raw_query = text.lower().strip()
                numbers = re.findall(r"[-+]?\d*\.\d+|\d+", raw_query)
                found_price = float(numbers[0]) if numbers else None
                if found_price:
                    clean_name = raw_query
                    if numbers: clean_name = clean_name.replace(numbers[0], "")
                    for w in ["ευρώ", "ευρω", "τιμή"]: clean_name = clean_name.replace(w, "")
                    price_to_add = -found_price if st.session_state.return_mode else found_price
                    st.session_state.cart.append({'bc': 'VOICE', 'name': clean_name.strip().upper() or "ΦΩΝΗΤΙΚΗ ΠΩΛΗΣΗ", 'price': price_to_add})
                    st.session_state.mic_key += 1; time.sleep(0.4); st.rerun()

        st.divider()
        menu_options = ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ", "⚙️ SYSTEM"]
        def_idx = 1 if st.session_state.return_mode else 0
        view = st.radio("Μενού", menu_options, index=def_idx, key="sidebar_nav")
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        current_view = view if view != "🔄 ΕΠΙΣΤΡΟΦΗ" else "🛒 ΤΑΜΕΙΟ"
        
        if st.button("❌ Έξοδος / Κλείδωμα", use_container_width=True): 
            st.session_state.logged_in = False
            st.session_state.cart = []
            st.rerun()

    # --- VIEW ROUTING ---
    if current_view == "🛒 ΤΑΜΕΙΟ":
        if st.session_state.return_mode:
            st.button("🔄 ΛΕΙΤΟΥΡΓΙΑ ΕΠΙΣΤΡΟΦΗΣ", on_click=switch_to_normal, use_container_width=True)
            st.error("⚠️ ΣΚΑΝΑΡΕΤΕ ΤΗΝ ΕΠΙΣΤΡΟΦΗ")
        else:
            st.markdown("<div class='status-header'>Πελάτης: {}</div>".format(st.session_state.cust_name), unsafe_allow_html=True)
            
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο (10 ψηφία)", key="ph_{}".format(st.session_state.ph_key))
                if ph:
                    clean_ph = ''.join(filter(str.isdigit, ph))
                    if len(clean_ph) == 10:
                        res = supabase.table("customers").select("*").eq("phone", clean_ph).execute()
                        if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.rerun()
                        else: new_customer_popup(clean_ph)
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ", use_container_width=True): st.session_state.selected_cust_id = 0; st.rerun()
            else:
                st.button("👤 {} (Αλλαγή)".format(st.session_state.cust_name), on_click=lambda: st.session_state.update({"selected_cust_id": None, "cust_name": "Λιανική Πώληση"}), use_container_width=True)
                bc = st.text_input("Barcode", key="bc_{}".format(st.session_state.bc_key))
                if bc and supabase:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data: 
                        val = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'bc': res.data[0]['barcode'], 'name': res.data[0]['name'].upper(), 'price': val})
                        st.session_state.bc_key += 1; st.rerun()
                for idx, item in enumerate(st.session_state.cart):
                    if st.button("❌ {} {}€".format(item['name'], item['price']), key="del_{}".format(idx), use_container_width=True): st.session_state.cart.pop(idx); st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
            if st.button("🔄 ΑΚΥΡΩΣΗ", use_container_width=True): reset_app()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            lines = ["{:45} | {:>4.2f}€".format(i['name'][:45], i['price']) for i in st.session_state.cart]
            st.markdown("<div class='cart-area'>{:45} | {:>4}\n{}\n{}</div>".format('Είδος', 'Τιμή', '-'*56, '\n'.join(lines)), unsafe_allow_html=True)
            st.markdown("<div class='total-label'>{:.2f}€</div>".format(total), unsafe_allow_html=True)

    elif current_view == "📦 ΑΠΟΘΗΚΗ" and supabase:
        st.title("📦 Διαχείριση Αποθήκης")
        tab_new, tab_settings, tab_list = st.tabs(["🆕 ΚΑΤΑΧΩΡΗΣΗ", "⚙️ ΡΥΘΜΙΣΕΙΣ", "📋 ΑΠΟΘΕΜΑ"])
        
        with tab_new:
            with st.form("inventory_form", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                f_item = c1.selectbox("Είδος", sorted(st.session_state.master_lists["Είδη"]))
                f_prov = c2.selectbox("Προμηθευτής", sorted(st.session_state.master_lists["Προμηθευτές"]))
                f_color = c3.selectbox("Χρώμα", sorted(st.session_state.master_lists["Χρώματα"]))
                c4, c5, c6 = st.columns(3)
                f_design = c4.text_input("Σχέδιο / Κωδικός")
                f_comp = c5.selectbox("Σύνθεση", sorted(st.session_state.master_lists["Συνθέσεις"]))
                f_price = c6.number_input("Τιμή Πώλησης (€)", min_value=0.0, step=1.0)
                f_stock = st.number_input("Αρχικό Απόθεμα", min_value=0, value=1)
                if st.form_submit_button("💾 ΑΠΟΘΗΚΕΥΣΗ ΠΡΟΪΟΝΤΟΣ"):
                    if f_design:
                        sku = "{}-{}-{}".format(generate_latin_code(f_item), generate_latin_code(f_prov), f_design.upper())
                        full_name = "{} {} ({})".format(f_item, f_color, f_comp).upper()
                        supabase.table("inventory").upsert({"barcode": sku, "name": full_name, "price": float(f_price), "stock": int(f_stock)}).execute()
                        st.success("Καταχωρήθηκε!")
                        time.sleep(1); st.rerun()

        with tab_settings:
            st.subheader("Διαχείριση Λιστών Επιλογής")
            cat = st.selectbox("Επιλέξτε Λίστα", list(st.session_state.master_lists.keys()))
            new_val = st.text_input("Νέα Τιμή (π.χ. ΑΣΠΡΟ)")
            
            if st.button("Προσθήκη στη Λίστα"):
                if new_val and new_val.upper() not in [x.upper() for x in st.session_state.master_lists[cat]]:
                    # Προσθήκη στην Cache Resource Λίστα (Global για την εφαρμογή)
                    st.session_state.master_lists[cat].append(new_val.upper())
                    st.session_state.master_lists[cat].sort()
                    st.success(f"Το '{new_val.upper()}' προστέθηκε!")
                    time.sleep(1); st.rerun()
            
            st.write("Τρέχουσες τιμές (Αλφαβητικά):")
            st.info(", ".join(sorted(st.session_state.master_lists[cat])))

        with tab_list:
            res = supabase.table("inventory").select("*").execute()
            if res.data:
                inv_df = pd.DataFrame(res.data).sort_values(by='name')
                for _, r in inv_df.iterrows():
                    col1, col2, col3 = st.columns([5, 1, 1])
                    txt = "📦 {} | {} | {:.2f}€ | Stock: {}".format(r['barcode'], r['name'], r['price'], r['stock'])
                    with col1: st.markdown("<div class='data-row'>{}</div>".format(txt), unsafe_allow_html=True)
                    with col2:
                        if st.button("🏷️", key="lbl_{}".format(r['barcode'])): print_label_popup(r['barcode'], r['name'], r['price'])
                    with col3:
                        if st.button("❌", key="inv_{}".format(r['barcode'])):
                            supabase.table("inventory").delete().eq("barcode", r['barcode']).execute()
                            st.rerun()
