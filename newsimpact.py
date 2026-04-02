import streamlit as st
import pandas as pd
import yfinance as yf
import feedparser
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh

# 1. AUTO-REFRESH: Reruns the script every 60 seconds to pull new data
st_autorefresh(interval=60000, key="nifty_dynamic_refresh")
IST = pytz.timezone('Asia/Kolkata')
st.set_page_config(page_title="Nifty 50 Dynamic Hub", layout="wide")

# 2. STRATEGIC KEYWORD ENGINE (For Dynamic Impact Assignment)
def analyze_headline(title):
    t = title.lower()
    # Weights & Logic Mapping
    if any(k in t for k in ['trump', 'iran', 'war', 'strike', 'missile', 'lockdown', 'covid']):
        return "🔴 Critical", 10, "High-stakes geopolitical or health crisis trigger."
    if any(k in t for k in ['rbi', 'fed', 'interest rate', 'inflation', 'cpi', 'oil', 'brent']):
        return "🟠 High", 8, "Macro-economic shift affecting fiscal stability/liquidity."
    if any(k in t for k in ['earnings', 'q4', 'profit', 'loss', 'tcs', 'hcltech', 'reliance']):
        return "🟡 Moderate", 6, "Corporate performance driving sectoral index movement."
    if any(k in t for k in ['fii', 'dii', 'selling', 'buying', 'pmi']):
        return "🟡 Moderate", 5, "Institutional flow or industrial data sentiment."
    return "⚪ Low", 2, "General market news with minor index impact."

# 3. DYNAMIC DATA FETCHING (Past 7 Days Aggregator)
def fetch_dynamic_news():
    sources = [
        "https://moneycontrol.com",
        "https://www.livemint.com/rss/markets",
        "https://indiatimes.com"
    ]
    all_news = []
    week_ago = datetime.now(IST) - timedelta(days=7)
    
    for url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                pub_time = datetime(*entry.published_parsed[:6]).replace(tzinfo=pytz.utc).astimezone(IST)
                if pub_time > week_ago:
                    impact, weight, logic = analyze_headline(entry.title)
                    all_news.append({
                        "Topic": entry.title,
                        "Exact Timing": pub_time.strftime("%d %b, %I:%M %p"),
                        "Impact Level": impact,
                        "Weight (1-10)": weight,
                        "Logic Behind Impact": logic,
                        "Sort_Key": weight # For Sorting
                    })
        except: continue
    
    df = pd.DataFrame(all_news).drop_duplicates(subset=['Topic'])
    return df.sort_values(by='Sort_Key', ascending=False).drop(columns=['Sort_Key'])

# 4. UI RENDER
st.title("🏛️ Nifty 50: Dynamic Strategic Monitor")

# Net Sentiment Calculation
df_all = fetch_dynamic_news()
today_score = df_all[df_all['Exact Timing'].str.contains(datetime.now(IST).strftime("%d %b"))]['Weight (1-10)'].sum()
gauge_color = "red" if today_score > 30 else "orange" if today_score > 15 else "green"
st.subheader(f"Current Market Intensity: :{gauge_color}[{today_score} / 50]")
st.progress(min(today_score / 50, 1.0))

st.info(f"📍 Bengaluru Hub | Live Sync Active (60s Refresh)")

# --- TABLE 1: ACTIVE EVENTS (DYNAMICALLY SCRAPED) ---
st.header("🔴 Active & Recent Events (Past 7 Days)")
def style_impact(val):
    color = 'red' if 'Critical' in str(val) else 'orange' if 'High' in str(val) else 'gold' if 'Moderate' in str(val) else 'black'
    return f'color: {color}; font-weight: bold;'

if not df_all.empty:
    st.table(df_all.head(15).style.map(style_impact, subset=['Impact Level']))
else:
    st.warning("No major triggers detected in live feeds. Checking backup data...")

# --- TABLE 2: FUTURE EVENTS (MANUAL OVERRIDE FOR SCHEDULED DATES) ---
st.markdown("---")
st.header("📅 One-Month Future Outlook (Scheduled Triggers)")
future_data = [
    ["Good Friday Holiday", "April 3, 2026", "No Impact", 0, "Markets Closed; No Trading today."],
    ["RBI MPC Meeting", "April 6-8, 2026", "🔴 Critical", 9, "First rate decision of FY27; focus on inflation."],
    ["TCS Q4 FY26 Results", "April 9, 2026", "🟠 High", 7, "IT earnings benchmark will dictate index direction."],
    ["US Fed FOMC Meeting", "April 28-29, 2026", "🔴 Critical", 9, "Global rate outlook and FII capital flow trigger."]
]
df_future = pd.DataFrame(future_data, columns=["Topic", "Exact Timing", "Impact Level", "Weight (1-10)", "Logic Behind Impact"])
st.table(df_future)

# --- SIDEBAR: REORGANIZED LAYOUT ---
st.sidebar.error("📍 **Bengaluru Weekend Alert:**")
st.sidebar.write("The **US Fed meeting** (end of April) is a **9/10 weight**. Key driver for FII flows.")
st.sidebar.markdown("---")

# Live Nifty Price
nifty_ticker = yf.Ticker("^NSEI")
nifty_hist = nifty_ticker.history(period="1d", interval="1m")
if not nifty_hist.empty:
    current_p = nifty_hist['Close'].iloc[-1]
    change = current_p - nifty_hist['Open'].iloc[0]
    st.sidebar.metric("Live Nifty 50", f"{current_p:,.2f}", f"{change:+.2f}")

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Weight & Sentiment Guide")
st.sidebar.write("**9-10/10:** 'Market Changers'. Expect 300+ point gaps.")
st.sidebar.write("**31-50 Total:** 'High Stress' zone.")
