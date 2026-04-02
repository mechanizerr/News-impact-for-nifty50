import streamlit as st
import pandas as pd
import feedparser
import requests
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh

# ─── 1. SETUP ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Nifty 50 Hybrid Hub", layout="wide")
st_autorefresh(interval=60000, key="nifty_hybrid_master_final")
IST = pytz.timezone('Asia/Kolkata')

# ─── 2. DYNAMIC LOGIC ENGINE ─────────────────────────────────────────────────
NIFTY_50_STOCKS = [
    'reliance', 'tcs', 'hdfcbank', 'icicibank', 'infosys', 'infy',
    'bhartiartl', 'airtel', 'sbi', 'itc', 'larsen', 'l&t', 'adanient',
    'adani', 'wipro', 'hcltech', 'axisbank', 'kotakbank', 'bajajfinance',
    'maruti', 'ultracemco', 'asianpaint', 'nestleind', 'titan', 'hindalco',
    'tatamotors', 'tataconsum', 'tatasteel', 'jswsteel', 'ongc', 'ntpc',
    'powergrid', 'techm', 'sunpharma', 'drreddy', 'cipla', 'apollohosp',
    'indusindbk', 'sbilife', 'hdfclife', 'bajajfinsv', 'bpcl', 'coalindia',
    'eichermot', 'upl', 'grasim', 'britannia', 'shreecem'
]

MACRO_KEYWORDS = [
    'rbi', 'fed', 'federal reserve', 'interest rate', 'inflation', 'cpi',
    'wpi', 'oil', 'brent', 'crude', 'gdp', 'fiscal deficit', 'repo rate',
    'reverse repo', 'monetary policy', 'mpc', 'sebi', 'fii', 'dii',
    'foreign investment', 'current account', 'trade deficit', 'rupee',
    'forex', 'dollar', 'imf', 'world bank', 'budget', 'tax', 'gst'
]

CRISIS_KEYWORDS = [
    'trump', 'iran', 'war', 'strike', 'missile', 'lockdown', 'covid',
    'recession', 'crash', 'collapse', 'default', 'sanctions', 'tariff',
    'china', 'pakistan', 'terror', 'attack', 'earthquake', 'flood',
    'pandemic', 'global crisis', 'banking crisis', 'debt crisis'
]

FUTURE_KEYWORDS = [
    'earnings', 'results', 'q4', 'q3', 'quarterly', 'meeting', 'policy',
    'announcement', 'upcoming', 'scheduled', 'expected', 'forecast',
    'outlook', 'guidance', 'ipo', 'merger', 'acquisition', 'deal'
]

def analyze_headline(title):
    t = title.lower()
    if any(k in t for k in CRISIS_KEYWORDS):
        return "🔴 Critical (Negative)", 10, "High-stakes geopolitical/health crisis trigger."
    if any(k in t for k in MACRO_KEYWORDS):
        return "🟠 High", 8, "Macro-economic policy shift affecting liquidity."
    if any(s in t for s in NIFTY_50_STOCKS) or 'nifty' in t or 'sensex' in t or 'nse' in t:
        return "🟡 Moderate", 6, "Specific Nifty 50 constituent event impacting sector."
    if 'india' in t and any(k in t for k in ['market', 'stock', 'equity', 'index', 'bse']):
        return "🟡 Moderate", 5, "Indian equity market event."
    return "⚪ Low", 2, "General market news."

# ─── 3. RSS LIVE FEEDS ────────────────────────────────────────────────────────
RSS_FEEDS = {
    "Moneycontrol Markets": "https://www.moneycontrol.com/rss/marketreports.xml",
    "Moneycontrol Economy": "https://www.moneycontrol.com/rss/economy.xml",
    "Economic Times Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Economic Times Economy": "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms",
    "Business Standard": "https://www.business-standard.com/rss/markets-106.rss",
    "LiveMint Markets": "https://www.livemint.com/rss/markets",
    "Financial Express": "https://www.financialexpress.com/market/feed/",
}

def fetch_rss_live():
    """Fetch live news from verified Indian financial RSS feeds."""
    live_news = []
    for source_name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            entries = feed.entries[:6]  # top 6 per source
            for entry in entries:
                title = entry.get('title', '').strip()
                if not title:
                    continue
                impact, weight, logic = analyze_headline(title)

                # Parse publish time
                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_time = datetime(*entry.published_parsed[:6]).replace(tzinfo=pytz.utc).astimezone(IST)
                        time_str = pub_time.strftime("%d %b, %I:%M %p")
                    else:
                        time_str = datetime.now(IST).strftime("%d %b, %I:%M %p")
                except Exception:
                    time_str = datetime.now(IST).strftime("%d %b, %I:%M %p")

                live_news.append([title, time_str, impact, weight, logic, source_name])
        except Exception:
            continue
    return live_news

