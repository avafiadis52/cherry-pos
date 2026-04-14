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

# --- 3. CONFIG & STYLE (Version v14.7.4) ---
st.set_page_config(page_title="CHERRY v14.7.4", layout="wide", page_icon="🍒")

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
if 'form_reset_key' not in st.session_state: st.session_state.form_reset_key = 0

sync_master_lists()

def get_athens_now(): return datetime.now() + timedelta(hours=2)

def generate_latin_code(text):
    char_map = {'Α':'A','Β':'B','Γ':'G','Δ':'D','Ε':'E','Ζ':'Z','Η':'H','Θ':'TH','Ι':'I','Κ':'K','Λ':'L','Μ':'M','Ν':'N','Ξ':'X','Ο':'O','Π':'P','Ρ':'R','Σ':'S','Τ':'T','Υ':'Y','Φ':'F','Χ':'CH','Ψ':'PS','Ω':'O','Ά':'A','Έ':'E','Ή':'H','Ί':'I','Ό':'O','Ύ':'Y','Ώ':'O','Ϊ':'I','Ϋ':'Y'}
    res = "".join([char_map.get(c, c) for c in str(text).upper()])
    return res if len(res) <= 3 else res[:3]

def reset_app():
    st.session_state.cart, st.session_state.selected_cust_id = [], None
    st.session_state.cust_name = "Λιανική Πώληση"
    st.session_state.bc_key += 1; st.session_state.ph_key += 1; st.session_state.mic_key += 1
    st.rerun()

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
        view = st.radio("Μενού", ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ", "⚙️ SYSTEM"])
        if st.button("❌ Έξοδος", use_container_width=True): st.session_state.logged_in = False; st.rerun()

    if view == "🛒 ΤΑΜΕΙΟ":
        st.subheader("🛒 ΤΑΜΕΙΟ")
        # (Το κομμάτι του ταμείου παραμένει ίδιο με v14.7.3)
        # ... [Ο κώδικας του ταμείου] ...
        pass # Συμπεριλαμβάνεται κανονικά στον πλήρη κώδικα

    elif view == "📊 MANAGER" and supabase:
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
                
                st.subheader("📋 Αναλυτικό Ημερολόγιο")
                for d_val in sorted(fdf['ΗΜΕΡΟΜΗΝΙΑ'].unique(), reverse=True):
                    day_data = fdf[fdf['ΗΜΕΡΟΜΗΝΙΑ'] == d_val]
                    st.markdown(f"<div class='day-header'>{d_val.strftime('%d/%m/%Y')} | Σύνολο: {day_data['final_item_price'].sum():.2f}€</div>", unsafe_allow_html=True)
                    st.table(day_data[['s_date', 'item_name', 'unit_price', 'discount', 'final_item_price', 'method']].rename(columns={'s_date':'Ώρα','item_name':'Είδος','unit_price':'Αρχική','discount':'Έκπτωση','final_item_price':'Τελική','method':'Τρόπος'}))

    elif view == "📦 ΑΠΟΘΗΚΗ" and supabase:
        st.title("📦 Διαχείριση Αποθήκης")
        t_new, t_set, t_inv = st.tabs(["🆕 ΚΑΤΑΧΩΡΗΣΗ", "⚙️ ΡΥΘΜΙΣΕΙΣ", "📋 ΑΠΟΘΕΜΑ"])
        
        with t_new:
            # Εύρεση τελευταίου σχεδίου για πληροφορία
            last_design_info = ""
            try:
                res_last = supabase.table("inventory").select("barcode").order("id", desc=True).limit(1).execute()
                if res_last.data:
                    parts = res_last.data[0]['barcode'].split('-')
                    if len(parts) >= 3: last_design_info = parts[2]
            except: pass

            # Φόρμα με δυναμικό Key για Reset
            with st.form(f"inv_form_{st.session_state.form_reset_key}", clear_on_submit=True):
                if last_design_info:
                    st.info(f"💡 Τελευταίο Σχέδιο στη Βάση: **{last_design_info}**")
                
                c1, c2, c3 = st.columns(3)
                f_item = c1.selectbox("Είδος", [""] + sorted(st.session_state.master_lists.get("Είδη", [])))
                f_prov = c2.selectbox("Προμηθευτής", [""] + sorted(st.session_state.master_lists.get("Προμηθευτές", [])))
                f_color = c3.selectbox("Χρώμα", [""] + sorted(st.session_state.master_lists.get("Χρώματα", [])))
                
                c4, c5, c6 = st.columns(3)
                f_design = c4.text_input("Σχέδιο / Κωδικός", value="") 
                f_size = c5.selectbox("Μέγεθος", [""] + sorted(st.session_state.master_lists.get("Μεγέθη", [])))
                f_comp = c6.selectbox("Σύνθεση", [""] + sorted(st.session_state.master_lists.get("Συνθέσεις", [])))
                
                c7, c8 = st.columns(2)
                f_price = c7.number_input("Τιμή Πώλησης (€)", min_value=0.0, step=0.5, value=0.0)
                f_stock = c8.number_input("Αρχικό Απόθεμα", min_value=0, value=1)
                
                if st.form_submit_button("💾 ΑΠΟΘΗΚΕΥΣΗ ΠΡΟΪΟΝΤΟΣ"):
                    if not all([f_item, f_prov, f_design, f_price > 0]):
                        st.error("⚠️ Παρακαλώ συμπληρώστε όλα τα βασικά πεδία και την τιμή!")
                    else:
                        sku = f"{generate_latin_code(f_item)}-{generate_latin_code(f_prov)}-{f_design.upper().strip()}-{generate_latin_code(f_color)}-{generate_latin_code(f_size)}"
                        name = f"{f_item} {f_color} ({f_comp}) [{f_size}]".upper()
                        try:
                            supabase.table("inventory").upsert({"barcode": sku, "name": name, "price": float(f_price), "stock": int(f_stock)}).execute()
                            st.success(f"✅ Καταχωρήθηκε: {sku}")
                            st.session_state.form_reset_key += 1 # Αλλάζει το key και αδειάζει η φόρμα
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Σφάλμα: {str(e)}")

        # Οι υπόλοιπες καρτέλες (Ρυθμίσεις, Απόθεμα κλπ) παραμένουν ίδιες...
