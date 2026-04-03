import streamlit as st
import pandas as pd
import feedparser
import requests
import json
import re
import time
import hashlib
from datetime import datetime, timedelta
from collections import Counter
import pytz
from streamlit_autorefresh import st_autorefresh

# ─── 1. SETUP ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Nifty 50 Hybrid Hub", layout="wide")
st_autorefresh(interval=60000, key="nifty_v6")
IST = pytz.timezone('Asia/Kolkata')

FREE_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash-8b", "gemini-1.0-pro"]

# ─── 2. RSS + NEWSAPI FETCH (cached 5 min) ───────────────────────────────────
RSS_FEEDS = {
    "Moneycontrol Markets":   "https://www.moneycontrol.com/rss/marketreports.xml",
    "Moneycontrol Economy":   "https://www.moneycontrol.com/rss/economy.xml",
    "Economic Times Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Economic Times Economy": "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms",
    "Business Standard":      "https://www.business-standard.com/rss/markets-106.rss",
    "LiveMint Markets":       "https://www.livemint.com/rss/markets",
    "Financial Express":      "https://www.financialexpress.com/market/feed/",
}

@st.cache_data(ttl=300, show_spinner=False)
def fetch_raw_news(news_key: str) -> tuple:
    """Fetch all raw headlines from RSS + NewsAPI. Cached 5 min. Returns tuple for cache stability."""
    raw = []

    # RSS
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
                raw.append((title, time_str, source_name))
        except Exception:
            continue

    # NewsAPI
    if news_key:
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
                f"?q={requests.utils.quote(q)}&from={seven_days_ago}"
                "&sortBy=publishedAt&language=en&pageSize=10"
                f"&apiKey={news_key}"
            )
            try:
                arts = requests.get(url, timeout=10).json().get('articles', [])
                for art in arts:
                    title = art.get('title', '').strip()
                    if not title or title == '[Removed]':
                        continue
                    try:
                        dt_ist = datetime.strptime(art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc).astimezone(IST)
                        time_str = dt_ist.strftime("%d %b, %I:%M %p")
                    except Exception:
                        time_str = "N/A"
                    source = art.get('source', {}).get('name', 'NewsAPI')
                    raw.append((title, time_str, source))
            except Exception:
                continue

    # Deduplicate
    def tokenize(text):
        return set(re.sub(r'[^a-z0-9 ]', '', text.lower()).split())

    kept = []
    for item in raw:
        toks = tokenize(item[0])
        if not any(
            len(toks & tokenize(s[0])) / max(len(toks | tokenize(s[0])), 1) > 0.55
            for s in kept
        ):
            kept.append(item)

    return tuple(kept)  # tuple so it's hashable/cacheable


# ─── 3. GEMINI CALL — WITH MODEL FALLBACK ────────────────────────────────────
def call_gemini(prompt: str, gemini_key: str, max_tokens: int = 4096) -> str | None:
    """
    Try each free Gemini model in order. Returns raw text or None.
    Does NOT cache — caching is done at the caller level with stable keys.
    """
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens}
    }
    for model in FREE_MODELS:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={gemini_key}"
        )
        for attempt in range(2):
            try:
                resp = requests.post(url, json=payload, timeout=40)
                if resp.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                if resp.status_code in (404, 400):
                    break  # try next model
                if resp.status_code == 200:
                    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip(), model
            except Exception:
                break
    return None, None


