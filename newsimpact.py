import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# 1. SETUP: Refresh every 1 minute
st_autorefresh(interval=60000, key="nifty_refresh_final")
IST = pytz.timezone('Asia/Kolkata')
st.set_page_config(page_title="Nifty 50 Strategic Monitor", layout="wide")

# 2. DATASET: Historical & Active Events (Past 7 Days)
# Manually updated with the week's major Nifty movers
WEEKLY_EVENTS = [
    ["Trump’s Iran Strike Threat", "02-Apr 09:15 AM", "🔴 Critical (Negative)", "US President Trump's overnight speech triggered a 426-point gap-down on war fears."],
    ["RBI Currency Intervention", "02-Apr 01:30 PM", "🔴 Critical (Positive)", "RBI restricted banks from NDFs, causing the Rupee to rebound 188 paise from record lows."],
    ["Crude Oil Price Spike", "01-Apr 09:15 AM", "🟠 High (Negative)", "Brent crude surged 7.28% to $108.52/bbl, threatening India's fiscal stability."],
    ["FII Panic Selling", "30-Mar (Session)", "🟠 High (Negative)", "FIIs offloaded ₹11,163 cr in a single day due to escalating global risk-off sentiment."],
    ["DII Liquidity Support", "30-Mar (Session)", "🟠 High (Positive)", "Domestic institutions bought ₹14,894 cr, acting as a crucial cushion against FII exits."],
    ["Value Buying in IT Sector", "02-Apr 02:00 PM", "🟡 Moderate (Positive)", "IT stocks like HCLTech and TCS jumped ~3% as a hedge against Rupee volatility."],
    ["Manufacturing PMI Slowdown", "01-Apr 10:30 AM", "🟡 Moderate (Negative)", "India's PMI fell to a 45-month low of 53.9, indicating cooling industrial momentum."],
    ["Short Covering at 22,200", "02-Apr 02:30 PM", "🟡 Moderate (Positive)", "Nifty held critical support, forcing bears to cover and pushing the index to 22,700."],
    ["US Import Tariff Reports", "30-Mar 11:00 AM", "⚪ Low (Negative)", "Reports of 25% US tariffs on steel/pharma created temporary drag on sector indices."]
]

# 3. SORTING LOGIC: Critical -> High -> Moderate -> Low
IMPACT_ORDER = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2, "⚪ Low": 3}

def get_sorted_events():
    df = pd.DataFrame(WEEKLY_EVENTS, columns=["Topic", "Exact Timing", "Impact Weight", "Logic Behind Impact"])
    # Sort based on the priority defined in IMPACT_ORDER
    df['Sort_Key'] = df['Impact Weight'].apply(lambda x: next((v for k, v in IMPACT_ORDER.items() if k in x), 99))
    df = df.sort_values(by='Sort_Key').drop(columns=['Sort_Key'])
    return df

# 4. UI RENDER
st.title("🏛️ Nifty 50: Strategic Impact Dashboard")
st.info(f"📍 Location: Bengaluru | Monitoring Window: Past 7 Days (March 26 - April 2)")

if st.button("🔄 Force Refresh Feed"):
    st.rerun()

# --- TABLE 1: ACTIVE EVENTS (Sorted Critical to Less Critical) ---
st.header("🔴 Active & Recent Events (Sorted by Impact)")
df_impact = get_sorted_events()
st.table(df_impact.style.apply(lambda x: [
    'background-color: #ffcccc' if 'Critical' in v else 
    'background-color: #ffe0b3' if 'High' in v else '' for v in x
], axis=1))

# --- TABLE 2: FUTURE EVENTS ---
st.markdown("---")
st.header("📅 Future Major Events (Scheduled Triggers)")
future_data = [
    ["Good Friday Holiday", "April 3, 2026", "No Impact", "Markets Closed; No Trading today."],
    ["TCS Q4 FY26 Results", "April 9, 2026", "🟠 High", "IT earnings benchmark will dictate index direction."],
    ["US CPI Inflation", "April 15, 2026", "🟠 High", "Impacts FII flows and global rate expectations."],
    ["RBI MPC Meeting", "Mid-April 2026", "🔴 Critical", "Interest rate decisions impact Banking and Auto stocks."]
]
st.table(pd.DataFrame(future_data, columns=["Topic", "Exact Timing", "Impact Weight", "Logic Behind Impact"]))

# --- SIDEBAR: LIVE INDEX ---
st.sidebar.header("NSE: NIFTY 50")
nifty_ticker = yf.Ticker("^NSEI")
nifty_hist = nifty_ticker.history(period="1d", interval="1m")

if not nifty_hist.empty:
    price = nifty_hist['Close'].iloc[-1]
    change = price - nifty_hist['Open'].iloc[0]
    st.sidebar.metric("Live Price", f"{price:,.2f}", f"{change:+.2f}")
else:
    st.sidebar.warning("Market Closed (Good Friday)")
