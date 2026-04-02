import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh

# 1. SETUP & AUTO-REFRESH
st.set_page_config(page_title="Nifty 50 Dynamic Hub", layout="wide")
st_autorefresh(interval=60000, key="nifty_dynamic_v7")
IST = pytz.timezone('Asia/Kolkata')

# 2. STRATEGIC LOGIC ENGINE
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

# 3. DYNAMIC 7-DAY NEWS FETCHING (Using NewsAPI)
def fetch_7day_news():
    # Retrieve key from Streamlit Secrets
    api_key = st.secrets["news_api_key"]
    
    # Calculate date for 7 days ago
    seven_days_ago = (datetime.now(IST) - timedelta(days=7)).strftime('%Y-%m-%d')
    
    # Query for Nifty 50 / Indian Market news
    url = f'https://newsapi.org"Nifty 50" OR "Indian Stock Market"&from={seven_days_ago}&sortBy=publishedAt&apiKey={api_key}&language=en'
    
    try:
        response = requests.get(url).json()
        articles = response.get('articles', [])
        
        news_list = []
        for art in articles[:20]: # Get top 20 relevant items
            impact, weight, logic = analyze_headline(art['title'])
            # Convert UTC string to IST
            dt_utc = datetime.strptime(art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc)
            dt_ist = dt_utc.astimezone(IST)
            
            news_list.append([
                art['title'], 
                dt_ist.strftime("%d %b, %I:%M %p"), 
                impact, 
                weight, 
                logic
            ])
        return news_list
    except Exception as e:
        return [["API Error", "N/A", "⚪ Low", 0, f"Check API Key in Secrets: {str(e)}"]]

# 4. UI RENDER
st.title("🏛️ Nifty 50: Dynamic Strategic Monitor")

# Fetch data
ACTIVE_EVENTS_DATA = fetch_7day_news()

# Sentiment Score Calculation
today_str = datetime.now(IST).strftime("%d %b")
today_score = sum([row for row in ACTIVE_EVENTS_DATA if today_str in row])
gauge_color = "red" if today_score > 30 else "orange" if today_score > 15 else "green"
st.subheader(f"Current Market Intensity: :{gauge_color}[{today_score} / 50]")
st.progress(min(today_score / 50, 1.0))

st.info(f"📍 Bengaluru Hub | Monitoring Window: Past 7 Days (Dynamic API)")

# --- TABLE 1: ACTIVE EVENTS ---
def get_clean_table(data_list):
    df = pd.DataFrame(data_list, columns=["Topic", "Exact Timing", "Impact Level", "Weight (1-10)", "Logic Behind Impact"])
    rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2, "⚪ Low": 3, "No Impact": 4}
    df['Sort_Key'] = df['Impact Level'].apply(lambda x: next((v for k, v in rank.items() if k in x), 99))
    df = df.sort_values('Sort_Key').drop(columns=['Sort_Key'])
    def style_impact_text(val):
        color = 'red' if 'Critical' in str(val) else 'orange' if 'High' in str(val) else 'gold' if 'Moderate' in str(val) else 'black'
        return f'color: {color}; font-weight: bold;'
    return df.style.map(style_impact_text, subset=['Impact Level'])

st.table(get_clean_table(ACTIVE_EVENTS_DATA))

# --- SIDEBAR (Fixed Subtraction) ---
st.sidebar.error("📍 **Bengaluru Weekend Alert:**")
st.sidebar.write("The **US Fed meeting** is a **9/10 weight**. Key for FII flows into IT.")
st.sidebar.markdown("---")

st.sidebar.header("NSE: NIFTY 50")
nifty_hist = yf.Ticker("^NSEI").history(period="1d", interval="1m")
if not nifty_hist.empty:
    current_p = nifty_hist['Close'].iloc[-1]
    opening_p = nifty_hist['Open'].iloc 
    change = current_p - opening_p
    st.sidebar.metric("Live Index", f"{current_p:,.2f}", f"{change:+.2f}")
else:
    st.sidebar.warning("Market Closed (Good Friday)")

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Weight & Sentiment Guide")
st.sidebar.write("**9-10/10:** 'Market Changers'. Expect 300+ point gaps.")
st.sidebar.write("**31-50 Total:** 'High Stress' zone.")
