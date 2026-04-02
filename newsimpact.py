import streamlit as st
import pandas as pd
import feedparser
import yfinance as yf
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# 1. AUTO-REFRESH: Set to 60,000ms (1 minute)
# This will rerun the entire script automatically every 60 seconds.
st_autorefresh(interval=60000, key="nifty_refresh_1min")

# 2. TIMEZONE & CONFIG
IST = pytz.timezone('Asia/Kolkata')
st.set_page_config(page_title="Nifty 50 Pro Monitor", layout="wide")

# 3. MASTER KEYWORDS (Historical & Government Triggers)
KEYWORDS = {
    "CRITICAL": ['covid', 'lockdown', 'pandemic', 'virus', 'variant', 'war', 'missile', 'attack', 'scam', 'crash'],
    "GOVERNMENT": ['rbi', 'repo rate', 'gst', 'budget', 'nirmala sitharaman', 'modi', 'fdi', 'regulation', 'sebi', 'tariff'],
    "CORPORATE": ['dividend', 'bonus', 'earnings', 'q4', 'q3', 'profit', 'loss', 'tcs', 'reliance', 'hdfc'],
    "GLOBAL": ['fed', 'inflation', 'cpi', 'gdp', 'brent crude', 'oil price', 'fii', 'dii']
}

def analyze_impact(title):
    title = title.lower()
    if any(k in title for k in KEYWORDS["CRITICAL"]): return "🔴 Critical Impact"
    if any(k in title for k in KEYWORDS["GOVERNMENT"]): return "🟠 High (Govt Policy)"
    if any(k in title for k in KEYWORDS["CORPORATE"]): return "🟡 Medium (Corporate)"
    if any(k in title for k in KEYWORDS["GLOBAL"]): return "🔵 High (Global Macro)"
    return "⚪ Low/Neutral"

# 4. DATA FETCHING
def get_nifty_feeds():
    sources = {
        "Moneycontrol": "https://moneycontrol.com",
        "Economic Times": "https://indiatimes.com",
        "LiveMint": "https://livemint.com"
    }
    news_data = []
    for name, url in sources.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                news_data.append({
                    "Source": name,
                    "Headline": entry.title,
                    "Impact": analyze_impact(entry.title),
                    "Time (IST)": datetime.now(IST).strftime("%H:%M:%S")
                })
        except: continue
    return pd.DataFrame(news_data)

# 5. UI RENDER
st.title("🏛️ Nifty 50 Pro: Policy & Impact Monitor")
st.write(f"📍 Monitoring Active from **Bengaluru** | Last Sync: {datetime.now(IST).strftime('%I:%M %p')}")

if st.button("🔄 Force Refresh Feed"):
    st.rerun()

# TABLE 1: Real-Time News (Updates every 60s)
st.subheader("🔴 Real-Time Impact Feed")
df_news = get_nifty_feeds()
if not df_news.empty:
    st.dataframe(df_news.style.apply(lambda x: [
        'background-color: #ffcccc' if 'Critical' in v else 
        'background-color: #ffe0b3' if 'Govt' in v else '' for v in x
    ], axis=1), use_container_width=True)

# TABLE 2: Future Events
st.markdown("---")
st.subheader("📅 Major Future Events (Scheduled)")
future_events = [
    {"Date": "April 3, 2026", "Event": "Good Friday (Market Holiday)", "Expected Impact": "No Trading"},
    {"Date": "April 9, 2026", "Event": "TCS Q4 FY26 Results", "Expected Impact": "High (IT Sector)"},
    {"Date": "April 15, 2026", "Event": "India WPI Inflation Data", "Expected Impact": "Medium"},
    {"Date": "Mid-April 2026", "Event": "RBI Monetary Policy Review", "Expected Impact": "High (Banking/Auto)"}
]
st.table(pd.DataFrame(future_events))

# SIDEBAR: LIVE INDEX (Updates every 60s)
st.sidebar.header("NSE: NIFTY 50")
nifty_ticker = yf.Ticker("^NSEI")
nifty_hist = nifty_ticker.history(period="1d", interval="1m")

if not nifty_hist.empty:
    price = nifty_hist['Close'].iloc[-1]
    # Fixed indexing for Price Change calculation
    change = price - nifty_hist['Open'].iloc[0] 
    st.sidebar.metric("Live Price", f"{price:,.2f}", f"{change:+.2f}")
else:
    st.sidebar.warning("Market is Closed or Fetching Data...")
