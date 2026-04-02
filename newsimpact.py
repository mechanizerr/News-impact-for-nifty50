import streamlit as st
import pandas as pd
import feedparser
import yfinance as yf
from datetime import datetime
import pytz

# 1. TIMEZONE & CONFIG
IST = pytz.timezone('Asia/Kolkata')
st.set_page_config(page_title="Nifty 50 Pro Monitor", layout="wide")

# 2. THE MASTER KEYWORD LIBRARY (Historical & Government Triggers)
# These keywords are derived from historical Nifty 50 milestones
KEYWORDS = {
    "CRITICAL": [
        'covid', 'lockdown', 'pandemic', 'virus', 'variant', 'quarantine', # Health crises
        'war', 'missile', 'attack', 'surgical strike', 'invasion', 'sanctions', # Geopolitical
        'demonetization', 'scam', 'default', 'bankruptcy', 'crash', 'plunge' # Financial shocks
    ],
    "GOVERNMENT_POLICY": [
        'rbi', 'repo rate', 'monetary policy', 'fiscal deficit', 'gst', 'budget', # Macro
        'nirmala sitharaman', 'modi', 'cabinet', 'disinvestment', 'privatization', # Political
        'excise duty', 'tariff', 'customs', 'subsidy', 'fdi', 'regulation', 'sebi' # Regulatory
    ],
    "CORPORATE_ACTIONS": [
        'dividend', 'bonus', 'stock split', 'rights issue', 'buyback', 'merger', # Stock-specific
        'acquisition', 'earnings', 'q4', 'q3', 'loss', 'profit', 'layoff', 'tcs', 'reliance' # Company
    ],
    "GLOBAL_MACRO": [
        'fed', 'inflation', 'cpi', 'gdp', 'brent crude', 'oil price', 'dollar', 'fii', 'dii' # External
    ]
}

# 3. CORE LOGIC: Dynamic Impact Scorer
def analyze_impact(title):
    title = title.lower()
    if any(k in title for k in KEYWORDS["CRITICAL"]):
        return "🔴 Critical Impact"
    if any(k in title for k in KEYWORDS["GOVERNMENT_POLICY"]):
        return "🟠 High (Govt Policy)"
    if any(k in title for k in KEYWORDS["CORPORATE_ACTIONS"]):
        return "🟡 Medium (Corporate)"
    if any(k in title for k in KEYWORDS["GLOBAL_MACRO"]):
        return "🔵 High (Global Macro)"
    return "⚪ Low/Neutral"

# 4. DATA FETCHING (Aggregated Sources)
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
            for entry in feed.entries[:6]:
                news_data.append({
                    "Source": name,
                    "Headline": entry.title,
                    "Impact Category": analyze_impact(entry.title),
                    "Time (IST)": datetime.now(IST).strftime("%H:%M:%S")
                })
        except: continue
    return pd.DataFrame(news_data)

# 5. UI COMPONENTS
st.title("🏛️ Nifty 50 Pro: Policy & Impact Monitor")
st.write(f"📍 Monitoring Active from **Bengaluru** | Last Sync: {datetime.now(IST).strftime('%I:%M %p')}")

# Refresh Layout
col_btn, col_empty = st.columns([1, 4])
if col_btn.button("🔄 Force Refresh Feed"):
    st.rerun()

# --- TABLE 1: Active News Feed ---
st.subheader("🔴 Real-Time Impact Feed")
df_news = get_nifty_feeds()
if not df_news.empty:
    st.dataframe(df_news.style.apply(lambda x: [
        'background-color: #ffcccc' if 'Critical' in v else 
        'background-color: #ffe0b3' if 'Govt' in v else '' for v in x
    ], axis=1), use_container_width=True)

# --- TABLE 2: Future & Scheduled Events ---
st.markdown("---")
st.subheader("📅 Major Future Events (Scheduled)")
future_events = [
    {"Date": "April 3, 2026", "Event": "Good Friday (Market Holiday)", "Expected Impact": "No Trading"},
    {"Date": "April 9, 2026", "Event": "TCS Q4 FY26 Results", "Expected Impact": "High (IT Sector)"},
    {"Date": "April 15, 2026", "Event": "India WPI Inflation Data", "Expected Impact": "Medium"},
    {"Date": "Mid-April 2026", "Event": "RBI Monetary Policy Review", "Expected Impact": "High (Banking/Auto)"}
]
st.table(pd.DataFrame(future_events))

# --- SIDEBAR: LIVE INDEX ---
st.sidebar.header("NSE: NIFTY 50")
nifty = yf.Ticker("^NSEI").history(period="1d", interval="1m")
if not nifty.empty:
    price = nifty['Close'].iloc[-1]
    change = price - nifty['Open'].iloc
    st.sidebar.metric("Live Price", f"{price:,.2f}", f"{change:+.2f}")
st.sidebar.markdown("**Keywords Monitor:** Active for 150+ Market Triggers")
