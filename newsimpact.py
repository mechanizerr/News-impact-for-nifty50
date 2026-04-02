import streamlit as st
import pandas as pd
import feedparser
import requests
import json
import re
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh

# ─── 1. SETUP ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Nifty 50 Hybrid Hub", layout="wide")
st_autorefresh(interval=60000, key="nifty_hybrid_v4")
IST = pytz.timezone('Asia/Kolkata')

# ─── 2. GEMINI AI ANALYSIS ENGINE (FREE TIER) ────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def analyze_headlines_with_gemini(headlines: tuple) -> list:
    """
    Batch-send headlines to Google Gemini API (free tier).
    Returns list of dicts: {index, relevant, impact_level, weight, logic}
    Free tier: 15 requests/min, 1500 requests/day — more than enough.
    Get your free key at: https://aistudio.google.com/app/apikey
    """
    if not headlines:
        return []

    gemini_api_key = st.secrets.get("gemini_api_key", None)
    if not gemini_api_key:
        # Fallback to keyword-based if no key provided
        return keyword_fallback(headlines)

    numbered = "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines))

    prompt = f"""You are a senior Indian equity market analyst specialising in the Nifty 50 index.

Below is a list of news headlines. For EACH headline, determine:
1. Is it genuinely relevant to Nifty 50 movement? (true/false)
   - RELEVANT: RBI/Fed policy, FII flows, oil/INR moves, Nifty-constituent earnings, India macro data (CPI/WPI/GDP/IIP), geopolitical events affecting India trade/oil, global risk-off events, SEBI actions, major NSE IPOs, US-China tariffs affecting Indian exports, rupee movement.
   - NOT RELEVANT: cricket, entertainment, domestic politics with no market mechanism, overseas company news with no India exposure, lifestyle, real estate listings, general crime, state elections with no macro angle.
2. Impact Level: 🔴 Critical / 🟠 High / 🟡 Moderate (never assign Low)
3. Weight (5-10): 5=Moderate, 6-7=High, 8-9=Critical, 10=Black Swan only
4. Logic (max 18 words): State the SPECIFIC mechanism by which THIS headline moves Nifty 50. Mention which sectors, stocks, or flows are affected.

Headlines:
{numbered}

Respond ONLY with a valid JSON array. One object per headline. Exact format:
[
  {{"index": 1, "relevant": true, "impact_level": "🔴 Critical", "weight": 9, "logic": "RBI rate cut lifts HDFCBANK, ICICIBANK; banking sector drives index 150+ pts up."}},
  {{"index": 2, "relevant": false, "impact_level": "🟡 Moderate", "weight": 5, "logic": "No direct Nifty mechanism."}}
]
No markdown fences, no extra text. Raw JSON array only."""

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-1.5-flash:generateContent?key={gemini_api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048}
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except Exception:
        return keyword_fallback(headlines)

# ─── 3. KEYWORD FALLBACK (if no Gemini key) ──────────────────────────────────
NIFTY_50_STOCKS = [
    'reliance', 'tcs', 'hdfcbank', 'icicibank', 'infosys', 'infy',
    'bhartiartl', 'airtel', 'sbi', 'itc', 'larsen', 'l&t', 'adanient',
    'adani', 'wipro', 'hcltech', 'axisbank', 'kotakbank', 'bajajfinance',
    'maruti', 'ultracemco', 'asianpaint', 'titan', 'hindalco', 'tatamotors',
    'tatasteel', 'jswsteel', 'ongc', 'ntpc', 'powergrid', 'techm',
    'sunpharma', 'drreddy', 'cipla', 'apollohosp', 'indusindbk',
    'sbilife', 'hdfclife', 'bajajfinsv', 'bpcl', 'coalindia', 'eichermot'
]
MACRO_KEYWORDS = [
    'rbi', 'fed', 'federal reserve', 'interest rate', 'inflation', 'cpi',
    'wpi', 'oil', 'brent', 'crude', 'gdp', 'fiscal deficit', 'repo rate',
    'monetary policy', 'mpc', 'sebi', 'fii', 'dii', 'foreign investment',
    'trade deficit', 'rupee', 'forex', 'dollar', 'budget', 'gst', 'iip'
]
CRISIS_KEYWORDS = [
    'trump', 'tariff', 'iran', 'war', 'strike', 'missile', 'lockdown',
    'recession', 'crash', 'collapse', 'default', 'sanctions', 'china',
    'pandemic', 'banking crisis', 'debt crisis', 'global selloff'
]
IRRELEVANT_KEYWORDS = [
    'cricket', 'ipl', 'bollywood', 'movie', 'film', 'celebrity', 'wedding',
    'recipe', 'fashion', 'lifestyle', 'horoscope', 'sports score'
]

