import streamlit as st
import pandas as pd
import yfinance as yf
import feedparser
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh

# 1. INITIAL SETUP & 1-MINUTE AUTO REFRESH
st.set_page_config(page_title="Nifty 50 Strategic Impact Hub", layout="wide")
st_autorefresh(interval=60000, key="nifty_master_7day_v1")
IST = pytz.timezone('Asia/Kolkata')

# 2. DYNAMIC LOGIC ENGINE
def analyze_headline(title):
    t = title.lower()
    if any(k in t for k in ['trump', 'iran', 'war', 'strike', 'missile', 'lockdown', 'covid']):
        return "🔴 Critical (Negative)", 10, "High-stakes geopolitical or health crisis trigger."
    if any(k in t for k in ['rbi', 'fed', 'interest rate', 'inflation', 'cpi', 'oil', 'brent']):
        return "🟠 High", 8, "Macro-economic shift affecting fiscal stability/liquidity."
    if any(k in t for k in ['earnings', 'q4', 'profit', 'loss', 'tcs', 'hcltech', 'reliance']):
        return "🟡 Moderate", 6, "Corporate performance driving sectoral index movement."
    if any(k in t for k in ['fii', 'dii', 'selling', 'buying', 'pmi']):
        return "🟡 Moderate", 5, "Institutional flow or industrial data sentiment."
    return "⚪ Low", 2, "General market news with minor index impact."

# 3. DYNAMIC DATA FETCHING (PAST 1 WEEK AGGREGATOR)
def fetch_weekly_active_events():
    sources = [
        "https://moneycontrol.com",
        "https://livemint.com",
        "https://indiatimes.com"
    ]
    news_list = []
    # LOOKBACK: Exactly 7 days from now
    lookback_date = datetime.now(IST) - timedelta(days=7)
    
    for url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # Parse published time
                pub_time = datetime(*entry.published_parsed[:6]).replace(tzinfo=pytz.utc).astimezone(IST)
                
                if pub_time > lookback_date:
                    impact, weight, logic = analyze_headline(entry.title)
                    news_list.append([entry.title, pub_time.strftime("%d %b, %I:%M %p"), impact, weight, logic])
        except: continue
    
    # Remove duplicates based on headline
    df_temp = pd.DataFrame(news_list, columns=["Topic", "Exact Timing", "Impact Level", "Weight (1-10)", "Logic Behind Impact"])
    df_temp = df_temp.drop_duplicates(subset=['Topic'])
    return df_temp.values.tolist()

# 4. DATASETS
ACTIVE_EVENTS_DATA = fetch_weekly_active_events()

FUTURE_EVENTS_DATA = [
    ["Good Friday Holiday", "April 3, 2026", "No Impact", 0, "Markets Closed; No Trading today."],
    ["RBI MPC Meeting", "April 6-8, 2026", "🔴 Critical", 9, "First rate decision of FY27; focus on inflation."],
    ["TCS Q4 FY26 Results", "April 9, 2026", "🟠 High", 7, "IT earnings benchmark will dictate index direction."],
    ["US Fed FOMC Meeting", "April 28-29, 2026", "🔴 Critical", 9, "Global rate outlook and FII capital flow trigger."]
]

# 5. STYLING UTILITIES
def get_clean_table(data_list):
    df = pd.DataFrame(data_list, columns=["Topic", "Exact Timing", "Impact Level", "Weight (1-10)", "Logic Behind Impact"])
    rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2, "⚪ Low": 3, "No Impact": 4}
    df['Sort_Key'] = df['Impact Level'].apply(lambda x: next((v for k, v in rank.items() if k in x), 99))
    df = df.sort_values('Sort_Key').drop(columns=['Sort_Key'])
    def style_impact_text(val):
        color = 'red' if 'Critical' in str(val) else 'orange' if 'High' in str(val) else 'gold' if 'Moderate' in str(val) else 'black'
        return f'color: {color}; font-weight: bold;'
    return df.style.map(style_impact_text, subset=['Impact Level'])

# 6. UI LAYOUT
st.title("🏛️ Nifty 50: Strategic Impact Dashboard")

# Sentiment Gauge (Calculated from today's triggers in the weekly list)
today_str = datetime.now(IST).strftime("%d %b")
today_score = sum([row[3] for row in ACTIVE_EVENTS_DATA if today_str in row[1]])
gauge_color = "red" if today_score > 30 else "orange" if today_score > 15 else "green"
st.subheader(f"Current Market Intensity: :{gauge_color}[{today_score} / 50]")
st.progress(min(today_score / 50, 1.0))

st.info(f"📍 Bengaluru Hub | Monitoring Window: Last 7 Days | Sync: {datetime.now(IST).strftime('%I:%M %p')}")

if st.button("🔄 Force Refresh Feed Now"):
    st.rerun()

# --- TABLE 1: ACTIVE EVENTS (PAST 7 DAYS) ---
st.header("🔴 Active & Recent Events (Past 7 Days)")
st.table(get_clean_table(ACTIVE_EVENTS_DATA))

# --- TABLE 2: FUTURE EVENTS ---
st.markdown("---")
st.header("📅 One-Month Future Outlook (Scheduled Triggers)")
st.table(get_clean_table(FUTURE_EVENTS_DATA))

# --- MARKET GUIDE ---
st.markdown("---")
st.header("📖 How to Read Net Sentiment")
col1, col2 = st.columns(2)
with col1:
    st.write("**0 - 15 (Low):** Sideways market; stable conditions.")
    st.write("**16 - 30 (Active):** Clear trend; 100-200 point intraday moves.")
with col2:
    st.write("**31 - 45 (Stress):** Major volatility; expect 300+ point gaps.")
    st.write("**46 - 50 (Black Swan):** Extreme risk; circuit breaker potential.")

# --- SIDEBAR REORGANIZED ---
st.sidebar.error("📍 **Bengaluru Weekend Alert:**")
st.sidebar.write("The **US Fed meeting** (end of April) is a **9/10 weight**. Major driver for FII flows into IT.")
st.sidebar.markdown("---")

st.sidebar.header("NSE: NIFTY 50")
nifty_ticker = yf.Ticker("^NSEI")
nifty_hist = nifty_ticker.history(period="1d", interval="1m")
if not nifty_hist.empty:
    current_p = nifty_hist['Close'].iloc[-1]
    opening_p = nifty_hist['Open'].iloc[0] # FIXED INDEXING
    change = current_p - opening_p
    st.sidebar.metric("Live Index", f"{current_p:,.2f}", f"{change:+.2f}")
else:
    st.sidebar.warning("Market Closed (Good Friday Holiday)")
st.sidebar.markdown("---")

st.sidebar.subheader("⚖️ Weight & Sentiment Guide")
st.sidebar.markdown("**Weights (1-10):**")
st.sidebar.write("• **9-10/10:** 'Market Changers'. Expect 300+ point gaps.")
st.sidebar.write("• **6-8/10:** 'Trend Setters'. 100-200 point moves.")
st.sidebar.write("• **Under 5/10:** 'Daily Volatility'.")
st.sidebar.markdown("**Net Sentiment (Total):**")
st.sidebar.write("• **31-50:** 'High Stress' zone.")
st.sidebar.write("• **16-30:** 'Active Trend' zone.")
st.sidebar.write("• **0-15:** 'Sideways' zone.")
