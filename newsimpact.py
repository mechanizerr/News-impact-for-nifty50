import streamlit as st
import pandas as pd
import yfinance as yf
import feedparser
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# 1. SETUP: Auto-refresh every 60 seconds
st_autorefresh(interval=60000, key="nifty_refresh")

st.set_page_config(page_title="Auto-Nifty Impact Dashboard", layout="wide")
st.title("📊 Nifty 50 Real-Time Event & News Feed")

# 2. DATA SOURCE: Fetch Live RSS News
def fetch_nifty_impact_news():
    # Economic Times - Indian Business RSS Feed
    RSS_URL = "https://indiatimes.com"
    feed = feedparser.parse(RSS_URL)
    
    events = []
    for entry in feed.entries[:8]:  # Get latest 8 news items
        # Simple Logic: Assign impact based on keywords in title
        title = entry.title.lower()
        impact = "Medium"
        if any(word in title for word in ['crash', 'surge', 'rbi', 'fed', 'war', 'oil']):
            impact = "High"
        
        events.append({
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Event": entry.title,
            "Impact Level": impact,
            "Source": "Economic Times"
        })
    return pd.DataFrame(events)

# 3. RENDER: Impact Table
st.header("Today's Active Impact Events")
with st.spinner('Updating Impact Table...'):
    df_impact = fetch_nifty_impact_news()
    if not df_impact.empty:
        # Highlighting High Impact rows
        st.dataframe(df_impact.style.apply(lambda x: ['background-color: #ffcccc' if v == 'High' else '' for v in x], axis=1), use_container_width=True)
    else:
        st.write("Waiting for new market triggers...")

# 4. RENDER: Live Market Metrics (Sidebar)
st.sidebar.header("Nifty 50 Live Status")
nifty = yf.Ticker("^NSEI")
nifty_data = nifty.history(period="1d", interval="1m")

if not nifty_data.empty:
    current_price = nifty_data['Close'].iloc[-1]
    prev_close = nifty_data['Open'].iloc[0]
    change = current_price - prev_close
    st.sidebar.metric("NIFTY 50", f"{current_price:,.2f}", f"{change:+.2f}")
    st.sidebar.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 5. FUTURE EVENTS (Static but crucial)
st.markdown("---")
st.header("📅 Upcoming Major Global Events")
future_data = {
    "Date": ["April 9, 2026", "April 15, 2026", "TBD"],
    "Event": ["Q4 Earnings (TCS Reporting)", "US Inflation (CPI) Data", "RBI MPC Meeting"],
    "Expected Impact": ["High", "High", "Critical"]
}
st.table(pd.DataFrame(future_data))