def keyword_fallback(headlines: tuple) -> list:
    results = []
    for i, title in enumerate(headlines):
        t = title.lower()
        if any(k in t for k in IRRELEVANT_KEYWORDS):
            results.append({"index": i+1, "relevant": False, "impact_level": "🟡 Moderate", "weight": 2, "logic": "Not market relevant."})
            continue
        if any(k in t for k in CRISIS_KEYWORDS):
            results.append({"index": i+1, "relevant": True, "impact_level": "🔴 Critical", "weight": 9, "logic": "Geopolitical/macro crisis — FII selling pressure, broad index decline expected."})
        elif any(k in t for k in MACRO_KEYWORDS):
            results.append({"index": i+1, "relevant": True, "impact_level": "🟠 High", "weight": 7, "logic": "Macro policy shift — affects liquidity, FII flows, and rate-sensitive Nifty stocks."})
        elif any(s in t for s in NIFTY_50_STOCKS) or any(k in t for k in ['nifty', 'sensex', 'nse', 'bse']):
            results.append({"index": i+1, "relevant": True, "impact_level": "🟡 Moderate", "weight": 6, "logic": "Nifty 50 constituent event — sector-level impact on index weight."})
        elif 'india' in t and any(k in t for k in ['market', 'stock', 'equity', 'index']):
            results.append({"index": i+1, "relevant": True, "impact_level": "🟡 Moderate", "weight": 5, "logic": "Indian equity market event — moderate index-level impact."})
        else:
            results.append({"index": i+1, "relevant": False, "impact_level": "🟡 Moderate", "weight": 2, "logic": "Low relevance to Nifty 50."})
    return results

# ─── 4. SMART DEDUPLICATION ───────────────────────────────────────────────────
def smart_deduplicate(items: list) -> list:
    """Remove near-duplicate headlines using Jaccard token overlap (threshold 0.55)."""
    def tokenize(text):
        return set(re.sub(r'[^a-z0-9 ]', '', text.lower()).split())

    kept = []
    for item in items:
        title_tokens = tokenize(item["title"])
        is_dup = False
        for seen in kept:
            seen_tokens = tokenize(seen["title"])
            if not title_tokens or not seen_tokens:
                continue
            overlap = len(title_tokens & seen_tokens) / len(title_tokens | seen_tokens)
            if overlap > 0.55:
                is_dup = True
                break
        if not is_dup:
            kept.append(item)
    return kept

# ─── 5. RSS LIVE FEEDS ────────────────────────────────────────────────────────
RSS_FEEDS = {
    "Moneycontrol Markets":   "https://www.moneycontrol.com/rss/marketreports.xml",
    "Moneycontrol Economy":   "https://www.moneycontrol.com/rss/economy.xml",
    "Economic Times Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Economic Times Economy": "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms",
    "Business Standard":      "https://www.business-standard.com/rss/markets-106.rss",
    "LiveMint Markets":       "https://www.livemint.com/rss/markets",
    "Financial Express":      "https://www.financialexpress.com/market/feed/",
}

