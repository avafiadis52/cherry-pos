import pandas as pd
from datetime import datetime, date, timedelta
import time, streamlit as st, re
from supabase import create_client, Client

try:
    from streamlit_mic_recorder import speech_to_text
    HAS_MIC = True
except ImportError:
    HAS_MIC = False

SUPABASE_URL = "https://hnwynihjkdkryrfepenh.supabase.co"
SUPABASE_KEY = "sb_publishable_ualF72lJKgUQA4TzjPQ-OA_zih7zJ-s"

@st.cache_resource
def init_supabase(): return create_client(SUPABASE_URL, SUPABASE_KEY)
supabase = init_supabase()

st.set_page_config(page_title="CHERRY v14.0.63", layout="wide", page_icon="🍒")
st.markdown("""<style>.stApp{background-color:#1a1a1a;color:white;}label,p{color:#fff!important;font-weight:700!important;}.cart-area{font-family:monospace;background-color:#2b2b2b;padding:15px;border-radius:5px;white-space:pre-wrap;border:1px solid #3b3b3b;min-height:200px;font-size:14px;}.total-label{font-size:60px;font-weight:bold;color:#2ecc71;text-align:center;}.status-header{font-size:20px;font-weight:bold;color:#3498db;text-align:center;margin-bottom:10px;}.final-amount-popup{font-size:40px;font-weight:bold;color:#e44d26;text-align:center;padding:10px;border-radius:10px;background-color:#fff3f0;border:2px solid #e44d26;}div.stButton>button{background-color:#d3d3d3!important;color:#000!important;border-radius:8px!important;font-weight:bold!important;}.data-row{background-color:#262626;padding:10px;border-radius:8px;margin-bottom:5px;border-left:5px solid #3498db;}.sidebar-date{color:#f1c40f;font-size:18px;font-weight:bold;margin-bottom:20px;border-bottom:1px solid #444;padding-bottom:10px;}.report-stat{background-color:#262730;padding:10px;border-radius:8px;text-align:center;border:1px solid #444;margin-bottom:5px;}.grand-stat{background-color:#1e272e;border:2px solid #2ecc71;padding:15px;border-radius:10px;text-align:center;margin-bottom:20px;}.stat-val{font-size:20px;font-weight:bold;color:#2ecc71;margin:0;}.stat-label{font-size:11px;color:#888;margin:0;font-weight:bold;text-transform:uppercase;}.day-title{color:#f1c40f;font-size:22px;font-weight:bold;border-bottom:2px solid #f1c40f;margin-top:30px;margin-bottom:15px;padding-bottom:5px;}</style>""", unsafe_allow_html=True)

for key, val in [('cart',[]),('selected_cust_id',None),('cust_name',"Λιανική Πώληση"),('bc_key',0),('ph_key',100),('is_logged_out',False),('last_speech',None),('mic_key',500)]:
    if key not in st.session_state: st.session_state[key] = val

def get_athens_now(): return datetime.now() + timedelta(hours=2)
def reset_app():
    for k in ['cart','selected_cust_id','last_speech']: st.session_state[k] = [] if k=='cart' else None
    st.session_state.cust_name, st.session_state.bc_key, st.session_state.ph_key, st.session_state.mic_key = "Λιανική Πώληση", st.session_state.bc_key+1, st.session_state.ph_key+1, st.session_state.mic_key+1
    st.rerun()

def play_sound(url): st.components.v1.html(f'<audio autoplay style="display:none"><source src="{url}" type="audio/mpeg"></audio>', height=0)

@st.dialog("➕ Χειροκίνητο")
def manual_item_popup():
    n, p = st.text_input("Όνομα"), st.number_input("Τιμή", min_value=0.0)
    if st.button("Προσθήκη"):
        if n: st.session_state.cart.append({'bc':'999','name':n,'price':round(float(p),2)}); st.session_state.bc_key+=1; st.rerun()

