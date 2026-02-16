import pandas as pd
from datetime import datetime, date, timedelta
import time
import streamlit as st
from supabase import create_client, Client
import re
import plotly.express as px

# --- 1. VOICE COMPONENT SETUP ---
HAS_MIC = False
try:
    from streamlit_mic_recorder import speech_to_text
    HAS_MIC = True
except Exception:
    HAS_MIC = False

# --- 2. SUPABASE SETUP ---
S_URL = "https://hnwynihjkdkryrfepenh.supabase.co"
S_KEY = "sb_publishable_ualF72lJKgUQA4TzjPQ-OA_zih7zJ-s"

@st.cache_resource
def init_supabase():
    try: return create_client(S_URL, S_KEY)
    except: return None

supabase = init_supabase()

# --- 3. CONFIG & STYLE ---
st.set_page_config(page_title="CHERRY v14.2.62", layout="wide", page_icon="🍒")

st.markdown("""
    <style>
    .stApp { background-color: #1a1a1a; color: white; }
    label, [data-testid="stWidgetLabel"] p { color: #ffffff !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    input { color: #000000 !important; font-weight: bold !important; }
    .cart-area { 
        font-family: 'Courier New', monospace; background-color: #000; padding: 15px; border-radius: 10px; 
        white-space: pre-wrap; border: 4px solid #2ecc71; box-shadow: 0 0 15px rgba(46,204,113,0.4); 
        min-height: 300px; font-size: 16px; color: #2ecc71; 
    }
    .total-label { font-size: 70px; font-weight: bold; color: #2ecc71; text-align: center; text-shadow: 2px 2px 10px rgba(46,204,113,0.5); }
    .status-header { font-size: 20px; font-weight: bold; color: #3498db; text-align: center; }
    .final-amount-popup { font-size: 40px; font-weight: bold; color: #e44d26; text-align: center; padding: 10px; border-radius: 10px; background-color: #fff3f0; border: 2px solid #e44d26; }
    div.stButton > button { background-color: #d3d3d3 !important; color: #000 !important; border-radius: 8px; font-weight: bold; }
    .data-row { font-family: 'Courier New', monospace; background-color: #262626; padding: 12px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #3498db; }
    .report-stat { background-color: #262730; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 10px; }
    .stat-val { font-size: 24px; font-weight: bold; color: #2ecc71; }
    .stat-desc { font-size: 13px; color: #888; }
    .day-header { background-color: #34495e; color: #f1c40f; padding: 10px; border-radius: 5px; margin-top: 25px; border-left: 8px solid #f1c40f; }
    </style>
    """, unsafe_allow_html=True)

# Session States
for k, v in {'logged_in':False,'cart':[],'selected_cust_id':None,'cust_name':"Λιανική Πώληση",'bc_key':0,'ph_key':100,'mic_key':28000,'return_mode':False}.items():
    if k not in st.session_state: st.session_state[k] = v

# --- 4. FUNCTIONS ---
def get_athens_now(): return datetime.now() + timedelta(hours=2)

def reset_app():
    st.session_state.update({'cart':[],'selected_cust_id':None,'cust_name':"Λιανική Πώληση",'return_mode':False})
    st.session_state.bc_key+=1; st.session_state.ph_key+=1; st.session_state.mic_key+=1; st.rerun()

def speak_text(text, play_beep=True):
    b_js = "var c=new (window.AudioContext||window.webkitAudioContext)();var o=c.createOscillator();o.type='sawtooth';o.frequency.setValueAtTime(150,c.currentTime);o.connect(c.destination);o.start();o.stop(c.currentTime+0.2);" if play_beep else ""
    s_js = f"var m=new SpeechSynthesisUtterance('{text}');m.lang='el-GR';window.speechSynthesis.speak(m);"
    st.components.v1.html(f"<script>{b_js}{s_js}</script>", height=0)

@st.dialog("👤 Νέος Πελάτης")
def new_customer_popup(phone):
    name = st.text_input(f"Όνομα για το {phone}")
    if st.button("Καταχώρηση", use_container_width=True) and name:
        res = supabase.table("customers").insert({"name": name.upper(), "phone": phone}).execute()
        if res.data:
            st.session_state.update({"selected_cust_id":res.data[0]['id'], "cust_name":res.data[0]['name']})
            st.success("OK"); time.sleep(1); st.rerun()

