import streamlit as st
import pandas as pd
import feedparser
import requests
import json
import re
import time
from datetime import datetime, timedelta
from collections import Counter
import pytz
from streamlit_autorefresh import st_autorefresh

# ─── 1. SETUP ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Nifty 50 Hybrid Hub", layout="wide")
st_autorefresh(interval=60000, key="nifty_hybrid_v5")
IST = pytz.timezone('Asia/Kolkata')

# ─── 2. GEMINI AI — SINGLE ENGINE FOR EVERYTHING ─────────────────────────────
# All filtering, topic synthesis, sentiment, logic — done by Gemini only.
# No hardcoded keywords, no hardcoded stocks, no hardcoded topics.

@st.cache_data(ttl=300, show_spinner=False)
def gemini_analyze(headlines: tuple, gemini_key: str) -> list:
    """
    Send headlines to Gemini. Returns list of analysis dicts.
    Falls back to returning headlines as-is (unfiltered, generic) only if API fails.
    """
    if not headlines or not gemini_key:
        return []

    numbered = "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines))
    today = datetime.now(IST).strftime("%d %b %Y")

    prompt = f"""You are a senior Indian equity market strategist covering the Nifty 50 index. Today is {today}.

I will give you a list of raw news headlines. Your job is to act as an intelligent filter and analyst.

For EACH headline, return ALL of these fields:

1. relevant (true/false)
   TRUE only if this headline has a DIRECT, SPECIFIC mechanism to move the Nifty 50 index.
   Ask yourself: "Will this cause FIIs to buy/sell, change RBI rate expectations, move oil/rupee, hit constituent earnings, or trigger a broad market gap?"
   TRUE examples: RBI policy, Fed decisions, crude oil moves, India macro data (CPI/GDP/IIP/WPI), Nifty constituent earnings, FII flow data, US market crashes, tariff wars hitting India, geopolitical events affecting oil or exports, SEBI actions, major NSE IPOs.
   FALSE examples: cricket, IPL, Bollywood, celebrity news, crime, food, travel, real estate listings, state-level politics with no macro link, foreign company news with zero India exposure.

2. topic — A crisp 2-5 word Bloomberg terminal-style label for this market event.
   DO NOT use the raw headline. Synthesize a clean label.
   Examples: "RBI Repo Rate Cut", "Crude Oil Price Spike", "US Tariff Escalation", "FII Selling Surge", "Trump Iran Strike Threat", "Dow Jones Crash", "IT Sector Earnings Beat", "Rupee Weakness", "Gold Safe-Haven Rally", "SEBI Derivative Curbs", "India GDP Miss"

3. sentiment — Effect on Nifty 50: "Positive" / "Negative" / "Mixed"

4. impact_level — "🔴 Critical" / "🟠 High" / "🟡 Moderate"
   Critical: index-moving event, 200+ point expected swing
   High: sector-level impact, 100-200 point swing
   Moderate: stock-specific or mild macro nudge

5. weight — integer 5 to 10
   10 = Black Swan (rare), 9 = Critical, 7-8 = High, 5-6 = Moderate

6. logic — 2-3 sentences. Explain the SPECIFIC mechanism by which THIS news moves Nifty 50.
   - Name the exact sectors and Nifty 50 stocks affected.
   - If the headline contains specific numbers (%, price, points), use them.
   - Each logic must be UNIQUE — never copy-paste the same text for two headlines.
   - Be precise: "BPCL and ONGC gain on higher crude, but IndiGo faces fuel cost pressure" is good. "FII selling pressure expected" alone is bad.

Headlines:
{numbered}

Respond ONLY with a raw JSON array. No markdown, no explanation, no preamble:
[
  {{"index": 1, "relevant": true, "topic": "Trump Iran Strike Threat", "sentiment": "Negative", "impact_level": "🔴 Critical", "weight": 9, "logic": "Trump's overnight threat to strike Iran in 2-3 weeks triggered a 426-pt gap-down open. Brent crude surged 7% on supply disruption fears. BPCL, ONGC rally but IndiGo, SpiceJet fall on jet fuel cost spike."}},
  {{"index": 2, "relevant": false, "topic": "N/A", "sentiment": "Mixed", "impact_level": "🟡 Moderate", "weight": 3, "logic": "Not relevant to Nifty 50."}}
]"""

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={gemini_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096}
    }

    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=40)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            if resp.status_code != 200:
                return []
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            raw = re.sub(r"```json|```", "", raw).strip()
            parsed = json.loads(raw)
            # Reject if Gemini returned duplicate logic (templated fallback)
            logics = [item.get("logic", "") for item in parsed if item.get("relevant")]
            if logics and Counter(logics).most_common(1)[0][1] > len(logics) * 0.4:
                return []
            return parsed
        except Exception:
            continue
    return []


