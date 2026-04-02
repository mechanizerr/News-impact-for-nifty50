import streamlit as st
import pandas as pd
import feedparser
import yfinance as yf
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# 1. SETUP: Auto-refresh every 1 minute
st_autorefresh(interval=60000, key="nifty_refresh_1min")

# Timezone for Bengaluru
IST = pytz.timezone('Asia/Kolkata')
st.set_page_config(page_title="Nifty 50 Smart Tracker", layout="wide")

# 2. IMPACT LOGIC ENGINE (Historical & Government)
def get_impact_details(headline):
    h = headline.lower()
    # Topic | Impact Weight | Logic
    if any(x in h for x in ['trump', 'iran', 'strike', 'war']):
        return "Trump/Iran Conflict", "High (Negative)", "Geopolitical escalation triggers global 'risk-off' and FII outflows."
    if any(x in h for x in ['oil', 'brent', 'crude']):
        return "Crude Oil Spike", "Moderate (Negative)", "Higher import bill threatens India's fiscal deficit and inflation."
    if any(x in h for x in ['rbi', 'intervention', 'rupee', 'ndf']):
        return "RBI Intervention", "High (Positive)", "Curbs on currency speculation support the Rupee and stabilize markets."
    if any(x in h for x in ['fii', 'selling', 'offload']):
        return "FII Panic Selling", "Moderate (Negative)", "Foreign capital fleeing to safe havens like USD amid global uncertainty."
    if any(x in h for x in ['pmi', 'manufacturing', 'industrial']):
        return "Manufacturing PMI", "Low (Negative)", "Slowing industrial momentum weighs on heavy machinery and auto stocks."
    if any(x in h for x in ['tariff', 'us trade', 'steel', 'pharma']):
        return "US Import Tariffs", "Low (Negative)", "Potential 25% tariffs create drag on Export-oriented Nifty sectors."
    if any(x in h for x in ['tcs', 'reliance', 'hdfc', 'earnings', 'q4']):
        return "Corporate Earnings", "High (Neutral)", "Blue-chip results dictate the immediate trend for the Nifty 50 index."
    
    return "Market Volatility", "Low", "General price action based on intraday liquidity and sentiment."

# 3. DATA FETCHING
def fetch_live_impact():
    sources = ["https://indiatimes.com", 
               "https://moneycontrol.com"]
    data = []
    for url in sources:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            topic, weight, logic = get_impact_details(entry.title)
            data.append({
                "Topic": topic,
                "Exact Timing": datetime.now(IST).strftime("%I:%M %p"),
                "Impact Weight": weight,
                "Logic Behind Impact": logic,
                "Live Headline": entry.title
            })
    return pd.DataFrame(data).drop_duplicates(subset=['Topic'])

# 4. UI LAYOUT
st.title("🏛️ Nifty 50: Strategic Impact Dashboard")
st.write(f"📍 Monitoring from **Bengaluru** | Last Refresh: {datetime.now(IST).strftime('%I:%M:%S %p')}")

if st.button("🔄 Force Manual Refresh"):
    st.rerun()

# --- TABLE 1: ACTIVE EVENTS TILL NOW ---
st.header("🔴 Active Events (Today's Session)")
df_live = fetch_live_impact()
if not df_live.empty:
    # Color coding the Impact Weight
    def color_weight(val):
        color = '#ffcccc' if 'High' in val else '#fff4cc' if 'Moderate' in val else '#e6f3ff'
        return f'background-color: {color}'
    
    st.table(df_live.style.applymap(color_weight, subset=['Impact Weight']))

# --- TABLE 2: FUTURE EVENTS ---
st.markdown("---")
st.header("📅 Future Major Events (Nifty 50 Impact)")
future_data = [
    ["Good Friday Holiday", "April 3, 2026 (All Day)", "No Impact", "Markets closed; potential position squaring happening today."],
    ["TCS Q4 FY26 Results", "April 9, 2026 (Post-Market)", "High", "Sets the tone for the IT sector and overall Nifty earnings growth."],
    ["US CPI Inflation", "April 15, 2026 (06:00 PM)", "High", "Impacts Fed rate cut expectations and FII flows into India."],
    ["RBI MPC Meeting", "Mid-April 2026", "Critical", "Directly impacts Bank Nifty and rate-sensitive sectors (Auto/Realty)."]
]
df_future = pd.DataFrame(future_data, columns=["Topic", "Exact Timing", "Impact Weight", "Logic Behind Impact"])
st.table(df_future)

# --- SIDEBAR: LIVE NIFTY ---
st.sidebar.header("NSE: NIFTY 50")
nifty = yf.Ticker("^NSEI").history(period="1d", interval="1m")
if not nifty.empty:
    curr = nifty['Close'].iloc[-1]
    change = curr - nifty['Open'].iloc[0]
    st.sidebar.metric("Current Value", f"{curr:,.2f}", f"{change:+.2f}")
st.sidebar.info("Auto-refreshing every 60 seconds.")
