import streamlit as st
import pandas as pd
import feedparser
import yfinance as yf
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh

# 1. INITIAL SETUP
IST = pytz.timezone('Asia/Kolkata')
st.set_page_config(page_title="Nifty 50: 7-Day Impact Monitor", layout="wide")
st_autorefresh(interval=60000, key="nifty_weekly_refresh")

# 2. STRATEGIC MASTER KEYWORDS (Refined for Sorting)
IMPACT_RANK = {"🔴 Critical": 1, "🟠 High": 2, "🟡 Moderate": 3, "⚪ Low/Neutral": 4}

KEYWORDS = {
    "CRITICAL": ['trump', 'iran', 'strike', 'war', 'lockdown', 'scam', 'crash'],
    "HIGH": ['rbi', 'fed', 'budget', 'gst', 'inflation', 'cpi', 'oil', 'brent', 'fii'],
    "MODERATE": ['earnings', 'q4', 'tcs', 'reliance', 'pmi', 'tariff', 'dividend', 'hcltech']
}

def analyze_impact(title):
    title = title.lower()
    if any(k in title for k in KEYWORDS["CRITICAL"]): return "🔴 Critical"
    if any(k in title for k in KEYWORDS["HIGH"]): return "🟠 High"
    if any(k in title for k in KEYWORDS["MODERATE"]): return "🟡 Moderate"
    return "⚪ Low/Neutral"

# 3. NEWS AGGREGATOR (Past 1 Week)
def get_weekly_nifty_feeds():
    # Multi-source for reliability
    RSS_URLS = [
        "https://indiatimes.com",
        "https://moneycontrol.com",
        "https://livemint.com"
    ]
    
    week_ago = datetime.now(IST) - timedelta(days=7)
    news_data = []

    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # Parse published date
                published = datetime(*entry.published_parsed[:6]).replace(tzinfo=pytz.utc).astimezone(IST)
                
                if published > week_ago:
                    impact = analyze_impact(entry.title)
                    news_data.append({
                        "Topic": entry.title[:60] + "...",
                        "Exact Timing": published.strftime("%d-%b %I:%M %p"),
                        "Impact Weight": impact,
                        "Logic Behind Impact": f"Detected trigger in {entry.title[:30]}",
                        "Raw_Time": published, # For sorting
                        "Rank": IMPACT_RANK.get(impact, 4) # For sorting
                    })
        except: continue
    
    df = pd.DataFrame(news_data).drop_duplicates(subset=['Topic'])
    # SORTING: Impact Level First (Rank 1 to 4), then Latest Time
    if not df.empty:
        df = df.sort_values(by=['Rank', 'Raw_Time'], ascending=[True, False]).drop(columns=['Raw_Time', 'Rank'])
    return df

# 4. UI RENDER
st.title("🏛️ Nifty 50: 7-Day Strategic Impact Dashboard")
st.info(f"📍 Location: Bengaluru | Monitoring Window: { (datetime.now(IST)-timedelta(days=7)).strftime('%d %b') } to Today")

if st.button("🔄 Force Refresh All Feeds"):
    st.rerun()

# --- TABLE 1: ACTIVE EVENTS (PAST WEEK) ---
st.header("🔴 Active & Recent Events (Sorted by Impact)")
df_active = get_weekly_nifty_feeds()

if not df_active.empty:
    st.dataframe(df_active.style.apply(lambda x: [
        'background-color: #ffcccc' if 'Critical' in v else 
        'background-color: #ffe0b3' if 'High' in v else '' for v in x
    ], axis=1), use_container_width=True)
else:
    st.write("No major impact events detected in the last 7 days.")

# --- TABLE 2: FUTURE EVENTS ---
st.markdown("---")
st.header("📅 Future Major Events (Scheduled Triggers)")
future_data = [
    ["Good Friday Holiday", "April 3, 2026", "No Impact", "Market Closed; Weekly settlements complete."],
    ["TCS Q4 FY26 Results", "April 9, 2026", "🟠 High", "IT sector earnings heavy-weight sets the index direction."],
    ["US CPI Inflation", "April 15, 2026", "🟠 High", "Crucial for FII flow sentiment and global rate outlook."],
    ["RBI MPC Meeting", "Mid-April 2026", "🔴 Critical", "Interest rate decision directly impacts Banking and Auto stocks."]
]
df_future = pd.DataFrame(future_data, columns=["Topic", "Exact Timing", "Impact Weight", "Logic Behind Impact"])
st.table(df_future)

# --- SIDEBAR: LIVE METRICS ---
st.sidebar.header("NSE: NIFTY 50")
nifty = yf.Ticker("^NSEI").history(period="1d", interval="1m")
if not nifty.empty:
    price = nifty['Close'].iloc[-1]
    change = price - nifty['Open'].iloc[0]
    st.sidebar.metric("Live Index", f"{price:,.2f}", f"{change:+.2f}")