# ─── 4. GEMINI ANALYSIS — CACHED ON CONTENT HASH ─────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)  # 30 min cache — stable across refreshes
def gemini_analyze_cached(headlines_hash: str, headlines: tuple, gemini_key: str) -> list:
    """
    Cache key = content hash of headlines, not the raw list.
    This means same headlines across multiple refreshes = ONE Gemini call, not many.
    TTL = 30 min so Gemini is called at most ~48 times/day total.
    """
    if not headlines or not gemini_key:
        return []

    numbered = "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines))
    today = datetime.now(IST).strftime("%d %b %Y")

    prompt = f"""You are a senior Indian equity market strategist covering Nifty 50. Today is {today}.

Analyse each raw news headline. For EACH return ALL fields:

1. relevant (true/false) — Does this headline have a DIRECT mechanism to move Nifty 50?
   TRUE: RBI/Fed policy, FII flows, crude oil, rupee, India macro data, constituent earnings, US market moves, tariff wars, geopolitical events affecting India oil/exports, SEBI actions, major NSE IPOs.
   FALSE: cricket, IPL, Bollywood, crime, food, travel, real estate, foreign company news with no India angle.

2. topic — 2-5 word Bloomberg terminal label. NOT the raw headline. Synthesize cleanly.
   Examples: "RBI Repo Rate Cut", "Crude Oil Spike", "US Tariff Escalation", "FII Selling Surge", "Dow Jones Crash", "IT Sector Earnings", "Rupee Weakness", "Gold Safe-Haven Rally"

3. sentiment — "Positive" / "Negative" / "Mixed" for Nifty 50

4. impact_level — "🔴 Critical" / "🟠 High" / "🟡 Moderate"

5. weight — integer 5–10

6. logic — 2-3 sentences. Specific mechanism, sectors, stock names, numbers from the headline. Unique per headline — never repeat same text.

Headlines:
{numbered}

Raw JSON array only — no markdown:
[{{"index":1,"relevant":true,"topic":"Topic Here","sentiment":"Negative","impact_level":"🔴 Critical","weight":9,"logic":"Specific logic here."}}]"""

    raw_text, model_used = call_gemini(prompt, gemini_key, max_tokens=4096)
    if not raw_text:
        return []

    try:
        clean = re.sub(r"```json|```", "", raw_text).strip()
        parsed = json.loads(clean)
        logics = [item.get("logic", "") for item in parsed if item.get("relevant")]
        if logics and Counter(logics).most_common(1)[0][1] > len(logics) * 0.4:
            return []  # templated output, reject
        # Tag which model was used
        for item in parsed:
            item["_model"] = model_used
        return parsed
    except Exception:
        return []


@st.cache_data(ttl=1800, show_spinner=False)
def gemini_future_cached(gemini_key: str, date_key: str) -> list:
    """
    date_key = today's date string — ensures one call per day max for future events.
    TTL = 30 min. Future events don't change by the minute.
    """
    if not gemini_key:
        return []

    today = datetime.now(IST).strftime("%d %b %Y")
    prompt = f"""You are a senior Indian equity market strategist. Today is {today}.

List the TOP 8 upcoming events in the next 30 days that will most significantly impact the Nifty 50 index.
These must be REAL scheduled events — earnings dates, RBI/Fed meetings, macro data releases, policy announcements.

For each return:
- topic: 2-5 word Bloomberg label
- timing: specific date or range (e.g. "09 Apr 2026")
- sentiment: "Positive" / "Negative" / "Mixed"
- impact_level: "🔴 Critical" / "🟠 High" / "🟡 Moderate"
- weight: 5-10
- logic: 2-3 sentences — which Nifty stocks/sectors affected, what magnitude of move expected, why.

Raw JSON array only:
[{{"topic":"RBI MPC Decision","timing":"07-09 Apr 2026","sentiment":"Mixed","impact_level":"🔴 Critical","weight":9,"logic":"RBI rate decision directly moves banking heavyweights HDFCBANK, ICICIBANK. A cut could lift Nifty 200+ pts. Market pricing 25bps cut on slowing growth."}}]"""

    raw_text, model_used = call_gemini(prompt, gemini_key, max_tokens=2048)
    if not raw_text:
        return []

    try:
        clean = re.sub(r"```json|```", "", raw_text).strip()
        parsed = json.loads(clean)
        for item in parsed:
            item["_model"] = model_used
        return parsed
    except Exception:
        return []


