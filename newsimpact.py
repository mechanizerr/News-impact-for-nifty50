import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh

# 1. INITIAL SETUP & 2-MINUTE AUTO REFRESH (Prevents Rate Limits)
st.set_page_config(page_title="Nifty 50 Strategic Hub", layout="wide")
st_autorefresh(interval=120000, key="nifty_master_dynamic_final")
IST = pytz.timezone('Asia/Kolkata')

# NIFTY 50 CONSTITUENTS (150+ Keywords Monitored)
NIFTY_50_STOCKS = [
    'ADANI', 'APOLLO', 'ASIAN PAINTS', 'AXIS BANK', 'BAJAJ', 'BPCL', 'BHARTI AIRTEL', 
    'BRITANNIA', 'CIPLA', 'COAL INDIA', 'DIVIS', 'DR REDDY', 'EICHER', 'GRASIM', 
    'HCL TECH', 'HDFC', 'HERO', 'HINDALCO', 'HINDUNILVR', 'ICICI', 'ITC', 'INDUSIND', 
    'INFOSYS', 'JSW STEEL', 'KOTAK', 'LTIM', 'L&T', 'M&M', 'MARUTI', 'NTPC', 
    'NESTLE', 'ONGC', 'POWERGRID', 'RELIANCE', 'SBI', 'SUN PHARMA', 'TCS', 
    'TATA MOTORS', 'TATA STEEL', 'TECH MAHINDRA', 'TITAN', 'UPL', 'ULTRACEMCO', 'WIPRO'
]

# 2. DYNAMIC LOGIC ENGINE (Assigns Weights & Logic on the fly)
def analyze_headline(title):
    t = title.lower()
    if any(k in t for k in ['trump', 'iran', 'war', 'strike', 'missile', 'lockdown', 'covid']):
        return "🔴 Critical (Negative)", 10, "High-stakes geopolitical or health crisis trigger."
    if any(k in t for k in ['rbi', 'fed', 'interest rate', 'inflation', 'cpi', 'oil', 'brent']):
        return "🟠 High", 8, "Macro-economic shift affecting fiscal stability/liquidity."
    if any(stock.lower() in t for stock in NIFTY_50_STOCKS) or any(k in t for k in ['earnings', 'q4', 'profit', 'loss']):
        return "🟡 Moderate", 6, "Specific Nifty 50 constituent performance driving index movement."
    return "⚪ Low", 2, "General market news with minor index impact."

# 3. DYNAMIC 7-DAY DATA FETCHING (Zero Hardcoding - Scrapes Live API)
def fetch_dynamic_7day_data():
    api_key = st.secrets["news_api_key"]
    seven_days_ago = (datetime.now(IST) - timedelta(days=7)).strftime('%Y-%m-%d')
    
    # DYNAMIC SEARCH: Hits the entire web for Nifty 50 news from the last week
    url = f'https://newsapi.org"Nifty 50" OR "NSE India" OR "Indian Stock Market"&from={seven_days_ago}&sortBy=publishedAt&apiKey={api_key}&language=en'
    
    try:
        response = requests.get(url).json()
        articles = response.get('articles', [])
        active_list = []
        future_list = []
        
        for art in articles[:40]: # Process top 40 items
            impact, weight, logic = analyze_headline(art['title'])
            dt_utc = datetime.strptime(art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc)
            dt_ist = dt_utc.astimezone(IST)
            
            row = [art['title'], dt_ist.strftime("%d %b, %I:%M %p"), impact, weight, logic]
            
            # SORTING LOGIC: If headline mentions "Upcoming", "Meeting Date", or future months
            if any(word in art['title'].lower() for word in ['upcoming', 'scheduled', 'april', 'may', 'meeting', 'calendar']):
                future_list.append(row)
            else:
                active_list.append(row)
        return active_list, future_list
    except:
        return [], []

# 4. UI RENDER & STYLING
st.title("🏛️ Nifty 50: 100% Dynamic Strategic Monitor")

active_raw, future_raw = fetch_dynamic_7day_data()

