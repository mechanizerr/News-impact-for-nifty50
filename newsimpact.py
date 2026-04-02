import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# 1. INITIAL SETUP & 1-MINUTE AUTO REFRESH
st.set_page_config(page_title="Nifty 50 Strategic Impact Hub", layout="wide")
st_autorefresh(interval=60000, key="nifty_master_final_v2")
IST = pytz.timezone('Asia/Kolkata')

# 2. DATASET A: ACTIVE & RECENT EVENTS (PAST 7 DAYS)
ACTIVE_EVENTS_DATA = [
    ["Trump’s Iran Strike Threat", "02-Apr 09:15 AM", "🔴 Critical (Negative)", "President Trump's overnight speech triggered a 426-point gap-down on war fears."],
    ["RBI Currency Intervention", "02-Apr 01:30 PM", "🔴 Critical (Positive)", "RBI restricted banks from NDFs; Rupee rebounded 188 paise from record lows."],
    ["Crude Oil Price Spike", "01-Apr 09:15 AM", "🟠 High (Negative)", "Brent crude surged to $108.52/bbl, threatening India's fiscal stability."],
    ["FII Panic Selling", "30-Mar (Session)", "🟠 High (Negative)", "FIIs offloaded ₹11,163 cr in one day due to global 'risk-off' sentiment."],
    ["DII Liquidity Support", "30-Mar (Session)", "🟠 High (Positive)", "Domestic institutions bought ₹14,894 cr to cushion the FII exit."],
    ["Value Buying in IT Sector", "02-Apr 02:00 PM", "🟡 Moderate (Positive)", "HCLTech and TCS jumped ~3% as a hedge against Rupee volatility."],
    ["Manufacturing PMI", "01-Apr 10:30 AM", "🟡 Moderate (Negative)", "PMI fell to 45-month low of 53.9, indicating cooling industrial momentum."],
    ["Short Covering at 22,200", "02-Apr 02:30 PM", "🟡 Moderate (Positive)", "Nifty held support, forcing bears to cover and pushing index to 22,700."],
    ["US Import Tariff Reports", "30-Mar 11:00 AM", "⚪ Low (Negative)", "Potential 25% tariffs on steel/pharma created minor sector drag."]
]

# 3. DATASET B: FUTURE MAJOR EVENTS (NEXT 30 DAYS)
FUTURE_EVENTS_DATA = [
    ["Good Friday Holiday", "April 3, 2026", "No Impact", "Markets Closed; No Trading today."],
    ["RBI MPC Meeting", "April 6-8, 2026", "🔴 Critical", "First rate decision of FY27; focus on inflation and geopolitics."],
    ["TCS Q4 FY26 Results", "April 9, 2026", "🟠 High", "IT earnings benchmark will dictate index direction."],
    ["India CPI Inflation", "April 13, 2026", "🟠 High", "Key indicator for future interest rate cuts."],
    ["Ambedkar Jayanti", "April 14, 2026", "No Impact", "Mid-week market holiday; segments closed."],
    ["HCL Tech Q4 Results", "April 21, 2026", "🟠 High", "Major benchmark for Nifty IT index and guidance."],
    ["US Fed FOMC Meeting", "April 28-29, 2026", "🔴 Critical", "Global rate outlook and FII capital flow trigger."],
    ["Maharashtra Day", "May 1, 2026", "No Impact", "Market Holiday; trading closed."]
]

# 4. SORTING & CELL-ONLY STYLING (FIXED Attribute Error)
def get_clean_table(data_list):
    df = pd.DataFrame(data_list, columns=["Topic", "Exact Timing", "Impact Weight", "Logic Behind Impact"])
    
    # Priority for Sorting
    rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2, "⚪ Low": 3, "No Impact": 4}
    df['Sort_Key'] = df['Impact Weight'].apply(lambda x: next((v for k, v in rank.items() if k in x), 99))
    df = df.sort_values('Sort_Key').drop(columns=['Sort_Key'])

    # FIXED: Style only the 'Impact Weight' column text (using .map instead of .applymap)
    def style_impact_text(val):
        color = 'red' if 'Critical' in str(val) else 'orange' if 'High' in str(val) else 'gold' if 'Moderate' in str(val) else 'black'
        return f'color: {color}; font-weight: bold;'

    # .map is the correct method for newer Pandas versions used in Streamlit Cloud
    return df.style.map(style_impact_text, subset=['Impact Weight'])

# 5. UI LAYOUT
st.title("🏛️ Nifty 50: Strategic Impact Dashboard")
st.info(f"📍 Monitoring from **Bengaluru** | Last Refresh: {datetime.now(IST).strftime('%d %b, %I:%M:%S %p')}")

if st.button("🔄 Force Refresh Feed Now"):
    st.rerun()

# --- TABLE 1: ACTIVE EVENTS ---
st.header("🔴 Active & Recent Events (Sorted by Priority)")
st.table(get_clean_table(ACTIVE_EVENTS_DATA))

# --- TABLE 2: FUTURE EVENTS ---
st.markdown("---")
st.header("📅 One-Month Future Outlook (Scheduled Triggers)")
st.table(get_clean_table(FUTURE_EVENTS_DATA))

# --- SIDEBAR: LIVE INDEX TRACKER ---
st.sidebar.header("NSE: NIFTY 50")
nifty_ticker = yf.Ticker("^NSEI")
nifty_hist = nifty_ticker.history(period="1d", interval="1m")

if not nifty_hist.empty:
    current_price = nifty_hist['Close'].iloc[-1]
    opening_price = nifty_hist['Open'].iloc[0] 
    price_change = current_price - opening_price
    st.sidebar.metric("Live Index", f"{current_price:,.2f}", f"{price_change:+.2f}")
    st.sidebar.write(f"IST Update: {datetime.now(IST).strftime('%H:%M:%S')}")
else:
    st.sidebar.warning("Market Closed (Good Friday Holiday)")

st.sidebar.markdown("---")
st.sidebar.write("✅ **Keywords Monitored:** RBI, Fed, Trump, War, Oil, COVID, Lockdown, GST, PMI, FII.")