# ─── 5. KEYWORD FALLBACK — WHEN GEMINI UNAVAILABLE ───────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def keyword_fallback_analysis(raw_news: tuple) -> list:
    """
    Pure Python analysis — zero API calls. Used when Gemini is unavailable.
    Gives basic topic/sentiment/logic without AI, so users always see something.
    """
    # Fetch Nifty 50 constituent list dynamically from Wikipedia
    nifty_stocks = fetch_nifty50_constituents()

    results = []
    for title, time_str, source in raw_news:
        t = title.lower()

        # Hard filter — obvious non-market content
        non_market = ['cricket','ipl','bollywood','movie','film','celebrity',
                      'wedding','recipe','fashion','horoscope','sports score',
                      'murder','crime','arrest','accident']
        if any(k in t for k in non_market):
            continue

        # Score relevance
        score = 0
        if any(k in t for k in ['nifty','sensex','nse','bse','dalal street']): score += 3
        if any(k in t for k in ['rbi','fed','repo','mpc','monetary','fomc','powell']): score += 3
        if any(k in t for k in ['fii','fpi','foreign investor','foreign fund']): score += 3
        if any(k in t for k in ['crude','brent','oil price','wti','petroleum']): score += 2
        if any(k in t for k in ['rupee','inr','forex','dollar index']): score += 2
        if any(k in t for k in ['inflation','cpi','wpi','gdp','iip']): score += 2
        if any(k in t for k in ['tariff','trade war','sanction','geopolit']): score += 2
        if any(k in t for k in ['war','conflict','strike','missile','iran','ukraine']): score += 2
        if any(k in t for k in ['earnings','results','q4','q3','quarterly','profit']): score += 2
        if any(k in t for k in ['gold','silver','comex']): score += 1
        if any(k in t for k in ['ipo','listing','sebi']): score += 1
        if any(s.lower() in t for s in nifty_stocks): score += 2
        if 'india' in t and any(k in t for k in ['market','stock','equity','index']): score += 1

        if score < 2:
            continue

        # Topic
        topic = derive_topic(t, title)
        # Sentiment
        neg_words = ['crash','fall','drop','decline','slump','weak','loss','sell','tariff',
                     'war','conflict','crisis','threat','sanction','recession','gap down',
                     'concern','uncertainty','pressure','negative','fear','risk']
        pos_words = ['rise','rally','gain','jump','surge','rebound','recover','growth',
                     'strong','boost','cut','intervention','support','profit','beat','inflow']
        neg = sum(1 for k in neg_words if k in t)
        pos = sum(1 for k in pos_words if k in t)
        sentiment = "Positive" if pos > neg else "Negative" if neg > pos else "Mixed"

        # Impact
        if score >= 5:
            impact, weight = "🔴 Critical", 8
        elif score >= 3:
            impact, weight = "🟠 High", 6
        else:
            impact, weight = "🟡 Moderate", 5

        # Logic
        logic = derive_logic(t, title, nifty_stocks)

        results.append({
            "topic": topic, "time": time_str, "source": source,
            "impact": f"{impact} ({'🟢' if sentiment=='Positive' else '🔴' if sentiment=='Negative' else '🟡'} {sentiment})",
            "weight": weight, "logic": logic, "_model": "Keyword Engine"
        })

    return results


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_nifty50_constituents() -> list:
    """Fetch current Nifty 50 stock names from Wikipedia — no hardcoding."""
    try:
        url = "https://en.wikipedia.org/wiki/NIFTY_50"
        resp = requests.get(url, timeout=10)
        # Extract company names from the wiki table
        names = re.findall(r'title="([^"]+)">[^<]+</a>\s*</td>', resp.text)
        # Filter to likely stock names (short, no spaces or 1-2 words)
        stocks = [n.lower() for n in names if len(n) < 30 and n[0].isupper()]
        return list(set(stocks))[:60] if stocks else []
    except Exception:
        return []


