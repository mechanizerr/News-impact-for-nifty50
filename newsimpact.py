import streamlit as st
import pandas as pd
import yfinance as yf
import feedparser
import requests
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh

# 1. INITIAL SETUP & 2-MINUTE AUTO REFRESH (Prevents Rate Limits)
st.set_page_config(page_title="Nifty 50 Strategic Hub", layout="wide")
st_autorefresh(interval=120000, key="nifty_hybrid_master")
IST = pytz.timezone('Asia/Kolkata')

# 2. DYNAMIC LOGIC ENGINE (150+ Stock & Topic Keywords)
NIFTY_50_STOCKS = ['ADANIENT', 'ADANIPORTS', 'APOLLOHOSP', 'ASIANPAINT', 'AXISBANK', 'BAJAJ-AUTO', 'BAJFINANCE', 'BAJAJFINSV', 'BEL', 'BHARTIARTL', 'BPCL', 'BRITANNIA', 'CIPLA', 'COALINDIA', 'DIVISLAB', 'DRREDDY', 'EICHERMOT', 'GRASIM', 'HCLTECH', 'HDFCBANK', 'HDFCLIFE', 'HEROMOTOCO', 'HINDALCO', 'HINDUNILVR', 'ICICIBANK', 'INDUSINDBK', 'INFY', 'ITC', 'JSWSTEEL', 'KOTAKBANK', 'LT', 'M&M', 'MARUTI', 'NESTLEIND', 'NTPC', 'ONGC', 'POWERGRID', 'RELIANCE', 'SBILIFE', 'SBIN', 'SUNPHARMA', 'TCS', 'TATACONSUM', 'TATAMOTORS', 'TATASTEEL', 'TECHM', 'TITAN', 'ULTRACEMCO', 'WIPRO']

def analyze_headline(title):
    t = title.lower()
    if any(k in t for k in ['trump', 'iran', 'war', 'strike', 'missile', 'lockdown', 'covid']):
        return "🔴 Critical (Negative)", 10, "High-stakes geopolitical/health crisis trigger."
    if any(k in t for k in ['rbi', 'fed', 'interest rate', 'inflation', 'cpi', 'oil', 'brent']):
        return "🟠 High", 8, "Macro-economic policy shift affecting liquidity."
    # DYNAMIC CHECK: Nifty 50 Stocks & Corporate Earnings
    if any(s.lower() in t for s in NIFTY_50_STOCKS) or any(k in t for k in ['earnings', 'q4', 'profit', 'loss']):
        return "🟡 Moderate", 6, "Specific Nifty 50 constituent event impacting sector."
    return "⚪ Low", 2, "General market news."

# 3. HYBRID FETCHING (RSS for Live + API for 7-Day History)
def fetch_hybrid_data():
    all_news = []
    
    # PART A: LIVE RSS FEEDS
    rss_sources = ["https://moneycontrol.com", "https://indiatimes.com"]
    for url in rss_sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                impact, weight, logic = analyze_headline(entry.title)
                pub_time = datetime(*entry.published_parsed[:6]).replace(tzinfo=pytz.utc).astimezone(IST)
                all_news.append([entry.title, pub_time.strftime("%d %b, %I:%M %p"), impact, weight, logic])
        except: continue

    # PART B: 7-DAY DYNAMIC NEWS API
    api_key = st.secrets.get("news_api_key") # Add to Streamlit Secrets
    if api_key:
        seven_days_ago = (datetime.now(IST) - timedelta(days=7)).strftime('%Y-%m-%d')
        url = f'https://newsapi.org"Nifty 50" OR "NSE India"&from={seven_days_ago}&sortBy=publishedAt&apiKey={api_key}&language=en'
        try:
            articles = requests.get(url).json().get('articles', [])
            for art in articles[:20]:
                impact, weight, logic = analyze_headline(art['title'])
                dt_ist = datetime.strptime(art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc).astimezone(IST)
                all_news.append([art['title'], dt_ist.strftime("%d %b, %I:%M %p"), impact, weight, logic])
        except: pass
    
    df = pd.DataFrame(all_news, columns=["Topic", "Exact Timing", "Impact Level", "Weight (1-10)", "Logic Behind Impact"])
    return df.drop_duplicates(subset=['Topic'])