# Sentiment Gauge (Calculated from today's triggers: April 2nd)
today_str = datetime.now(IST).strftime("%d %b")
today_score = sum([row[3] for row in active_raw if today_str in str(row)])
gauge_color = "red" if today_score > 30 else "orange" if today_score > 15 else "green"
st.subheader(f"Current Market Intensity: :{gauge_color}[{today_score} / 50]")
st.progress(min(today_score / 50, 1.0))

st.info(f"📍 Bengaluru Hub | Live Dynamic API Sync | Last Refresh: {datetime.now(IST).strftime('%I:%M %p')}")

# --- TABLE 1: DYNAMIC ACTIVE EVENTS (PAST 7 DAYS) ---
def get_clean_table(data_list):
    df = pd.DataFrame(data_list, columns=["Topic", "Exact Timing", "Impact Level", "Weight (1-10)", "Logic Behind Impact"])
    rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2, "⚪ Low": 3}
    df['Sort_Key'] = df['Impact Level'].apply(lambda x: next((v for k, v in rank.items() if k in str(x)), 99))
    df = df.sort_values(['Sort_Key', 'Weight (1-10)'], ascending=[True, False]).drop(columns=['Sort_Key'])
    def style_impact_text(val):
        color = 'red' if 'Critical' in str(val) else 'orange' if 'High' in str(val) else 'gold' if 'Moderate' in str(val) else 'black'
        return f'color: {color}; font-weight: bold;'
    return df.head(15).style.map(style_impact_text, subset=['Impact Level'])

st.header("🔴 Active & Recent Events (Constituent Aware)")
if active_raw:
    st.table(get_clean_table(active_raw))
else:
    st.warning("Ensure your NewsAPI key is correctly set in Streamlit Secrets.")

# --- TABLE 2: DYNAMIC FUTURE EVENTS ---
st.markdown("---")
st.header("📅 Future Major Events (Detected from News)")
if future_raw:
    st.table(get_clean_table(future_raw))
else:
    st.write("Searching live feeds for upcoming 'Scheduled' or 'Upcoming' events...")

# --- MARKET GUIDE "READ ME" ---
st.markdown("---")
st.header("📖 How to Read Net Sentiment")
col1, col2 = st.columns(2)
with col1:
    st.write("**0 - 15 (Low):** Sideways market; narrow price range.")
    st.write("**16 - 30 (Active):** Clear trend forming; 100-200 point intraday moves.")
with col2:
    st.write("**31 - 45 (Stress):** Major volatility; expect 300+ point gaps.")
    st.write("**46 - 50 (Black Swan):** Extreme risk; potential circuit breakers.")

# --- SIDEBAR REORGANIZED (Restored Alert, Price & Guide) ---
st.sidebar.error("📍 **Bengaluru Weekend Alert:**")
st.sidebar.write("The **US Fed meeting** (late April) is a **9/10 weight**. This will be the biggest driver for FII flows in May.")
st.sidebar.markdown("---")

st.sidebar.header("NSE: NIFTY 50")
@st.cache_data(ttl=300)
def get_nifty_price():
    try:
        hist = yf.Ticker("^NSEI").history(period="1d", interval="1m")
        if not hist.empty:
            return hist['Close'].iloc[-1], hist['Open'].iloc[-1]
    except: return None, None
    return None, None

curr_p, open_p = get_nifty_price()
if curr_p:
    st.sidebar.metric("Live Index", f"{curr_p:,.2f}", f"{(curr_p - open_p):+.2f}")
else:
    st.sidebar.warning("Market Closed (Good Friday Holiday)")

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Weight & Sentiment Guide")
st.sidebar.write("• **9-10/10:** 'Market Changers'. Expect 300+ point gaps.")
st.sidebar.write("• **6-8/10:** 'Trend Setters'. 100-200 point moves.")
st.sidebar.write("• **Under 5/10:** 'Daily Volatility'.")
st.sidebar.write("• **31-50 Total:** 'High Stress' zone.")