def derive_topic(t: str, title: str) -> str:
    """Derive a clean topic label from headline text."""
    if 'iran' in t and any(k in t for k in ['war','strike','threat','conflict','escalat']): return "Iran Strike Threat"
    if any(k in t for k in ['dow jones','dow futures']): return "Dow Jones Selloff"
    if any(k in t for k in ['nasdaq']) and any(k in t for k in ['fall','crash','drop']): return "Nasdaq Tech Selloff"
    if 'trump' in t and any(k in t for k in ['tariff','trade']): return "US Tariff Escalation"
    if 'trump' in t and 'iran' in t: return "Trump Iran Rhetoric"
    if 'trump' in t: return "Trump Policy Uncertainty"
    if any(k in t for k in ['rbi']) and any(k in t for k in ['rate','repo','mpc','policy']): return "RBI Monetary Policy"
    if any(k in t for k in ['rbi']) and any(k in t for k in ['rupee','ndf','intervention']): return "RBI Currency Intervention"
    if any(k in t for k in ['rate cut','repo cut']): return "RBI Repo Rate Cut"
    if any(k in t for k in ['rate hike','hawkish']): return "Rate Hike Signal"
    if any(k in t for k in ['fed','fomc','powell']): return "US Fed Rate Decision"
    if any(k in t for k in ['fii','fpi']) and any(k in t for k in ['sell','outflow','exit']): return "FII Selling Surge"
    if any(k in t for k in ['fii','fpi']) and any(k in t for k in ['buy','inflow']): return "FII Buying Inflow"
    if any(k in t for k in ['crude','brent','oil price']) and any(k in t for k in ['surge','spike','rise','jump']): return "Crude Oil Price Spike"
    if any(k in t for k in ['crude','brent','oil price']) and any(k in t for k in ['drop','fall','decline']): return "Crude Oil Price Drop"
    if any(k in t for k in ['gold','silver','comex']) and any(k in t for k in ['surge','rally','high']): return "Gold Safe-Haven Rally"
    if any(k in t for k in ['rupee','inr']) and any(k in t for k in ['fall','weak','low','record']): return "Rupee Weakness"
    if any(k in t for k in ['rupee','inr']) and any(k in t for k in ['rise','rebound','strong']): return "Rupee Recovery"
    if any(k in t for k in ['inflation','cpi','wpi']): return "India Inflation Data"
    if any(k in t for k in ['gdp','economic growth']): return "India GDP Data"
    if any(k in t for k in ['earnings','results','q4','q3','quarterly']): return "Nifty Earnings Report"
    if any(k in t for k in ['ipo','listing']): return "NSE IPO Event"
    if any(k in t for k in ['sebi']): return "SEBI Regulatory Action"
    if any(k in t for k in ['market cap','global cap']): return "India Market Cap Move"
    if any(k in t for k in ['war','conflict','middle east','geopolit']): return "Geopolitical Risk Event"
    stopwords = {'the','a','an','in','on','at','for','of','to','is','are','was','by','with','after','and','or','from'}
    words = [w for w in re.sub(r'[^a-zA-Z0-9 ]','',title).split() if w.lower() not in stopwords]
    return " ".join(words[:4]) if words else title[:25]


