import streamlit as st
import pandas as pd
import yfinance as yf
import feedparser
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz

# 1. TIMEZONE SETUP: Force Bengaluru/Kolkata Time
IST = pytz.timezone('Asia/Kolkata')
current_time_ist = datetime.now(IST).strftime('%Y-%m-%d %I:%M:%S %p')

# 2. AUTO-REFRESH: Update every 30 seconds
st_autorefresh(interval=30000, key="nifty_refresh_ist")

st.set_page_config(page_title="Nifty 50 Bengaluru Hub", layout="wide")
st.title(f"🚀 Nifty 50 Live Impact Dashboard")
st.subheader(f"📍 Monitoring from Bengaluru | {current_time_ist}")

# 3. LIVE TABLE: Automated News & Impact
def fetch_ist_news():
    RSS_URL = "https://indiatimes.com"
    feed = feedparser.parse(RSS_URL)
    events = []
    for entry in feed.entries[:6]:
        # Basic logic for impact
        impact = "High" if any(x in entry.title.lower() for x in ['rbi', 'fed', 'crash', 'surge']) else "Medium"
        events.append({
            "Event": entry.title,
            "Impact": impact,
            "Justification": "Real-time feed trigger from Economic Times."
        })
    return pd.DataFrame(events)

st.header("Today's Market Movers")
df = fetch_ist_news()
st.table(df)

# 4. SIDEBAR: LIVE NIFTY PRICE
st.sidebar.header("NSE: NIFTY 50")
nifty = yf.Ticker("^NSEI").history(period="1d", interval="1m")
if not nifty.empty:
    price = nifty['Close'].iloc[-1]
    change = price - nifty['Open'].iloc[0]
    st.sidebar.metric("Live Index", f"{price:,.2f}", f"{change:+.2f}")

st.sidebar.info("Market Hours: 09:15 - 15:30 IST")