def finalize(disc, method):
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio = disc / sub if sub > 0 else 0
    ts = get_athens_now().strftime("%Y-%m-%d %H:%M:%S")
    for i in st.session_state.cart:
        d_val = round(i['price'] * ratio, 2)
        f_val = round(i['price'] - d_val, 2)
        supabase.table("sales").insert({"barcode":str(i['bc']),"item_name":str(i['name']),"unit_price":float(i['price']),"discount":float(d_val),"final_item_price":float(f_val),"method":method,"s_date":ts,"cust_id":st.session_state.selected_cust_id or None}).execute()
        if i['bc'] != 'VOICE':
            inv = supabase.table("inventory").select("stock").eq("barcode", i['bc']).execute()
            if inv.data:
                chg = 1 if i['price'] < 0 else -1
                supabase.table("inventory").update({"stock": int(inv.data[0]['stock']) + chg}).eq("barcode", i['bc']).execute()
    st.success("💰 OK"); speak_text("Επιτυχής Πληρωμή", False); time.sleep(1); reset_app()

@st.dialog("💰 Πληρωμή")
def payment_popup():
    tot = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {tot:.2f}€</h3>", unsafe_allow_html=True)
    opt = st.radio("Έκπτωση;", ["ΟΧΙ", "ΝΑΙ"], horizontal=True)
    dsc = 0.0
    if opt == "ΝΑΙ":
        inp = st.text_input("Ποσό ή %")
        if inp:
            try: dsc = round((float(inp.replace("%",""))/100*tot),2) if "%" in inp else float(inp)
            except: st.error("Error")
    st.markdown(f"<div class='final-amount-popup'>{(tot-dsc):.2f}€</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("💵 Μετρητά", use_container_width=True): finalize(dsc, "Μετρητά")
    if c2.button("💳 Κάρτα", use_container_width=True): finalize(dsc, "Κάρτα")

# --- 5. MAIN LOGIC ---
if not st.session_state.logged_in:
    if st.text_input("Password", type="password") == "CHERRY123":
        st.session_state.logged_in = True; st.rerun()
else:
    with st.sidebar:
        st.write(get_athens_now().strftime('%d/%m/%Y %H:%M'))
        if HAS_MIC:
            cmd = speech_to_text(language='el', key=f"v_{st.session_state.mic_key}")
            if cmd:
                nums = re.findall(r"\d+", cmd)
                if nums:
                    p = float(nums[0])
                    p = -p if st.session_state.return_mode else p
                    st.session_state.cart.append({'bc':'VOICE','name':cmd.upper(),'price':p})
                    st.session_state.mic_key+=1; st.rerun()
        view = st.radio("Menu", ["🛒 ΤΑΜΕΙΟ", "🔄 ΕΠΙΣΤΡΟΦΗ", "📊 MANAGER", "📦 ΑΠΟΘΗΚΗ", "👥 ΠΕΛΑΤΕΣ", "⚙️ SYSTEM"])
        st.session_state.return_mode = (view == "🔄 ΕΠΙΣΤΡΟΦΗ")
        if st.button("❌ EXIT"): st.session_state.logged_in=False; st.rerun()

    cv = view if view != "🔄 ΕΠΙΣΤΡΟΦΗ" else "🛒 ΤΑΜΕΙΟ"

    if cv == "🛒 ΤΑΜΕΙΟ":
        st.write(f"👤 {st.session_state.cust_name}")
        cl, cr = st.columns([1, 1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"ph_{st.session_state.ph_key}")
                if len(ph)==10:
                    res = supabase.table("customers").select("*").eq("phone", ph).execute()
                    if res.data: st.session_state.update({"selected_cust_id":res.data[0]['id'], "cust_name":res.data[0]['name']}); st.rerun()
                    else: new_customer_popup(ph)
                if st.button("🛒 ΛΙΑΝΙΚΗ"): st.session_state.selected_cust_id=0; st.rerun()
            else:
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    res = supabase.table("inventory").select("*").eq("barcode", bc).execute()
                    if res.data:
                        val = -float(res.data[0]['price']) if st.session_state.return_mode else float(res.data[0]['price'])
                        st.session_state.cart.append({'bc':bc,'name':res.data[0]['name'],'price':val})
                        st.session_state.bc_key+=1; st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ", use_container_width=True): payment_popup()
                if st.button("🔄 ΑΚΥΡΩΣΗ"): reset_app()
        with cr:
            tot = sum(i['price'] for i in st.session_state.cart)
            st.markdown(f"<div class='cart-area'>{chr(10).join([f'{i.get('name')[:15]} | {i.get('price')}€' for i in st.session_state.cart])}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{tot:.2f}€</div>", unsafe_allow_html=True)

    elif cv == "📊 MANAGER":
        res_s = supabase.table("sales").select("*").execute()
        if res_s.data:
            df = pd.DataFrame(res_s.data)
            df['s_date_dt'] = pd.to_datetime(df['s_date'])
            df['ΗΜΕΡΟΜΗΝΙΑ'] = df['s_date_dt'].dt.date
            today = get_athens_now().date()
            t1, t2, t3 = st.tabs(["📅 ΣΗΜΕΡΑ", "📆 ΠΕΡΙΟΔΟΣ", "📈 INSIGHTS"])
            
            with t1:
                tdf = df[df['ΗΜΕΡΟΜΗΝΙΑ'] == today]
                st.metric("Τζίρος", f"{tdf['final_item_price'].sum():.2f}€")
                st.dataframe(tdf, use_container_width=True)
            with t2:
                sd = st.date_input("Από", today-timedelta(7))
                ed = st.date_input("Έως", today)
                pdf = df[(df['ΗΜΕΡΟΜΗΝΙΑ'] >= sd) & (df['ΗΜΕΡΟΜΗΝΙΑ'] <= ed)]
                st.metric("Τζίρος Περιόδου", f"{pdf['final_item_price'].sum():.2f}€")
                st.dataframe(pdf, use_container_width=True)
            with t3:
                # Insights based on pdf (Tab 2 dates)
                pdf_in = df[(df['ΗΜΕΡΟΜΗΝΙΑ'] >= sd) & (df['ΗΜΕΡΟΜΗΝΙΑ'] <= ed)]
                if not pdf_in.empty:
                    c1, c2 = st.columns(2)
                    top = pdf_in.groupby('item_name')['final_item_price'].sum().nlargest(5)
                    c1.write("Top 5 Προϊόντα (€)"); c1.table(top)
                    fig = px.pie(pdf_in, values='final_item_price', names='method', title="Μεθοδος Πληρωμής")
                    c2.plotly_chart(fig, use_container_width=True)
                    pdf_in['hour'] = pdf_in['s_date_dt'].dt.hour
                    hourly = pdf_in.groupby('hour')['final_item_price'].sum().reset_index()
                    st.plotly_chart(px.line(hourly, x='hour', y='final_item_price', title="Τζίρος ανά Ώρα"), use_container_width=True)
                else: st.info("Όχι δεδομένα")

    elif cv == "📦 ΑΠΟΘΗΚΗ":
        with st.form("inv_f"):
            c1,c2,c3,c4 = st.columns(4)
            b = c1.text_input("BC"); n = c2.text_input("Όνομα")
            p = c3.number_input("Τιμή"); s = c4.number_input("Stock")
            if st.form_submit_button("Save"):
                supabase.table("inventory").upsert({"barcode":b,"name":n.upper(),"price":p,"stock":s}).execute(); st.rerun()
        res = supabase.table("inventory").select("*").execute()
        if res.data: st.table(res.data)

    elif cv == "👥 ΠΕΛΑΤΕΣ":
        res = supabase.table("customers").select("*").execute()
        if res.data: st.table(res.data)

    elif cv == "⚙️ SYSTEM":
        if st.text_input("System Pass", type="password") == "999":
            target = st.selectbox("Delete Table", ["---", "sales", "customers", "inventory"])
            if target != "---" and st.button("ΔΙΑΓΡΑΦΗ"):
                supabase.table(target).delete().neq("id", -1).execute(); st.success("OK")