def derive_logic(t: str, title: str, stocks: list) -> str:
    """Derive specific logic from headline text."""
    matched = [s.title() for s in stocks if s in t][:2]
    target = ", ".join(matched) if matched else "Nifty heavyweights"

    if any(k in t for k in ['gold','silver','comex']): return f"Precious metal move signals safe-haven demand; equity rotation out of {target} likely."
    if any(k in t for k in ['dow jones','dow futures','nasdaq']): return f"US market fall triggers overnight FII selling; {target} expected to gap down at NSE open."
    if 'iran' in t and any(k in t for k in ['war','conflict','strike','threat']): return f"Iran conflict spikes crude oil; BPCL, ONGC gain but aviation and {target} face cost pressure."
    if any(k in t for k in ['crude','brent','oil price']): return f"Crude move hits India import bill; {target} reprice on fuel cost and inflation impact."
    if any(k in t for k in ['tariff','trade war']): return f"US tariffs raise global risk-off; FIIs exit emerging markets, {target} under selling pressure."
    if 'trump' in t: return f"Trump policy uncertainty drives FII caution; {target} vulnerable to risk-off sentiment."
    if any(k in t for k in ['rbi','mpc','repo']): return f"RBI policy signals affect {target}; market re-prices rate trajectory and banking sector flows."
    if any(k in t for k in ['fed','fomc','powell']): return f"Fed stance drives dollar/yield; FII flows into {target} react to global rate movement."
    if any(k in t for k in ['fii','fpi']): return f"FII flow data directly moves {target}; sets overall Nifty 50 direction at open."
    if any(k in t for k in ['rupee','inr']): return f"Rupee move affects {target}; IT exporters gain on weak INR, importers lose margin."
    if any(k in t for k in ['inflation','cpi','wpi']): return f"Inflation data shifts RBI rate expectations; {target} reprice on policy outlook change."
    if any(k in t for k in ['gdp','iip']): return f"GDP/IIP data resets earnings expectations; {target} valuations re-rated by market."
    if any(k in t for k in ['earnings','results','q4','q3']): return f"{target} earnings beat/miss sets sector tone and near-term Nifty direction."
    if any(k in t for k in ['war','conflict','geopolit']): return f"Geopolitical risk triggers FII exit from EM; {target} under broad selling pressure."
    return f"{target} directly in focus; watch for index-level moves at NSE open."


# ─── 6. MASTER DATA PIPELINE ─────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_active_events(gemini_key: str, news_key: str) -> tuple[pd.DataFrame, str]:
    """Returns (dataframe, source_label). Always returns something."""
    raw_news = fetch_raw_news(news_key)
    if not raw_news:
        return pd.DataFrame(), "No data"

    # Try Gemini first
    if gemini_key:
        # Stable hash of headline content → cache key doesn't change between refreshes
        content_hash = hashlib.md5(str(raw_news).encode()).hexdigest()
        titles = tuple(item[0] for item in raw_news)
        analysis = gemini_analyze_cached(content_hash, titles, gemini_key)

        if analysis:
            rows = []
            model_used = None
            for idx, (title, time_str, source) in enumerate(raw_news):
                info = next((a for a in analysis if a.get("index") == idx + 1), {})
                if not info.get("relevant"): continue
                weight = info.get("weight", 5)
                if weight < 5: continue
                topic = info.get("topic","").strip() or derive_topic(title.lower(), title)
                sentiment = info.get("sentiment","Mixed")
                s_icon = "🟢" if sentiment=="Positive" else "🔴" if sentiment=="Negative" else "🟡"
                model_used = info.get("_model","Gemini")
                rows.append({
                    "Topic": topic,
                    "Timing": time_str,
                    "Impact": f"{info.get('impact_level','🟡 Moderate')} ({s_icon} {sentiment})",
                    "Weight": weight,
                    "Logic Behind Impact": info.get("logic","—"),
                    "Source": source,
                })
            if rows:
                df = pd.DataFrame(rows)
                rank = {"🔴 Critical":0,"🟠 High":1,"🟡 Moderate":2}
                df['_s'] = df['Impact'].apply(lambda x: next((v for k,v in rank.items() if k in str(x)),99))
                df = df.sort_values(['_s','Weight'],ascending=[True,False]).drop(columns=['_s']).reset_index(drop=True)
                return df, f"Gemini AI ({model_used})"

    # Keyword fallback — always works, zero API calls
    results = keyword_fallback_analysis(raw_news)
    if not results:
        return pd.DataFrame(), "No relevant events"

    rows = [{
        "Topic": r["topic"], "Timing": r["time"],
        "Impact": r["impact"], "Weight": r["weight"],
        "Logic Behind Impact": r["logic"], "Source": r["source"],
    } for r in results]
    df = pd.DataFrame(rows)
    rank = {"🔴 Critical":0,"🟠 High":1,"🟡 Moderate":2}
    df['_s'] = df['Impact'].apply(lambda x: next((v for k,v in rank.items() if k in str(x)),99))
    df = df.sort_values(['_s','Weight'],ascending=[True,False]).drop(columns=['_s']).reset_index(drop=True)
    return df, "Keyword Engine (Gemini rate-limited)"