# ─── 4. NEWSAPI: PAST 7 DAYS + FUTURE EVENTS ─────────────────────────────────
def fetch_newsapi_history(api_key):
    """Fetch past 7 days of Nifty 50 relevant news via NewsAPI."""
    history_news = []
    seven_days_ago = (datetime.now(IST) - timedelta(days=7)).strftime('%Y-%m-%d')
    queries = [
        '"Nifty 50" OR "NSE India" OR "BSE Sensex"',
        '"RBI" OR "repo rate" OR "monetary policy India"',
        '"Indian market" OR "FII" OR "Dalal Street"',
    ]
    for q in queries:
        url = (
            f"https://newsapi.org/v2/everything"
            f"?q={requests.utils.quote(q)}"
            f"&from={seven_days_ago}"
            f"&sortBy=publishedAt"
            f"&language=en"
            f"&pageSize=10"
            f"&apiKey={api_key}"
        )
        try:
            resp = requests.get(url, timeout=10)
            articles = resp.json().get('articles', [])
            for art in articles:
                title = art.get('title', '').strip()
                if not title or title == '[Removed]':
                    continue
                impact, weight, logic = analyze_headline(title)
                try:
                    dt_ist = datetime.strptime(
                        art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ'
                    ).replace(tzinfo=pytz.utc).astimezone(IST)
                    time_str = dt_ist.strftime("%d %b, %I:%M %p")
                except Exception:
                    time_str = "N/A"
                source = art.get('source', {}).get('name', 'NewsAPI')
                history_news.append([title, time_str, impact, weight, logic, source])
        except Exception:
            continue
    return history_news

def fetch_newsapi_future_events(api_key):
    """Fetch upcoming scheduled events that impact Nifty 50."""
    future_news = []
    queries = [
        '"RBI MPC" OR "RBI meeting" 2025',
        '"Q4 results" India earnings 2025',
        '"IPO" India NSE 2025',
        '"budget" OR "policy announcement" India 2025',
        '"Fed meeting" OR "FOMC" 2025',
    ]
    today = datetime.now(IST).strftime('%Y-%m-%d')
    for q in queries:
        url = (
            f"https://newsapi.org/v2/everything"
            f"?q={requests.utils.quote(q)}"
            f"&from={today}"
            f"&sortBy=publishedAt"
            f"&language=en"
            f"&pageSize=5"
            f"&apiKey={api_key}"
        )
        try:
            resp = requests.get(url, timeout=10)
            articles = resp.json().get('articles', [])
            for art in articles:
                title = art.get('title', '').strip()
                if not title or title == '[Removed]':
                    continue
                impact, weight, logic = analyze_headline(title)
                try:
                    dt_ist = datetime.strptime(
                        art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ'
                    ).replace(tzinfo=pytz.utc).astimezone(IST)
                    time_str = dt_ist.strftime("%d %b, %I:%M %p")
                except Exception:
                    time_str = "Upcoming"
                source = art.get('source', {}).get('name', 'NewsAPI')
                future_news.append([title, time_str, impact, weight, logic, source])
        except Exception:
            continue
    return future_news

# ─── 5. MASTER FETCH ──────────────────────────────────────────────────────────
def fetch_all_data():
    all_news = fetch_rss_live()

    api_key = st.secrets.get("news_api_key", None)
    if api_key:
        all_news += fetch_newsapi_history(api_key)

    cols = ["Topic", "Exact Timing", "Impact Level", "Weight (1-10)", "Logic Behind Impact", "Source"]
    df = pd.DataFrame(all_news, columns=cols)
    df = df.drop_duplicates(subset=['Topic'])
    # Filter: only keep Moderate and above — exclude Low (⚪) impact items
    df = df[df["Weight (1-10)"] >= 5].copy()
    return df

def fetch_future_data():
    api_key = st.secrets.get("news_api_key", None)
    future_rows = []

    # Always show hardcoded known upcoming events as baseline
    hardcoded = [
        ["RBI MPC Meeting", "06-08 Apr 2025, 10:00 AM IST", "🔴 Critical", 9,
         "First rate review of FY27; focus on West Asia oil inflation impact on CPI.", "Fixed Calendar"],
        ["TCS Q4 FY25 Results", "09 Apr 2025, Post-Market", "🟠 High", 7,
         "Kicks off IT earnings season; sets tone for index direction.", "Fixed Calendar"],
        ["Infosys Q4 FY25 Results", "23 Apr 2025, Post-Market", "🔴 Critical", 8,
         "Major Nifty heavyweight; dictates tech sector sentiment.", "Fixed Calendar"],
        ["US Fed FOMC Meeting", "06-07 May 2025", "🔴 Critical", 9,
         "Rate decision drives FII flows into Indian equity markets.", "Fixed Calendar"],
        ["India Q4 GDP Data", "Late May 2025", "🟠 High", 7,
         "FY25 full-year GDP print; critical for market valuation re-rating.", "Fixed Calendar"],
    ]
    future_rows.extend(hardcoded)

    # Supplement with dynamic NewsAPI future events
    if api_key:
        dynamic = fetch_newsapi_future_events(api_key)
        future_rows.extend(dynamic)

    cols = ["Topic", "Exact Timing", "Impact Level", "Weight (1-10)", "Logic Behind Impact", "Source"]
    df = pd.DataFrame(future_rows, columns=cols)
    df = df.drop_duplicates(subset=['Topic'])
    # Exclude Low impact items
    df = df[df["Weight (1-10)"] >= 5].copy()
    return df