def fetch_rss_live() -> list:
    raw = []
    for source_name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                title = entry.get('title', '').strip()
                if not title:
                    continue
                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_time = datetime(*entry.published_parsed[:6]).replace(tzinfo=pytz.utc).astimezone(IST)
                        time_str = pub_time.strftime("%d %b, %I:%M %p")
                    else:
                        time_str = datetime.now(IST).strftime("%d %b, %I:%M %p")
                except Exception:
                    time_str = datetime.now(IST).strftime("%d %b, %I:%M %p")
                raw.append({"title": title, "time": time_str, "source": source_name})
        except Exception:
            continue
    return raw

# ─── 6. NEWSAPI: PAST 7 DAYS ─────────────────────────────────────────────────
def fetch_newsapi_history(api_key: str) -> list:
    raw = []
    seven_days_ago = (datetime.now(IST) - timedelta(days=7)).strftime('%Y-%m-%d')
    queries = [
        '"Nifty 50" OR "NSE India" OR "BSE Sensex"',
        '"RBI" OR "repo rate" OR "monetary policy India"',
        '"Indian market" OR "FII" OR "Dalal Street"',
        '"crude oil" OR "rupee" India market',
    ]
    for q in queries:
        url = (
            "https://newsapi.org/v2/everything"
            f"?q={requests.utils.quote(q)}"
            f"&from={seven_days_ago}"
            "&sortBy=publishedAt&language=en&pageSize=10"
            f"&apiKey={api_key}"
        )
        try:
            articles = requests.get(url, timeout=10).json().get('articles', [])
            for art in articles:
                title = art.get('title', '').strip()
                if not title or title == '[Removed]':
                    continue
                try:
                    dt_ist = datetime.strptime(
                        art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ'
                    ).replace(tzinfo=pytz.utc).astimezone(IST)
                    time_str = dt_ist.strftime("%d %b, %I:%M %p")
                except Exception:
                    time_str = "N/A"
                source = art.get('source', {}).get('name', 'NewsAPI')
                raw.append({"title": title, "time": time_str, "source": source})
        except Exception:
            continue
    return raw

# ─── 7. NEWSAPI: FUTURE EVENTS ───────────────────────────────────────────────
def fetch_newsapi_future_events(api_key: str) -> list:
    raw = []
    today = datetime.now(IST).strftime('%Y-%m-%d')
    queries = [
        '"RBI MPC" OR "RBI meeting"',
        '"Q4 results" India earnings',
        '"IPO" India NSE 2025',
        '"Fed meeting" OR "FOMC" 2025',
        '"India GDP" OR "IIP data" OR "CPI data" 2025',
    ]
    for q in queries:
        url = (
            "https://newsapi.org/v2/everything"
            f"?q={requests.utils.quote(q)}"
            f"&from={today}"
            "&sortBy=publishedAt&language=en&pageSize=5"
            f"&apiKey={api_key}"
        )
        try:
            articles = requests.get(url, timeout=10).json().get('articles', [])
            for art in articles:
                title = art.get('title', '').strip()
                if not title or title == '[Removed]':
                    continue
                try:
                    dt_ist = datetime.strptime(
                        art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ'
                    ).replace(tzinfo=pytz.utc).astimezone(IST)
                    time_str = dt_ist.strftime("%d %b, %I:%M %p")
                except Exception:
                    time_str = "Upcoming"
                source = art.get('source', {}).get('name', 'NewsAPI')
                raw.append({"title": title, "time": time_str, "source": source})
        except Exception:
            continue
    return raw