@st.cache_data(ttl=1800, show_spinner=False)
def get_future_events(gemini_key: str, news_key: str) -> tuple[pd.DataFrame, str]:
    date_key = datetime.now(IST).strftime("%Y-%m-%d")
    events = gemini_future_cached(gemini_key, date_key) if gemini_key else []
    model_used = events[0].get("_model","Gemini") if events else "—"

    if not events:
        return pd.DataFrame(), "Gemini unavailable"

    rows = []
    for e in events:
        sentiment = e.get("sentiment","Mixed")
        s_icon = "🟢" if sentiment=="Positive" else "🔴" if sentiment=="Negative" else "🟡"
        rows.append({
            "Topic": e.get("topic","—"),
            "Timing": e.get("timing","Upcoming"),
            "Impact": f"{e.get('impact_level','🟡 Moderate')} ({s_icon} {sentiment})",
            "Weight": e.get("weight",5),
            "Logic Behind Impact": e.get("logic","—"),
            "Source": "Gemini AI",
        })

    df = pd.DataFrame(rows).drop_duplicates(subset=["Topic"])
    rank = {"🔴 Critical":0,"🟠 High":1,"🟡 Moderate":2}
    df['_s'] = df['Impact'].apply(lambda x: next((v for k,v in rank.items() if k in str(x)),99))
    df = df.sort_values(['_s','Weight'],ascending=[True,False]).drop(columns=['_s']).reset_index(drop=True)
    return df, f"Gemini AI ({model_used})"


# ─── 7. STYLED TABLE ─────────────────────────────────────────────────────────
def get_styled_table(df: pd.DataFrame) -> pd.DataFrame.style:
    cols = ["Topic","Timing","Impact","Weight","Logic Behind Impact","Source"]
    cols = [c for c in cols if c in df.columns]
    def color_impact(v):
        if 'Critical' in str(v): return 'color:red;font-weight:bold;'
        if 'High'     in str(v): return 'color:orange;font-weight:bold;'
        if 'Moderate' in str(v): return 'color:goldenrod;font-weight:bold;'
        return ''
    return df[cols].style\
        .map(color_impact, subset=['Impact'])\
        .map(lambda _: 'font-weight:bold;', subset=['Topic'])


# ─── 8. UI ────────────────────────────────────────────────────────────────────
st.title("🏛️ Nifty 50: Strategic Event Monitor")

gemini_key = st.secrets.get("gemini_api_key", "")
news_key   = st.secrets.get("news_api_key", "")

# Active events
with st.spinner("Fetching & analysing live Nifty 50 events..."):
    df_all, source_label = get_active_events(gemini_key, news_key)

# Sentiment Gauge
today_str = datetime.now(IST).strftime("%d %b")
today_df = df_all[df_all['Timing'].str.contains(today_str, na=False)] if not df_all.empty else pd.DataFrame()
today_score = int(today_df["Weight"].sum()) if not today_df.empty else 0
gauge_color = "red" if today_score > 30 else "orange" if today_score > 15 else "green"
st.subheader(f"Today's Market Intensity: :{gauge_color}[{today_score} / 50]")
st.progress(min(today_score / 50, 1.0))

now_ist = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")
st.info(f"📍 Bengaluru | Engine: **{source_label}** | {now_ist} | Auto-Refresh: 60s")