@st.dialog("🆕 Νέος Πελάτης")
def new_customer_popup(phone=""):
    n, ph = st.text_input("Όνομα"), st.text_input("Τηλέφωνο", value=phone)
    if st.button("Αποθήκευση"):
        res = supabase.table("customers").insert({"name":n,"phone":ph}).execute()
        if res.data: st.session_state.selected_cust_id, st.session_state.cust_name = res.data[0]['id'], res.data[0]['name']; st.success("OK"); time.sleep(0.5); st.rerun()

def finalize(disc, method):
    sub = sum(i['price'] for i in st.session_state.cart)
    ratio, ts, aid = (disc/sub if sub>0 else 0), get_athens_now().strftime("%Y-%m-%d %H:%M:%S"), int(time.time())
    cid = st.session_state.selected_cust_id if st.session_state.selected_cust_id != 0 else None
    try:
        for i in st.session_state.cart:
            d, f = round(i['price']*ratio,2), round(i['price']-(i['price']*ratio),2)
            supabase.table("sales").insert({"barcode":str(i['bc']),"item_name":str(i['name']),"unit_price":float(i['price']),"discount":float(d),"final_item_price":float(f),"method":str(method),"s_date":ts,"cust_id":cid,"action_id":aid}).execute()
            if i['bc']!='999':
                curr = supabase.table("inventory").select("stock").eq("barcode",i['bc']).execute()
                if curr.data: supabase.table("inventory").update({"stock":curr.data[0]['stock']-1}).eq("barcode",i['bc']).execute()
        st.success("✅ ΕΠΙΤΥΧΙΑ"); st.balloons(); play_sound("https://www.soundjay.com/misc/sounds/magic-chime-01.mp3"); time.sleep(1.2); reset_app()
    except Exception as e: st.error(str(e))