@st.cache_data(ttl=300, show_spinner=False)
def gemini_future_events(gemini_key: str) -> list:
    """
    Ask Gemini to identify upcoming Nifty 50-impacting events for the next 30 days,
    sourced purely from its knowledge of the financial calendar.
    """
    if not gemini_key:
        return []

    today = datetime.now(IST).strftime("%d %b %Y")
    prompt = f"""You are a senior Indian equity market strategist. Today is {today}.

List the TOP 8-10 upcoming events in the next 30 days that will most significantly impact the Nifty 50 index.
These must be REAL, SCHEDULED events from the financial calendar — earnings dates, central bank meetings, macro data releases, key policy announcements.

For each event return:
- topic: 2-5 word Bloomberg-style label
- timing: specific date or date range (e.g. "10 Apr 2026" or "06-08 Apr 2026")
- sentiment: expected impact "Positive" / "Negative" / "Mixed"
- impact_level: "🔴 Critical" / "🟠 High" / "🟡 Moderate"
- weight: 5-10
- logic: 2-3 sentences explaining the specific Nifty 50 mechanism — which stocks/sectors, what flows, what magnitude of move expected.

Return ONLY a raw JSON array, no markdown:
[
  {{"topic": "RBI MPC Rate Decision", "timing": "07-09 Apr 2026", "sentiment": "Mixed", "impact_level": "🔴 Critical", "weight": 9, "logic": "RBI's first meeting of FY27 will set repo rate. A cut would rally HDFCBANK, ICICIBANK 3-5%. A hold keeps markets flat. All eyes on RBI governor's tone on inflation."}}
]"""

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={gemini_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048}
    }

    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=40)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            if resp.status_code != 200:
                return []
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception:
            continue
    return []


# ─── 3. RSS LIVE FEEDS ────────────────────────────────────────────────────────
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