st.header("🔴 Active & Recent Events")
if not df_all.empty:
    st.caption(f"{len(df_all)} events | Engine: {source_label}")
    st.table(get_styled_table(df_all))
else:
    st.warning("No relevant events loaded. Check API keys or internet connection.")

# Future events
st.markdown("---")
st.header("📅 Upcoming Events (Next 30 Days)")
with st.spinner("Building financial calendar outlook..."):
    df_future, future_label = get_future_events(gemini_key, news_key)

if not df_future.empty:
    st.caption(f"Source: {future_label}")
    st.table(get_styled_table(df_future))
else:
    st.info("Future events unavailable — Gemini may be rate-limited. Refreshes automatically.")

# Market Guide
st.markdown("---")
st.header("📖 Market Intensity Guide")
c1, c2 = st.columns(2)
with c1:
    st.write("**0–15:** Sideways; narrow range.")
    st.write("**16–30:** Trend forming; 100–200 pt moves.")
with c2:
    st.write("**31–45:** High volatility; 300+ pt gaps.")
    st.write("**46–50:** Black Swan; circuit breaker risk.")

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
st.sidebar.header("🔧 System Status")

# Engine status
st.sidebar.subheader("🤖 Analysis Engine")
if gemini_key:
    st.sidebar.success("✅ Gemini AI (free tier)")
    st.sidebar.write("**Fallback chain:**")
    st.sidebar.write("1. gemini-2.0-flash")
    st.sidebar.write("2. gemini-1.5-flash-8b")
    st.sidebar.write("3. gemini-1.0-pro")
    st.sidebar.write("4. ⚙️ Keyword Engine (if all rate-limited)")
    st.sidebar.write("Cache: 30 min — Gemini called max ~48×/day")
else:
    st.sidebar.warning("⚠️ Gemini key missing → Keyword Engine active")
    st.sidebar.write("Add `gemini_api_key` → https://aistudio.google.com/app/apikey")

st.sidebar.subheader("📰 NewsAPI")
if news_key:
    st.sidebar.success("✅ Connected (7-day history)")
else:
    st.sidebar.warning("⚠️ Not set — RSS only")

st.sidebar.subheader("⚖️ Weight Guide")
st.sidebar.write("**9–10** Critical: 200+ pt swing")
st.sidebar.write("**7–8** High: 100–200 pt swing")
st.sidebar.write("**5–6** Moderate: stock-level move")

# Diagnostics
st.sidebar.markdown("---")
st.sidebar.subheader("🔬 Diagnostics")
if st.sidebar.button("▶ Run Health Check"):
    st.sidebar.write("**Gemini AI:**")
    if not gemini_key:
        st.sidebar.error("❌ Key missing")
    else:
        active_model = None
        for model in FREE_MODELS:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                r = requests.post(url, json={"contents":[{"parts":[{"text":"Say OK"}]}],"generationConfig":{"maxOutputTokens":5}}, timeout=10)
                if r.status_code == 200:
                    active_model = model
                    break
                elif r.status_code == 429:
                    st.sidebar.info(f"`{model}` rate limited → trying next...")
                    time.sleep(1)
            except Exception:
                continue
        if active_model:
            st.sidebar.success(f"✅ Active on `{active_model}`")
        else:
            st.sidebar.warning("⚠️ All models rate-limited → Keyword Engine in use")

    st.sidebar.write("**NewsAPI:**")
    if not news_key:
        st.sidebar.warning("⚠️ Not set")
    else:
        try:
            r = requests.get(f"https://newsapi.org/v2/everything?q=Nifty&pageSize=1&apiKey={news_key}", timeout=10)
            d = r.json()
            if r.status_code == 200 and d.get("status") == "ok":
                st.sidebar.success(f"✅ OK — {d.get('totalResults',0)} results")
            else:
                st.sidebar.error(f"❌ {r.status_code}: {d.get('message','')}")
        except Exception as e:
            st.sidebar.error(f"❌ {e}")

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