# ─── 6. UI RENDER ─────────────────────────────────────────────────────────────
st.title("🏛️ Nifty 50: Hybrid Strategic Monitor")

df_all = fetch_all_data()

# ── Sentiment Gauge ──
today_str = datetime.now(IST).strftime("%d %b")
today_df = df_all[df_all['Exact Timing'].str.contains(today_str, na=False)]
today_score = int(today_df["Weight (1-10)"].sum())
gauge_color = "red" if today_score > 30 else "orange" if today_score > 15 else "green"

st.subheader(f"Current Market Intensity: :{gauge_color}[{today_score} / 50]")
st.progress(min(today_score / 50, 1.0) if today_score > 0 else 0.0)

now_ist = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")
st.info(f"📍 Bengaluru Hub | Hybrid Sync Active | Last Refresh: {now_ist} | Auto-Refresh: 60s")

# ── Helper: Styled Table ──
def get_styled_table(df):
    display_cols = ["Topic", "Exact Timing", "Impact Level", "Weight (1-10)", "Logic Behind Impact", "Source"]
    # Keep only columns that exist
    display_cols = [c for c in display_cols if c in df.columns]
    rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2, "⚪ Low": 3}
    df = df.copy()
    df['_sort'] = df['Impact Level'].apply(lambda x: next((v for k, v in rank.items() if k in str(x)), 99))
    df = df.sort_values('_sort').drop(columns=['_sort'])

    def color_impact(v):
        if 'Critical' in str(v):
            return 'color: red; font-weight: bold;'
        elif 'High' in str(v):
            return 'color: orange; font-weight: bold;'
        elif 'Moderate' in str(v):
            return 'color: goldenrod; font-weight: bold;'
        return 'color: gray;'

    return df[display_cols].style.map(color_impact, subset=['Impact Level'])

# ── TABLE 1: ACTIVE & RECENT EVENTS ──
st.header("🔴 Active & Recent Events (Live RSS + 7-Day History)")
if not df_all.empty:
    st.caption(f"Total events loaded: {len(df_all)} | Sources: RSS feeds + NewsAPI (7 days)")
    st.table(get_styled_table(df_all))
else:
    st.warning(
        "⚠️ No live data fetched. Possible reasons:\n"
        "1. RSS feeds unreachable (check internet connection).\n"
        "2. NewsAPI key missing — add `news_api_key` to Streamlit Secrets.\n"
        "   Get a free key at: https://newsapi.org/register"
    )

# ── TABLE 2: FUTURE EVENTS ──
st.markdown("---")
st.header("📅 Future Major Events (Dynamic + Fixed Calendar)")

df_future = fetch_future_data()
if not df_future.empty:
    st.caption(
        "Hardcoded known events + live NewsAPI search for upcoming Nifty-impacting announcements."
    )
    st.table(get_styled_table(df_future))
else:
    st.info("No upcoming events found. Add a NewsAPI key for dynamic event discovery.")

# ── MARKET GUIDE ──
st.markdown("---")
st.header("📖 How to Read Net Sentiment")
c1, c2 = st.columns(2)
with c1:
    st.write("**0 – 15 (Low):** Sideways market; narrow price range.")
    st.write("**16 – 30 (Active):** Clear trend forming; 100–200 point moves.")
with c2:
    st.write("**31 – 45 (Stress):** Major volatility; expect 300+ point gaps.")
    st.write("**46 – 50 (Black Swan):** Extreme risk; circuit breaker potential.")

# ── SIDEBAR ──
st.sidebar.error("📍 **Bengaluru Weekend Alert:**")
st.sidebar.write(
    "The **US Fed meeting** is a **9/10 weight**. "
    "Major driver for FII flows into Indian IT stocks."
)

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Weight & Sentiment Guide")
st.sidebar.write("• **9–10/10:** 'Market Changers' — systemic impact.")
st.sidebar.write("• **6–8/10:** 'Trend Setters' — sector-level impact.")
st.sidebar.write("• **3–5/10:** 'Watch List' — stock-specific moves.")
st.sidebar.write("• **< 5/10:** Hidden (Low impact — filtered out).")

st.sidebar.markdown("---")
st.sidebar.subheader("📡 Data Sources")
st.sidebar.write("**Live (RSS):**")
for name in RSS_FEEDS.keys():
    st.sidebar.write(f"  • {name}")
st.sidebar.write("**Historical:** NewsAPI.org (7-day window)")
st.sidebar.write("**Future Events:** NewsAPI.org + Fixed Calendar")

if not st.secrets.get("news_api_key"):
    st.sidebar.warning(
        "⚠️ NewsAPI key not found.\n"
        "Add `news_api_key = 'your_key'` to `.streamlit/secrets.toml` "
        "for 7-day history and future event discovery.\n"
        "Free tier: https://newsapi.org/register"
    )
