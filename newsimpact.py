import streamlit as st
import pandas as pd
import yfinance as yf
import feedparser
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh

# 1. SETUP: Refresh every 2 minutes (120,000ms) to avoid Rate Limits
st_autorefresh(interval=120000, key="nifty_stable_refresh")
IST = pytz.timezone('Asia/Kolkata')
st.set_page_config(page_title="Nifty 50 Strategic Hub", layout="wide")

# 2. CACHED DATA FETCHING: Prevents YFRateLimitError
@st.cache_data(ttl=300) # Cache market data for 5 minutes
def get_nifty_price():
    try:
        ticker = yf.Ticker("^NSEI")
        # Use a longer period to ensure we get data even on weekends/holidays
        hist = ticker.history(period="5d", interval="1m")
        if not hist.empty:
            last_close = hist['Close'].iloc[-1]
            # Use the most recent 'Open' from the same session
            last_open = hist['Open'].iloc[-1] 
            return last_close, last_open
        return None, None
    except Exception:
        return None, None

# 3. DYNAMIC NEWS LOGIC (Scraping last 7 days from RSS)
def analyze_headline(title):
    t = title.lower()
    if any(k in t for k in ['trump', 'iran', 'war', 'strike', 'missile', 'lockdown', 'covid']):
        return "🔴 Critical (Negative)", 10, "High-stakes geopolitical/health crisis."
    if any(k in t for k in ['rbi', 'fed', 'interest rate', 'inflation', 'cpi', 'oil', 'brent']):
        return "🟠 High", 8, "Macro-economic shift affecting liquidity."
    if any(k in t for k in ['earnings', 'q4', 'profit', 'loss', 'tcs', 'hcltech', 'reliance']):
        return "🟡 Moderate", 6, "Corporate performance driving index."
    return "⚪ Low", 2, "General market news."

def fetch_dynamic_news():
    sources = ["https://moneycontrol.com", 
               "https://indiatimes.com"]
    news_list = []
    # Hardcoded historical items for April 2nd recovery (since RSS clears after 24h)
    historical_items = [
        ["Trump’s Iran Strike Threat", "02-Apr 09:15 AM", "🔴 Critical (Negative)", 10, "Trump overnight speech triggered gap-down on war fears."],
        ["RBI Currency Intervention", "02-Apr 01:30 PM", "🔴 Critical (Positive)", 9, "RBI NDF restrictions caused 188-paise Rupee rebound."]
    ]
    
    for url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                impact, weight, logic = analyze_headline(entry.title)
                pub_time = datetime(*entry.published_parsed[:6]).replace(tzinfo=pytz.utc).astimezone(IST)
                news_list.append([entry.title, pub_time.strftime("%d %b, %I:%M %p"), impact, weight, logic])
        except: continue
    
    df = pd.DataFrame(news_list + historical_items, columns=["Topic", "Exact Timing", "Impact Level", "Weight (1-10)", "Logic Behind Impact"])
    return df.drop_duplicates(subset=['Topic'])

# 4. UI RENDER
st.title("🏛️ Nifty 50: Strategic Impact Dashboard")

df_active = fetch_dynamic_news()
today_score = sum([row for row in df_active.values.tolist() if "02-Apr" in str(row)])
gauge_color = "red" if today_score > 30 else "orange" if today_score > 15 else "green"
st.subheader(f"Current Market Intensity: :{gauge_color}[{today_score} / 50]")
st.progress(min(today_score / 50, 1.0))

# TABLES
def get_clean_table(df):
    rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2, "⚪ Low": 3}
    df['Sort_Key'] = df['Impact Level'].apply(lambda x: next((v for k, v in rank.items() if k in str(x)), 99))
    df = df.sort_values('Sort_Key').drop(columns=['Sort_Key'])
    return df.style.map(lambda v: f"color: {'red' if 'Critical' in str(v) else 'orange' if 'High' in str(v) else 'black'}; font-weight: bold;", subset=['Impact Level'])

st.header("🔴 Active & Recent Events (Past 7 Days)")
st.table(get_clean_table(df_active))

# SIDEBAR: REORGANIZED & RATE-LIMIT PROOF
st.sidebar.error("📍 **Bengaluru Weekend Alert:**")
st.sidebar.write("The **US Fed meeting** (end of April) is a **9/10 weight**. Major driver for FII flows.")
st.sidebar.markdown("---")

st.sidebar.header("NSE: NIFTY 50")
curr_p, open_p = get_nifty_price()
if curr_p:
    st.sidebar.metric("Last Price", f"{curr_p:,.2f}", f"{(curr_p - open_p):+.2f}")
    st.sidebar.write(f"IST Update: {datetime.now(IST).strftime('%H:%M:%S')}")
else:
    st.sidebar.warning("Rate Limit Active: Retrying in 2 mins...")

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Weight & Sentiment Guide")
st.sidebar.write("**9-10/10:** 'Market Changers'.")
st.sidebar.write("**31-50 Total:** 'High Stress' zone.")