# ─── 4. NEWSAPI: PAST 7 DAYS ─────────────────────────────────────────────────
def fetch_newsapi_history(api_key: str) -> list:
    raw = []
    seven_days_ago = (datetime.now(IST) - timedelta(days=7)).strftime('%Y-%m-%d')
    queries = [
        '"Nifty 50" OR "NSE India" OR "BSE Sensex"',
        '"RBI" OR "repo rate" OR "monetary policy India"',
        '"Indian market" OR "FII" OR "Dalal Street"',
        '"crude oil" OR "rupee" India market',
        '"US tariff" OR "Fed rate" OR "global market"',
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


# ─── 5. SMART DEDUPLICATION ──────────────────────────────────────────────────
def smart_deduplicate(items: list) -> list:
    def tokenize(text):
        return set(re.sub(r'[^a-z0-9 ]', '', text.lower()).split())
    kept = []
    for item in items:
        toks = tokenize(item["title"])
        if not any(
            len(toks & tokenize(s["title"])) / max(len(toks | tokenize(s["title"])), 1) > 0.55
            for s in kept
        ):
            kept.append(item)
    return kept


# ─── 6. MASTER PIPELINE ──────────────────────────────────────────────────────
def build_news_table(raw_items: list, gemini_key: str) -> pd.DataFrame:
    if not raw_items:
        return pd.DataFrame()

    deduped = smart_deduplicate(raw_items)
    titles = tuple(item["title"] for item in deduped)

    if not gemini_key:
        st.warning("⚠️ Gemini key not set. Add `gemini_api_key` to Streamlit Secrets for AI analysis.")
        return pd.DataFrame()

    analysis_map = {}
    for i in range(0, len(titles), 10):
        batch = titles[i:i+10]
        results = gemini_analyze(batch, gemini_key)
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
        topic = info.get("topic", "").strip() or " ".join(item["title"].split()[:5])
        sentiment = info.get("sentiment", "Mixed")
        s_icon = "🟢" if sentiment == "Positive" else "🔴" if sentiment == "Negative" else "🟡"
        rows.append({
            "Topic":               topic,
            "Timing":              item["time"],
            "Impact":              f"{info.get('impact_level','🟡 Moderate')} ({s_icon} {sentiment})",
            "Weight":              weight,
            "Logic Behind Impact": info.get("logic", "—"),
            "Source":              item["source"],
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2}
    df['_s'] = df['Impact'].apply(lambda x: next((v for k, v in rank.items() if k in str(x)), 99))
    return df.sort_values(['_s', 'Weight'], ascending=[True, False]).drop(columns=['_s']).reset_index(drop=True)


def build_future_table(gemini_key: str, news_key: str) -> pd.DataFrame:
    if not gemini_key:
        return pd.DataFrame()

    # Get future events from Gemini's financial calendar knowledge
    events = gemini_future_events(gemini_key)

    # Also fetch any forward-looking news from NewsAPI
    if news_key:
        today = datetime.now(IST).strftime('%Y-%m-%d')
        extra_raw = []
        for q in ['"RBI MPC"', '"Q4 results" India', '"FOMC" 2026', '"India CPI" 2026', '"earnings" Nifty 2026']:
            url = (
                "https://newsapi.org/v2/everything"
                f"?q={requests.utils.quote(q)}&from={today}"
                "&sortBy=publishedAt&language=en&pageSize=5"
                f"&apiKey={news_key}"
            )
            try:
                arts = requests.get(url, timeout=10).json().get('articles', [])
                for art in arts:
                    title = art.get('title', '').strip()
                    if title and title != '[Removed]':
                        extra_raw.append({"title": title, "time": "Upcoming", "source": art.get('source', {}).get('name', 'NewsAPI')})
            except Exception:
                continue

        if extra_raw:
            extra_deduped = smart_deduplicate(extra_raw)
            extra_titles = tuple(i["title"] for i in extra_deduped)
            extra_analysis = {}
            for i in range(0, len(extra_titles), 10):
                batch = extra_titles[i:i+10]
                results = gemini_analyze(batch, gemini_key)
                for r in results:
                    extra_analysis[i + r["index"] - 1] = r
            for idx, item in enumerate(extra_deduped):
                info = extra_analysis.get(idx, {})
                if info.get("relevant") and info.get("weight", 0) >= 5:
                    events.append({
                        "topic": info.get("topic", " ".join(item["title"].split()[:5])),
                        "timing": item["time"],
                        "sentiment": info.get("sentiment", "Mixed"),
                        "impact_level": info.get("impact_level", "🟡 Moderate"),
                        "weight": info.get("weight", 5),
                        "logic": info.get("logic", "—"),
                    })

    if not events:
        return pd.DataFrame()

    rows = []
    for e in events:
        sentiment = e.get("sentiment", "Mixed")
        s_icon = "🟢" if sentiment == "Positive" else "🔴" if sentiment == "Negative" else "🟡"
        rows.append({
            "Topic":               e.get("topic", "—"),
            "Timing":              e.get("timing", "Upcoming"),
            "Impact":              f"{e.get('impact_level','🟡 Moderate')} ({s_icon} {sentiment})",
            "Weight":              e.get("weight", 5),
            "Logic Behind Impact": e.get("logic", "—"),
            "Source":              e.get("source", "Gemini AI"),
        })

    df = pd.DataFrame(rows).drop_duplicates(subset=["Topic"])
    rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2}
    df['_s'] = df['Impact'].apply(lambda x: next((v for k, v in rank.items() if k in str(x)), 99))
    return df.sort_values(['_s', 'Weight'], ascending=[True, False]).drop(columns=['_s']).reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_all_data(gemini_key: str, news_key: str):
    raw = fetch_rss_live()
    if news_key:
        raw += fetch_newsapi_history(news_key)
    return build_news_table(raw, gemini_key)

@st.cache_data(ttl=300, show_spinner=False)
def fetch_future_data(gemini_key: str, news_key: str):
    return build_future_table(gemini_key, news_key)


# ─── 7. STYLED TABLE ─────────────────────────────────────────────────────────
def get_styled_table(df: pd.DataFrame):
    cols = ["Topic", "Timing", "Impact", "Weight", "Logic Behind Impact", "Source"]
    cols = [c for c in cols if c in df.columns]

    def color_impact(v):
        if 'Critical' in str(v): return 'color: red; font-weight: bold;'
        if 'High'     in str(v): return 'color: orange; font-weight: bold;'
        if 'Moderate' in str(v): return 'color: goldenrod; font-weight: bold;'
        return ''

    return df[cols].style\
        .map(color_impact, subset=['Impact'])\
        .map(lambda _: 'font-weight: bold;', subset=['Topic'])


# ─── 8. UI ────────────────────────────────────────────────────────────────────
st.title("🏛️ Nifty 50: Strategic Event Monitor")

gemini_key = st.secrets.get("gemini_api_key", "")
news_key   = st.secrets.get("news_api_key", "")
has_gemini = bool(gemini_key)
has_news   = bool(news_key)

if not has_gemini:
    st.error("⚠️ Gemini API key not set. All analysis requires Gemini. Add `gemini_api_key` to Streamlit Secrets → https://aistudio.google.com/app/apikey (free)")
    st.stop()

# Fetch
with st.spinner("🤖 Gemini AI fetching & analysing live Nifty 50 events..."):
    df_all = fetch_all_data(gemini_key, news_key)

# Sentiment Gauge
today_str = datetime.now(IST).strftime("%d %b")
today_df = df_all[df_all['Timing'].str.contains(today_str, na=False)] if not df_all.empty else pd.DataFrame()
today_score = int(today_df["Weight"].sum()) if not today_df.empty else 0
gauge_color = "red" if today_score > 30 else "orange" if today_score > 15 else "green"
st.subheader(f"Today's Market Intensity: :{gauge_color}[{today_score} / 50]")
st.progress(min(today_score / 50, 1.0) if today_score > 0 else 0.0)

now_ist = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")
st.info(f"📍 Bengaluru | Gemini AI-Powered | {now_ist} | Auto-Refresh: 60s")

# Table 1: Active Events
st.header("🔴 Active & Recent Events")
if not df_all.empty:
    st.caption(f"{len(df_all)} events | Filtered & analysed by Gemini AI | Topics synthesized, not raw headlines")
    st.table(get_styled_table(df_all))
else:
    st.warning("No relevant events found. Gemini may be rate-limited — wait 60s and refresh.")

# Table 2: Future Events
st.markdown("---")
st.header("📅 Upcoming Events (Next 30 Days)")
with st.spinner("🤖 Gemini AI building financial calendar outlook..."):
    df_future = fetch_future_data(gemini_key, news_key)

if not df_future.empty:
    st.caption("Generated by Gemini AI from financial calendar knowledge + live NewsAPI data.")
    st.table(get_styled_table(df_future))
else:
    st.info("Could not load upcoming events. Gemini may be rate-limited — try again in 60s.")

# Market Guide
st.markdown("---")
st.header("📖 How to Read Market Intensity")
c1, c2 = st.columns(2)
with c1:
    st.write("**0 – 15 (Low):** Sideways; narrow price range.")
    st.write("**16 – 30 (Active):** Clear trend forming; 100–200 pt moves.")
with c2:
    st.write("**31 – 45 (Stress):** High volatility; 300+ pt gaps.")
    st.write("**46 – 50 (Black Swan):** Extreme risk; circuit breaker possible.")

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
st.sidebar.header("🔧 System Status")

st.sidebar.subheader("🤖 Gemini AI")
if has_gemini:
    st.sidebar.success(f"✅ Active — gemini-2.0-flash (free tier)")
    st.sidebar.write("15 req/min · 1,500 req/day · Results cached 5 min")
else:
    st.sidebar.error("❌ Key missing")
    st.sidebar.write("Add `gemini_api_key` → https://aistudio.google.com/app/apikey")

st.sidebar.subheader("📰 NewsAPI (7-day history)")
if has_news:
    st.sidebar.success("✅ Connected")
else:
    st.sidebar.warning("⚠️ Not set — RSS feeds only")
    st.sidebar.write("Add `news_api_key` → https://newsapi.org/register")

st.sidebar.subheader("📡 Live RSS Feeds")
st.sidebar.write("\n".join(f"• {name}" for name in RSS_FEEDS))

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Weight Guide")
st.sidebar.write("**10** — Black Swan (rare)")
st.sidebar.write("**9** — Critical: 200+ pt swing")
st.sidebar.write("**7–8** — High: 100–200 pt swing")
st.sidebar.write("**5–6** — Moderate: stock-level move")

st.sidebar.markdown("---")
st.sidebar.subheader("🔬 API Health Check")
if st.sidebar.button("▶ Run Diagnostics"):
    # Gemini
    st.sidebar.write("**Gemini AI:**")
    if not gemini_key:
        st.sidebar.error("❌ Key missing")
    else:
        st.sidebar.write(f"🔑 Key: `...{gemini_key[-6:]}`")
        try:
            with st.spinner("Testing..."):
                test_url = (
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"gemini-2.0-flash:generateContent?key={gemini_key}"
                )
                test_payload = {
                    "contents": [{"parts": [{"text": "Say OK"}]}],
                    "generationConfig": {"maxOutputTokens": 5}
                }
                r = None
                for attempt in range(3):
                    r = requests.post(test_url, json=test_payload, timeout=15)
                    if r.status_code == 429:
                        st.sidebar.info(f"Rate limited, retrying ({attempt+1}/3)...")
                        time.sleep(2 ** attempt)
                        continue
                    break
            if r and r.status_code == 200:
                st.sidebar.success(f"✅ Gemini responding (HTTP 200)")
            elif r and r.status_code == 429:
                st.sidebar.warning("⚠️ Rate limited (429) — wait 60s")
            elif r and r.status_code == 403:
                st.sidebar.error("❌ Invalid key (403)")
            else:
                st.sidebar.error(f"❌ HTTP {r.status_code if r else 'timeout'}")
                if r: st.sidebar.code(str(r.json()))
        except Exception as e:
            st.sidebar.error(f"❌ {e}")

    # NewsAPI
    st.sidebar.write("**NewsAPI:**")
    if not news_key:
        st.sidebar.warning("⚠️ Key missing — RSS still works")
    else:
        try:
            with st.spinner("Testing..."):
                r = requests.get(f"https://newsapi.org/v2/everything?q=Nifty&pageSize=1&apiKey={news_key}", timeout=10)
                d = r.json()
            if r.status_code == 200 and d.get("status") == "ok":
                st.sidebar.success(f"✅ OK — {d.get('totalResults',0)} results")
            else:
                st.sidebar.error(f"❌ {r.status_code}: {d.get('message','')}")
        except Exception as e:
            st.sidebar.error(f"❌ {e}")

    # RSS
    st.sidebar.write("**RSS Feeds:**")
    ok, fail = 0, []
    for name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            if feed.entries: ok += 1
            else: fail.append(name)
        except Exception:
            fail.append(name)
    st.sidebar.success(f"✅ {ok}/{len(RSS_FEEDS)} feeds live")
    if fail:
        st.sidebar.warning(f"⚠️ Failed: {', '.join(fail)}")