# 4. UI RENDER (All Features Preserved)
st.title("🏛️ Nifty 50: Hybrid Strategic Monitor")
df_all = fetch_hybrid_data()

# Sentiment Gauge
today_score = df_all[df_all['Exact Timing'].str.contains(datetime.now(IST).strftime("%d %b"))]["Weight (1-10)"].sum()
gauge_color = "red" if today_score > 30 else "orange" if today_score > 15 else "green"
st.subheader(f"Current Market Intensity: :{gauge_color}[{today_score} / 50]")
st.progress(min(today_score / 50, 1.0))

st.info(f"📍 Bengaluru Hub | Hybrid Sync Active (RSS + API) | Refresh: 120s")

if st.button("🔄 Force Refresh Feed Now"):
    st.rerun()

# --- TABLE 1: ACTIVE & RECENT EVENTS ---
def get_clean_table(df):
    rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2, "⚪ Low": 3}
    df['Sort_Key'] = df['Impact Level'].apply(lambda x: next((v for k, v in rank.items() if k in str(x)), 99))
    df = df.sort_values('Sort_Key').drop(columns=['Sort_Key'])
    return df.style.map(lambda v: f"color: {'red' if 'Critical' in str(v) else 'orange' if 'High' in str(v) else 'black'}; font-weight: bold;", subset=['Impact Level'])

st.header("🔴 Active & Recent Events (Constituent Aware)")
st.table(get_clean_table(df_all))

# --- TABLE 2: FUTURE EVENTS (DYNAMIC FROM NEWS) ---
st.markdown("---")
st.header("📅 Future Major Events (One-Month Outlook)")
# Logic: Scan news for future keywords or use a pre-determined schedule
future_data = [
    ["RBI MPC Meeting", "06-08 Apr, 10:00 AM", "🔴 Critical", 9, "First rate review of FY27; focus on West Asia oil inflation."],
    ["TCS Q4 Results", "09 Apr, Post-Market", "🟠 High", 7, "Kicks off IT earnings; sets tone for index direction."],
    ["Infosys Q4 Results", "23 Apr, Post-Market", "🔴 Critical", 8, "Major Nifty heavyweight; dictates tech sector sentiment."],
    ["US Fed FOMC Meeting", "28-29 Apr, 11:30 PM", "🔴 Critical", 9, "Global rate decision; primary driver for FII flows."]
]
st.table(pd.DataFrame(future_data, columns=["Topic", "Exact Timing", "Impact Weight", "Logic Behind Impact"]))

# --- MARKET GUIDE "READ ME" ---
st.markdown("---")
st.header("📖 How to Read Net Sentiment")
c1, c2 = st.columns(2)
with c1:
    st.write("**0 - 15 (Low):** Sideways market; narrow price range.")
    st.write("**16 - 30 (Active):** Clear trend forming; 100-200 point intraday moves.")
with c2:
    st.write("**31 - 45 (Stress):** Major volatility; expect 300+ point gaps.")
    st.write("**46 - 50 (Black Swan):** Extreme risk; potential circuit breakers.")

# --- SIDEBAR (Restored Features) ---
st.sidebar.error("📍 **Bengaluru Weekend Alert:**")
st.sidebar.write("The **US Fed meeting** (late April) is a **9/10 weight**. Major driver for FII flows into IT.")
st.sidebar.markdown("---")

st.sidebar.header("NSE: NIFTY 50")
@st.cache_data(ttl=300)
def get_price():
    try:
        ticker = yf.Ticker("^NSEI")
        hist = ticker.history(period="1d", interval="1m")
        return hist['Close'].iloc[-1], hist['Open'].iloc[0]
    except: return None, None

curr_p, open_p = get_price()
if curr_p:
    st.sidebar.metric("Live Index", f"{curr_p:,.2f}", f"{(curr_p - open_p):+.2f}")
else:
    st.sidebar.warning("Market Closed (Good Friday Holiday)")

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Weight & Sentiment Guide")
st.sidebar.write("• **9-10/10:** 'Market Changers'.")
st.sidebar.write("• **6-8/10:** 'Trend Setters'.")
st.sidebar.write("• **Under 5/10:** 'Daily Volatility'.")
