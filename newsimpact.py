import streamlit as st
import pandas as pd
import yfinance as yf
import feedparser
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh

# 1. SETUP: Refresh every 2 minutes to avoid Rate Limits on Streamlit Cloud
st_autorefresh(interval=120000, key="nifty_stable_refresh_v2")
IST = pytz.timezone('Asia/Kolkata')
st.set_page_config(page_title="Nifty 50 Strategic Hub", layout="wide")

# 2. CACHED MARKET DATA: Prevents YFRateLimitError
@st.cache_data(ttl=300) 
def get_nifty_data():
    try:
        ticker = yf.Ticker("^NSEI")
        hist = ticker.history(period="5d", interval="1m")
        if not hist.empty:
            return hist['Close'].iloc[-1], hist['Open'].iloc[-1]
    except:
        return None, None
    return None, None

# 3. DYNAMIC LOGIC ENGINE
def analyze_headline(title):
    t = title.lower()
    if any(k in t for k in ['trump', 'iran', 'war', 'strike', 'missile', 'lockdown', 'covid']):
        return "🔴 Critical (Negative)", 10, "High-stakes geopolitical/health crisis trigger."
    if any(k in t for k in ['rbi', 'fed', 'interest rate', 'inflation', 'cpi', 'oil', 'brent']):
        return "🟠 High", 8, "Macro-economic shift affecting fiscal stability."
    if any(k in t for k in ['earnings', 'q4', 'profit', 'loss', 'tcs', 'hcltech', 'reliance']):
        return "🟡 Moderate", 6, "Corporate performance driving sectoral index movement."
    return "⚪ Low", 2, "General market news with minor index impact."

# 4. DATA FETCHING (Live RSS + Historical Backup)
def fetch_dynamic_news():
    sources = ["https://moneycontrol.com", 
               "https://indiatimes.com"]
    
    # Static backup for the week's biggest moves (since RSS clears quickly)
    historical_items = [
        ["Trump’s Iran Strike Threat", "02 Apr, 09:15 AM", "🔴 Critical (Negative)", 10, "Trump speech triggered 426-pt gap-down on war fears."],
        ["RBI Currency Intervention", "02 Apr, 01:30 PM", "🔴 Critical (Positive)", 9, "RBI NDF curbs caused 188-paise Rupee rebound."],
        ["FII Panic Selling", "30 Mar, 12:30 PM", "🟠 High (Negative)", 7, "FIIs offloaded ₹11,163 cr during European open."]
    ]
    
    live_news = []
    for url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                impact, weight, logic = analyze_headline(entry.title)
                pub_time = datetime(*entry.published_parsed[:6]).replace(tzinfo=pytz.utc).astimezone(IST)
                live_news.append([entry.title, pub_time.strftime("%d %b, %I:%M %p"), impact, weight, logic])
        except: continue
    
    full_list = live_news + historical_items
    df = pd.DataFrame(full_list, columns=["Topic", "Exact Timing", "Impact Level", "Weight (1-10)", "Logic Behind Impact"])
    return df.drop_duplicates(subset=['Topic'])

# 5. UI RENDER
st.title("🏛️ Nifty 50: Strategic Impact Dashboard")

df_active = fetch_dynamic_news()

# FIXED: Sum only the Weight column for today's date (02 Apr)
today_data = df_active[df_active['Exact Timing'].str.contains("02 Apr")]
today_score = today_data["Weight (1-10)"].sum()

gauge_color = "red" if today_score > 30 else "orange" if today_score > 15 else "green"
st.subheader(f"Current Market Intensity: :{gauge_color}[{today_score} / 50]")
st.progress(min(today_score / 50, 1.0))

st.info(f"📍 Bengaluru Hub | Last Refresh: {datetime.now(IST).strftime('%I:%M %p')}")

# --- TABLE 1: ACTIVE EVENTS ---
def get_clean_table(df):
    rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2, "⚪ Low": 3}
    df['Sort_Key'] = df['Impact Level'].apply(lambda x: next((v for k, v in rank.items() if k in str(x)), 99))
    df = df.sort_values('Sort_Key').drop(columns=['Sort_Key'])
    return df.style.map(lambda v: f"color: {'red' if 'Critical' in str(v) else 'orange' if 'High' in str(v) else 'black'}; font-weight: bold;", subset=['Impact Level'])

st.header("🔴 Active & Recent Events (Past 7 Days)")
st.table(get_clean_table(df_active))

# --- SIDEBAR (RATE LIMIT PROTECTED) ---
st.sidebar.error("📍 **Bengaluru Weekend Alert:**")
st.sidebar.write("The **US Fed meeting** (end of April) is a **9/10 weight**. Major driver for FII flows into IT.")
st.sidebar.markdown("---")

st.sidebar.header("NSE: NIFTY 50")
curr_p, open_p = get_nifty_data()
if curr_p:
    st.sidebar.metric("Last Price", f"{curr_p:,.2f}", f"{(curr_p - open_p):+.2f}")
    st.sidebar.write(f"IST Update: {datetime.now(IST).strftime('%H:%M:%S')}")
else:
    st.sidebar.warning("Rate Limit: Retrying in 2 mins...")

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Weight & Sentiment Guide")
st.sidebar.write("**9-10/10:** 'Market Changers'.")
st.sidebar.write("**31-50 Total:** 'High Stress' zone.")
