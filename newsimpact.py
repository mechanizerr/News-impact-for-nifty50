import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# 1. INITIAL SETUP & 1-MINUTE AUTO REFRESH
st.set_page_config(page_title="Nifty 50 Strategic Impact Hub", layout="wide")
st_autorefresh(interval=60000, key="nifty_final_production_v3")
IST = pytz.timezone('Asia/Kolkata')

# 2. DATASET A: ACTIVE & RECENT EVENTS (PAST 7 DAYS)
ACTIVE_EVENTS_DATA = [
    ["Trump’s Iran Strike Threat", "02-Apr 09:15 AM", "🔴 Critical (Negative)", 10, "President Trump's overnight speech triggered a 426-point gap-down on war fears."],
    ["RBI Currency Intervention", "02-Apr 01:30 PM", "🔴 Critical (Positive)", 9, "RBI restricted banks from NDFs; Rupee rebounded 188 paise from record lows."],
    ["Crude Oil Price Spike", "01-Apr 09:15 AM", "🟠 High (Negative)", 8, "Brent crude surged to $108.52/bbl, threatening India's fiscal stability."],
    ["FII Panic Selling", "30-Mar 12:30 PM", "🟠 High (Negative)", 7, "FIIs offloaded ₹11,163 cr; selling peaked during European market open."],
    ["DII Liquidity Support", "30-Mar 02:30 PM", "🟠 High (Positive)", 7, "Domestic institutions bought ₹14,894 cr to cushion the aggressive FII exit."],
    ["Value Buying in IT Sector", "02-Apr 02:00 PM", "🟡 Moderate (Positive)", 5, "HCLTech and TCS jumped ~3% as a hedge against Rupee volatility."],
    ["Manufacturing PMI", "01-Apr 10:30 AM", "🟡 Moderate (Negative)", 4, "PMI fell to 45-month low of 53.9, indicating cooling industrial momentum."],
    ["Short Covering at 22,200", "02-Apr 02:30 PM", "🟡 Moderate (Positive)", 4, "Nifty held support, forcing bears to cover and pushing index to 22,700."],
    ["US Import Tariff Reports", "30-Mar 11:00 AM", "⚪ Low (Negative)", 2, "Potential 25% tariffs on steel/pharma created minor mid-day sector drag."]
]

# 3. DATASET B: FUTURE MAJOR EVENTS (NEXT 30 DAYS)
FUTURE_EVENTS_DATA = [
    ["Good Friday Holiday", "April 3, 2026", "No Impact", 0, "Markets Closed; No Trading today."],
    ["RBI MPC Meeting", "April 6-8, 2026", "🔴 Critical", 9, "First rate decision of FY27; focus on inflation and geopolitics."],
    ["TCS Q4 FY26 Results", "April 9, 2026", "🟠 High", 7, "IT earnings benchmark will dictate index direction on Friday open."],
    ["India CPI Inflation", "April 13, 2026", "🟠 High", 6, "Key indicator for future interest rate cuts; impacts next-day open."],
    ["HCL Tech Q4 Results", "April 21, 2026", "🟠 High", 6, "Major benchmark for Nifty IT index and guidance."],
    ["US Fed FOMC Meeting", "April 28-29, 2026", "🔴 Critical", 9, "Global rate outlook and FII capital flow trigger for Indian open."]
]

# 4. STYLING UTILITIES
def get_clean_table(data_list):
    df = pd.DataFrame(data_list, columns=["Topic", "Exact Timing", "Impact Level", "Weight (1-10)", "Logic Behind Impact"])
    rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2, "⚪ Low": 3, "No Impact": 4}
    df['Sort_Key'] = df['Impact Level'].apply(lambda x: next((v for k, v in rank.items() if k in x), 99))
    df = df.sort_values('Sort_Key').drop(columns=['Sort_Key'])
    def style_impact_text(val):
        color = 'red' if 'Critical' in str(val) else 'orange' if 'High' in str(val) else 'gold' if 'Moderate' in str(val) else 'black'
        return f'color: {color}; font-weight: bold;'
    return df.style.map(style_impact_text, subset=['Impact Level'])

# 5. MAIN UI LAYOUT
st.title("🏛️ Nifty 50: Strategic Impact Dashboard")

# NET SENTIMENT SCORE & GAUGE
today_score = sum([row[3] for row in ACTIVE_EVENTS_DATA if "02-Apr" in row[1]])

# Dynamic Gauge Color
gauge_color = "red" if today_score > 30 else "orange" if today_score > 15 else "green"
st.subheader(f"Current Market Intensity: :{gauge_color}[{today_score} / 50]")
st.progress(today_score / 50)

st.info(f"📍 Bengaluru Hub | Last Refresh: {datetime.now(IST).strftime('%d %b, %I:%M:%S %p')}")

# --- TABLE 1: ACTIVE EVENTS ---
st.header("🔴 Active & Recent Events (Sorted by Priority)")
st.table(get_clean_table(ACTIVE_EVENTS_DATA))

# --- TABLE 2: FUTURE EVENTS ---
st.markdown("---")
st.header("📅 One-Month Future Outlook (Scheduled Triggers)")
st.table(get_clean_table(FUTURE_EVENTS_DATA))

# --- MARKET GUIDE: READ ME ---
st.markdown("---")
st.header("📖 How to Read Net Sentiment")
col1, col2 = st.columns(2)
with col1:
    st.write("**0 - 15 (Low):** Sideways market; narrow price range.")
    st.write("**16 - 30 (Active):** Clear trend forming; 100-200 point intraday moves.")
with col2:
    st.write("**31 - 45 (Stress):** Major volatility; expect 300+ point gaps.")
    st.write("**46 - 50 (Black Swan):** Extreme risk; potential circuit breakers.")

# --- SIDEBAR: REORGANIZED LAYOUT ---
# TOP: Alert
st.sidebar.error("📍 **Bengaluru Weekend Alert:**")
st.sidebar.write("The **US Fed meeting** (end of April) is a **9/10 weight**. This will be the biggest driver for FII flows into Indian tech stocks in May.")
st.sidebar.markdown("---")

# MIDDLE: Live Index
st.sidebar.header("NSE: NIFTY 50")
nifty_ticker = yf.Ticker("^NSEI")
nifty_hist = nifty_ticker.history(period="1d", interval="1m")

if not nifty_hist.empty:
    current_price = nifty_hist['Close'].iloc[-1]
    opening_price = nifty_hist['Open'].iloc[0] # Fixed .iloc[0] for stability
    price_change = current_price - opening_price
    st.sidebar.metric("Live Index", f"{current_price:,.2f}", f"{price_change:+.2f}")
    st.sidebar.write(f"IST Update: {datetime.now(IST).strftime('%H:%M:%S')}")
else:
    st.sidebar.warning("Market Closed (Good Friday Holiday)")
st.sidebar.markdown("---")

# BOTTOM: Weight Reference
st.sidebar.subheader("⚖️ Weight & Sentiment Guide")
st.sidebar.markdown("**Weights (1-10):**")
st.sidebar.write("• **9-10/10:** 'Market Changers'. Expect 300+ point gaps.")
st.sidebar.write("• **6-8/10:** 'Trend Setters'. 100-200 point moves.")
st.sidebar.write("• **Under 5/10:** 'Daily Volatility'.")

st.sidebar.markdown("**Net Sentiment (Total):**")
st.sidebar.write("• **31-50:** 'High Stress' zone.")
st.sidebar.write("• **16-30:** 'Active Trend' zone.")
st.sidebar.write("• **0-15:** 'Sideways' zone.")