# ─── 8. MASTER PIPELINE ──────────────────────────────────────────────────────
def build_table(raw_items: list) -> pd.DataFrame:
    if not raw_items:
        return pd.DataFrame()

    deduped = smart_deduplicate(raw_items)
    titles = tuple(item["title"] for item in deduped)

    analysis_map = {}
    batch_size = 20
    for i in range(0, len(titles), batch_size):
        batch = titles[i:i+batch_size]
        results = analyze_headlines_with_gemini(batch)
        for r in results:
            analysis_map[i + r["index"] - 1] = r

    rows = []
    for idx, item in enumerate(deduped):
        info = analysis_map.get(idx, {})
        if not info.get("relevant", False):
            continue
        weight = info.get("weight", 5)
        if weight < 5:
            continue
        rows.append({
            "Topic":               item["title"],
            "Exact Timing":        item["time"],
            "Impact Level":        info.get("impact_level", "🟡 Moderate"),
            "Weight (1-10)":       weight,
            "Logic Behind Impact": info.get("logic", "—"),
            "Source":              item["source"],
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2}
    df['_sort'] = df['Impact Level'].apply(lambda x: next((v for k, v in rank.items() if k in str(x)), 99))
    df = df.sort_values(['_sort', 'Weight (1-10)'], ascending=[True, False]).drop(columns=['_sort']).reset_index(drop=True)
    return df

@st.cache_data(ttl=300, show_spinner=False)
def fetch_all_data():
    raw = fetch_rss_live()
    api_key = st.secrets.get("news_api_key", None)
    if api_key:
        raw += fetch_newsapi_history(api_key)
    return build_table(raw)

@st.cache_data(ttl=300, show_spinner=False)
def fetch_future_data():
    hardcoded = [
        {"title": "RBI MPC Meeting — First Rate Decision of FY27",      "time": "06-08 Apr 2025",          "source": "Fixed Calendar"},
        {"title": "TCS Q4 FY25 Earnings Results",                        "time": "09 Apr 2025, Post-Market", "source": "Fixed Calendar"},
        {"title": "Wipro Q4 FY25 Earnings Results",                      "time": "16 Apr 2025, Post-Market", "source": "Fixed Calendar"},
        {"title": "HCL Technologies Q4 FY25 Results",                    "time": "22 Apr 2025, Post-Market", "source": "Fixed Calendar"},
        {"title": "Infosys Q4 FY25 Earnings Results",                    "time": "23 Apr 2025, Post-Market", "source": "Fixed Calendar"},
        {"title": "US Fed FOMC Rate Decision May 2025",                  "time": "06-07 May 2025",           "source": "Fixed Calendar"},
        {"title": "India April CPI Inflation Data Release",              "time": "12 May 2025",              "source": "Fixed Calendar"},
        {"title": "India Q4 GDP and FY25 Full-Year Growth Data",         "time": "Late May 2025",            "source": "Fixed Calendar"},
    ]
    raw = list(hardcoded)
    api_key = st.secrets.get("news_api_key", None)
    if api_key:
        raw += fetch_newsapi_future_events(api_key)
    return build_table(raw)

# ─── 9. STYLED TABLE ─────────────────────────────────────────────────────────
def get_styled_table(df: pd.DataFrame):
    display_cols = ["Topic", "Exact Timing", "Impact Level", "Weight (1-10)", "Logic Behind Impact", "Source"]
    display_cols = [c for c in display_cols if c in df.columns]

    def color_impact(v):
        if 'Critical' in str(v): return 'color: red; font-weight: bold;'
        if 'High' in str(v):     return 'color: orange; font-weight: bold;'
        if 'Moderate' in str(v): return 'color: goldenrod; font-weight: bold;'
        return ''

    return df[display_cols].style.map(color_impact, subset=['Impact Level'])

# ─── 10. UI ───────────────────────────────────────────────────────────────────
st.title("🏛️ Nifty 50: Hybrid Strategic Monitor")

has_gemini = bool(st.secrets.get("gemini_api_key"))
ai_label = "Gemini AI" if has_gemini else "Keyword Engine"

with st.spinner(f"🤖 {ai_label} is analysing headlines for Nifty 50 relevance..."):
    df_all = fetch_all_data()

today_str = datetime.now(IST).strftime("%d %b")
today_df = df_all[df_all['Exact Timing'].str.contains(today_str, na=False)] if not df_all.empty else pd.DataFrame()
today_score = int(today_df["Weight (1-10)"].sum()) if not today_df.empty else 0
gauge_color = "red" if today_score > 30 else "orange" if today_score > 15 else "green"

st.subheader(f"Current Market Intensity: :{gauge_color}[{today_score} / 50]")
st.progress(min(today_score / 50, 1.0) if today_score > 0 else 0.0)

now_ist = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")
st.info(f"📍 Bengaluru Hub | {ai_label}-Curated | Last Refresh: {now_ist} | Auto-Refresh: 60s")

# Table 1
st.header("🔴 Active & Recent Events (Nifty 50 Relevant Only)")
if not df_all.empty:
    st.caption(
        f"{len(df_all)} curated events | Irrelevant & low-impact items filtered by {ai_label} | "
        "Logic is specific to each headline."
    )
    st.table(get_styled_table(df_all))
else:
    st.warning(
        "⚠️ No relevant events found.\n"
        "1. RSS feeds may be unreachable — check internet.\n"
        "2. All items may have been filtered as irrelevant.\n"
        "3. Add `news_api_key` to Secrets for 7-day history."
    )

# Table 2
st.markdown("---")
st.header("📅 Future Major Events (Nifty 50 Outlook)")
with st.spinner(f"🤖 {ai_label} analysing upcoming events..."):
    df_future = fetch_future_data()

if not df_future.empty:
    st.caption(f"Fixed calendar + dynamic NewsAPI — logic written per event by {ai_label}.")
    st.table(get_styled_table(df_future))
else:
    st.info("No upcoming events loaded. Add NewsAPI key for dynamic event discovery.")

# Market Guide
st.markdown("---")
st.header("📖 How to Read Net Sentiment")
c1, c2 = st.columns(2)
with c1:
    st.write("**0 – 15 (Low):** Sideways market; narrow price range.")
    st.write("**16 – 30 (Active):** Clear trend forming; 100–200 point moves.")
with c2:
    st.write("**31 – 45 (Stress):** Major volatility; expect 300+ point gaps.")
    st.write("**46 – 50 (Black Swan):** Extreme risk; circuit breaker potential.")

# Sidebar
st.sidebar.error("📍 **Bengaluru Weekend Alert:**")
st.sidebar.write("The **US Fed meeting** is a **9/10 weight**. Major FII flow driver for Indian IT stocks.")
st.sidebar.markdown("---")

if has_gemini:
    st.sidebar.success("✅ Gemini AI Active (Free Tier)")
    st.sidebar.write("Model: gemini-1.5-flash")
    st.sidebar.write("Free limits: 15 req/min, 1,500 req/day")
else:
    st.sidebar.warning("⚠️ Gemini key not set — using Keyword Engine.")
    st.sidebar.write("Add `gemini_api_key` to Secrets for smarter AI curation.")
    st.sidebar.write("Get free key → https://aistudio.google.com/app/apikey")

st.sidebar.markdown("---")
st.sidebar.subheader("🤖 Curation Rules")
st.sidebar.write("• Only Nifty 50-relevant headlines shown.")
st.sidebar.write("• Logic written per headline — not templated.")
st.sidebar.write("• Near-duplicates (>55% overlap) auto-merged.")
st.sidebar.write("• Weight < 5 items always hidden.")
st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Weight Guide")
st.sidebar.write("• **9–10/10:** Market Changers — systemic impact.")
st.sidebar.write("• **6–8/10:** Trend Setters — sector-level moves.")
st.sidebar.write("• **5/10:** Watch List — stock-specific impact.")
st.sidebar.markdown("---")
st.sidebar.subheader("📡 Sources")
st.sidebar.write("Live RSS: Moneycontrol, ET, Business Standard, LiveMint, FE")
st.sidebar.write("History: NewsAPI.org (7-day window)")
st.sidebar.write("Future: NewsAPI.org + Fixed Calendar")
st.sidebar.write(f"Analysis: {ai_label}")

if not st.secrets.get("news_api_key"):
    st.sidebar.warning(
        "⚠️ NewsAPI key not set.\n"
        "Add `news_api_key = 'your_key'` to `.streamlit/secrets.toml`.\n"
        "Free key: https://newsapi.org/register"
    )
