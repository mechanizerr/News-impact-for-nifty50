import streamlit as st
import pandas as pd
import yfinance as yf
import feedparser
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz

# 1. SETUP: IST Timezone
IST = pytz.timezone('Asia/Kolkata')

# 2. AUTO-REFRESH: Every 60 seconds
st_autorefresh(interval=60000, key="nifty_timer")

st.set_page_config(page_title="Nifty 50 Pro Dashboard", layout="wide")

# 3. MANUAL FORCE REFRESH BUTTON
col_title, col_refresh = st.columns([4, 1])
with col_title:
    st.title("🚀 Nifty 50 Active Impact Feed")
with col_refresh:
    if st.button("🔄 Force Refresh Now"):
        st.rerun()

# 4. MULTI-SOURCE FAST FEED
def get_aggregated_news():
    # Faster and higher-impact news sources for Indian markets
    RSS_SOURCES = {
        "CNBC-TV18": "https://cnbctv18.com",
        "Zee Business": "https://zeebiz.com",
        "LiveMint Markets": "https://www.livemint.com/rss/markets",
        "Economic Times": "https://indiatimes.com"
    }
    
    all_events = []
    for source_name, url in RSS_SOURCES.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]: # Top 3 from each
                title_low = entry.title.lower()
                # Dynamic Impact Logic based on market-moving keywords
                impact = "High" if any(word in title_low for word in ['rbi', 'fed', 'trump', 'war', 'oil', 'crash', 'surge', 'tariff']) else "Medium"
                
                all_events.append({
                    "Source": source_name,
                    "Event": entry.title,
                    "Impact Level": impact,
                    "Timestamp (IST)": datetime.now(IST).strftime("%H:%M:%S")
                })
        except:
            continue
    return pd.DataFrame(all_events)

# 5. RENDER IMPACT TABLE
st.header("🔴 Live Market Triggers")
df_news = get_aggregated_news()

if not df_news.empty:
    # Highlight High Impact events in red
    def highlight_high(s):
        return ['background-color: #ffcccc' if v == 'High' else '' for v in s]
    
    st.dataframe(df_news.style.apply(highlight_high, axis=1), use_container_width=True)
else:
    st.warning("Fetching live data... Please ensure you are connected to the internet.")

# 6. SIDEBAR: REAL-TIME NIFTY 50
st.sidebar.header("NSE: NIFTY 50")
nifty_ticker = yf.Ticker("^NSEI")
nifty_hist = nifty_ticker.history(period="1d", interval="1m")

if not nifty_hist.empty:
    current_val = nifty_hist['Close'].iloc[-1]
    open_val = nifty_hist['Open'].iloc[0]
    change = current_val - open_val
    st.sidebar.metric("Current Index", f"{current_val:,.2f}", f"{change:+.2f}")
    st.sidebar.write(f"Updated at: {datetime.now(IST).strftime('%H:%M:%S')} IST")