@st.dialog("💰 Πληρωμή")
def payment_popup():
    tot = sum(i['price'] for i in st.session_state.cart)
    st.markdown(f"<h3 style='text-align:center;'>Σύνολο: {tot:.2f}€</h3>", unsafe_allow_html=True)
    if st.radio("Έκπτωση;",["ΟΧΙ","ΝΑΙ"],horizontal=True)=="ΝΑΙ":
        inp = st.text_input("Ποσό ή %")
        disc = round((float(inp.replace("%",""))/100*tot if "%" in inp else float(inp)),2) if inp else 0.0
    else: disc = 0.0
    st.markdown(f"<div class='final-amount-popup'>ΠΛΗΡΩΤΕΟ: {tot-disc:.2f}€</div>", unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    if c1.button("💵 Μετρητά"): finalize(disc,"Μετρητά")
    if c2.button("💳 Κάρτα"): finalize(disc,"Κάρτα")

if st.session_state.is_logged_out:
    if st.button("Επανασύνδεση"): st.session_state.is_logged_out=False; st.rerun()
else:
    with st.sidebar:
        st.markdown(f"<div class='sidebar-date'>{get_athens_now().strftime('%d/%m/%Y %H:%M:%S')}</div>", unsafe_allow_html=True)
        if HAS_MIC:
            text = speech_to_text(language='el', start_prompt="🔊 Φωνητική Εντολή", key=f"mic_{st.session_state.mic_key}")
            if text and text != st.session_state.last_speech:
                st.session_state.last_speech = text
                cmd = text.lower().strip()
                res = supabase.table("inventory").select("*").ilike("name",f"%{cmd}%").execute()
                if res.data:
                    it = res.data[0]
                    st.session_state.cart.append({'bc':it['barcode'],'name':it['name'],'price':float(it['price'])})
                    st.rerun()
                else:
                    nums = re.findall(r"\d+\.?\d*", cmd.replace(",","."))
                    if nums:
                        p = float(nums[0])
                        n = cmd.replace(str(nums[0]),"").replace("ευρώ","").strip() or "Είδος"
                        st.session_state.cart.append({'bc':'999','name':n.capitalize(),'price':p})
                        st.rerun()
        view = st.radio("Μενού",["🛒 ΤΑΜΕΙΟ","📊 MANAGER","📦 ΑΠΟΘΗΚΗ","👥 ΠΕΛΑΤΕΣ"])
        if st.button("❌ Έξοδος"): st.session_state.is_logged_out=True; st.rerun()

    if view == "🛒 ΤΑΜΕΙΟ":
        st.markdown(f"<div class='status-header'>Πελάτης: {st.session_state.cust_name}</div>", unsafe_allow_html=True)
        cl, cr = st.columns([1,1.5])
        with cl:
            if st.session_state.selected_cust_id is None:
                ph = st.text_input("Τηλέφωνο", key=f"ph_{st.session_state.ph_key}")
                if ph and len(ph)==10:
                    r = supabase.table("customers").select("*").eq("phone",ph).execute()
                    if r.data: st.session_state.selected_cust_id, st.session_state.cust_name = r.data[0]['id'], r.data[0]['name']; st.rerun()
                    else: new_customer_popup(ph)
                if st.button("🛒 ΛΙΑΝΙΚΗ ΠΩΛΗΣΗ"): st.session_state.selected_cust_id=0; st.rerun()
            else:
                st.button(f"👤 {st.session_state.cust_name} (Αλλαγή)", on_click=lambda:st.session_state.update({"selected_cust_id":None,"cust_name":"Λιανική Πώληση"}))
                bc = st.text_input("Barcode", key=f"bc_{st.session_state.bc_key}")
                if bc:
                    if bc=="999": manual_item_popup()
                    else:
                        r = supabase.table("inventory").select("*").eq("barcode",bc).execute()
                        if r.data: st.session_state.cart.append({'bc':r.data[0]['barcode'],'name':r.data[0]['name'],'price':float(r.data[0]['price'])}); st.session_state.bc_key+=1; st.rerun()
                for idx, i in enumerate(st.session_state.cart):
                    if st.button(f"❌ {i['name']} {i['price']}€", key=f"d_{idx}"): st.session_state.cart.pop(idx); st.rerun()
                if st.session_state.cart and st.button("💰 ΠΛΗΡΩΜΗ"): payment_popup()
        with cr:
            total = sum(i['price'] for i in st.session_state.cart)
            lines = [f"{i['name'][:20]:<20} | {i['price']:>6.2f}€" for i in st.session_state.cart]
            st.markdown(f"<div class='cart-area'>{'Είδος':<20} | {'Τιμή':>6}\n{'-'*30}\n{chr(10).join(lines)}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='total-label'>{total:.2f}€</div>", unsafe_allow_html=True)

    elif view == "📊 MANAGER":
        st.title("📊 Dashboard")
        res = supabase.table("sales").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['date'] = pd.to_datetime(df['s_date']).dt.date
            t_df = df[df['date'] == get_athens_now().date()]
            c1,c2 = st.columns(2)
            c1.metric("Μετρητά Σήμερα", f"{t_df[t_df['method']=='Μετρητά']['final_item_price'].sum():.2f}€")
            c2.metric("Κάρτα Σήμερα", f"{t_df[t_df['method']=='Κάρτα']['final_item_price'].sum():.2f}€")
            st.dataframe(df.sort_values('s_date',ascending=False), use_container_width=True)

    elif view == "📦 ΑΠΟΘΗΚΗ":
        with st.form("inv"):
            c1,c2,c3,c4 = st.columns(4)
            b,n,p,s = c1.text_input("BC"), c2.text_input("Όνομα"), c3.number_input("Τιμή"), c4.number_input("Stock")
            if st.form_submit_button("OK") and b and n: supabase.table("inventory").upsert({"barcode":b,"name":n,"price":p,"stock":s}).execute(); st.rerun()
        for r in supabase.table("inventory").select("*").execute().data:
            st.markdown(f"<div class='data-row'>{r['barcode']} | {r['name']} | {r['price']}€ | Stock: {r['stock']}</div>", unsafe_allow_html=True)

    elif view == "👥 ΠΕΛΑΤΕΣ":
        for r in supabase.table("customers").select("*").execute().data:
            st.markdown(f"<div class='data-row'>👤 {r['name']} | 📞 {r['phone']}</div>", unsafe_allow_html=True)
            if st.button("Διαγραφή", key=f"c_{r['id']}"): supabase.table("customers").delete().eq("id",r['id']).execute(); st.rerun()
