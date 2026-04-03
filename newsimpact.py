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
st_autorefresh(interval=120000, key="nifty_v7")   # 2-min refresh — gentler on rate limits
IST = pytz.timezone('Asia/Kolkata')

FREE_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash-8b", "gemini-1.0-pro"]

# ─── 2. SINGLE GEMINI CALLER WITH MODEL FALLBACK ─────────────────────────────
def call_gemini(prompt: str, gemini_key: str, max_tokens: int = 800) -> tuple:
    """
    Try each free model. On 429 wait 65s (full minute reset) then retry.
    Returns (text, model_name) or (None, None).
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
                resp = requests.post(url, json=payload, timeout=45)
                if resp.status_code == 200:
                    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return text, model
                if resp.status_code == 429:
                    # Wait for rate limit window to reset, then try next model
                    time.sleep(65 if attempt == 1 else 10)
                    continue
                if resp.status_code in (404, 400):
                    break   # model not available, skip to next
            except Exception:
                break
    return None, None

# ─── 3. RSS + NEWSAPI — CACHED 5 MIN ─────────────────────────────────────────
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
    """Fetch & deduplicate all raw headlines. Returns tuple of (title, time, source)."""
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
                        pub = datetime(*entry.published_parsed[:6]).replace(tzinfo=pytz.utc).astimezone(IST)
                        ts = pub.strftime("%d %b, %I:%M %p")
                    else:
                        ts = datetime.now(IST).strftime("%d %b, %I:%M %p")
                except Exception:
                    ts = datetime.now(IST).strftime("%d %b, %I:%M %p")
                raw.append((title, ts, source_name))
        except Exception:
            continue

    if news_key:
        seven_days_ago = (datetime.now(IST) - timedelta(days=7)).strftime('%Y-%m-%d')
        for q in [
            '"Nifty 50" OR "NSE India" OR "BSE Sensex"',
            '"RBI" OR "repo rate" OR "monetary policy India"',
            '"Indian market" OR "FII" OR "Dalal Street"',
            '"crude oil" OR "rupee" India market',
            '"US tariff" OR "Fed rate" OR "global market"',
        ]:
            try:
                url = (
                    "https://newsapi.org/v2/everything"
                    f"?q={requests.utils.quote(q)}&from={seven_days_ago}"
                    "&sortBy=publishedAt&language=en&pageSize=10"
                    f"&apiKey={news_key}"
                )
                arts = requests.get(url, timeout=10).json().get('articles', [])
                for art in arts:
                    title = art.get('title', '').strip()
                    if not title or title == '[Removed]':
                        continue
                    try:
                        dt = datetime.strptime(art['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.utc).astimezone(IST)
                        ts = dt.strftime("%d %b, %I:%M %p")
                    except Exception:
                        ts = "N/A"
                    raw.append((title, ts, art.get('source', {}).get('name', 'NewsAPI')))
            except Exception:
                continue

    # Deduplicate by Jaccard overlap
    def tok(t): return set(re.sub(r'[^a-z0-9 ]', '', t.lower()).split())
    kept = []
    for item in raw:
        toks = tok(item[0])
        if not any(len(toks & tok(s[0])) / max(len(toks | tok(s[0])), 1) > 0.55 for s in kept):
            kept.append(item)
    return tuple(kept)

# ─── 4. PER-HEADLINE GEMINI ANALYSIS — 24H CACHE ─────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def gemini_analyze_one(h_hash: str, headline: str, gemini_key: str) -> dict:
    """
    One Gemini call per unique headline. Cached 24h — never re-called for same headline.
    Prompt is compact (<200 tokens) to maximise throughput within rate limits.
    """
    today = datetime.now(IST).strftime("%d %b %Y")
    prompt = f"""Senior Nifty 50 analyst. Today: {today}.

Headline: "{headline}"

Return a single raw JSON object (no markdown):
{{
  "relevant": true/false,
  "topic": "2-5 word Bloomberg label",
  "sentiment": "Positive"/"Negative"/"Mixed",
  "impact_level": "🔴 Critical"/"🟠 High"/"🟡 Moderate",
  "weight": 5-10,
  "logic": "2-3 sentences: specific Nifty mechanism, sectors, stock names, numbers."
}}

relevant=true only if direct Nifty 50 mechanism exists (RBI/Fed policy, FII flows, crude/rupee, India macro, constituent earnings, US market crash, tariffs hitting India, geopolitical oil/export impact, SEBI, NSE IPO).
relevant=false for cricket, Bollywood, crime, lifestyle, foreign stocks with no India angle."""

    text, model = call_gemini(prompt, gemini_key, max_tokens=300)
    if not text:
        return {}
    try:
        clean = re.sub(r"```json|```", "", text).strip()
        result = json.loads(clean)
        result["_model"] = model
        return result
    except Exception:
        return {}

# ─── 5. FUTURE EVENTS — SINGLE GEMINI CALL, CACHED 6H ───────────────────────
@st.cache_data(ttl=21600, show_spinner=False)
def gemini_future(gemini_key: str, date_key: str) -> list:
    """
    One Gemini call for the full 30-day event calendar. Cached 6h.
    Called after a deliberate 10s pause so rate limit has headroom.
    """
    if not gemini_key:
        return []
    today = datetime.now(IST).strftime("%d %b %Y")
    prompt = f"""Senior Nifty 50 strategist. Today: {today}.

List the 8 most impactful SCHEDULED events for Nifty 50 in the next 30 days.
Include: RBI/Fed meetings, major earnings dates (TCS, Infosys, HDFCBANK etc), India CPI/GDP/IIP releases, SEBI events, budget sessions.

Return raw JSON array only:
[{{
  "topic": "2-5 word Bloomberg label",
  "timing": "specific date e.g. 09 Apr 2026",
  "sentiment": "Positive"/"Negative"/"Mixed",
  "impact_level": "🔴 Critical"/"🟠 High"/"🟡 Moderate",
  "weight": 5-10,
  "logic": "2-3 sentences: which Nifty stocks/sectors, expected move magnitude, why."
}}]"""

    # Deliberate pause before this call so we don't stack on active-events calls
    time.sleep(10)
    text, model = call_gemini(prompt, gemini_key, max_tokens=1500)
    if not text:
        return []
    try:
        clean = re.sub(r"```json|```", "", text).strip()
        parsed = json.loads(clean)
        for item in parsed:
            item["_model"] = model
        return parsed
    except Exception:
        return []

# ─── 6. PROGRESSIVE HEADLINE PROCESSOR ───────────────────────────────────────
def process_headlines_progressively(
    raw_news: tuple,
    gemini_key: str,
    result_placeholder,
    status_placeholder
):
    """
    Process headlines one at a time:
    - Check session cache first (instant, free)
    - If not cached: call Gemini, wait CALL_GAP seconds, update display
    - Render the table after EVERY new result so users see data arriving live
    - Never sends more than MAX_PER_RUN new calls in one page load
    - Hard sleep between calls keeps us at ~10 calls/min (under the 15/min limit)
    """
    CALL_GAP    = 7    # seconds between new Gemini calls → ~8.5 calls/min, safely under 15
    MAX_PER_RUN = 10   # max new calls per page load; rest served from cache next refresh

    if "hcache" not in st.session_state:
        st.session_state["hcache"] = {}

    rows = []
    new_calls = 0
    cached_count = 0
    total = len(raw_news)

    for i, (title, ts, source) in enumerate(raw_news):
        h = hashlib.md5(title.encode()).hexdigest()

        # Try session cache
        info = st.session_state["hcache"].get(h)

        if info is None:
            # Hard cap on new calls per run
            if new_calls >= MAX_PER_RUN:
                status_placeholder.info(
                    f"⏸ Paused at {MAX_PER_RUN} new calls this run. "
                    f"{total - i} headlines queued — will process on next refresh (2 min)."
                )
                break

            # Wait between calls to stay under 15/min
            if new_calls > 0:
                for remaining in range(CALL_GAP, 0, -1):
                    status_placeholder.info(
                        f"🤖 Gemini: {i}/{total} headlines | "
                        f"{new_calls} new calls | {cached_count} from cache | "
                        f"Next call in {remaining}s..."
                    )
                    time.sleep(1)

            # Call Gemini
            status_placeholder.info(
                f"🤖 Calling Gemini for headline {i+1}/{total}..."
            )
            info = gemini_analyze_one(h, title, gemini_key)
            st.session_state["hcache"][h] = info  # cache even empty result
            new_calls += 1
        else:
            cached_count += 1

        # Skip irrelevant or empty
        if not info or not info.get("relevant"):
            continue
        weight = info.get("weight", 5)
        if weight < 5:
            continue

        topic = info.get("topic", "").strip() or title[:40]
        sentiment = info.get("sentiment", "Mixed")
        s_icon = "🟢" if sentiment == "Positive" else "🔴" if sentiment == "Negative" else "🟡"

        rows.append({
            "Topic":               topic,
            "Timing":              ts,
            "Impact":              f"{info.get('impact_level','🟡 Moderate')} ({s_icon} {sentiment})",
            "Weight":              weight,
            "Logic Behind Impact": info.get("logic", "—"),
            "Source":              source,
        })

        # Re-render table after every new row so user sees live updates
        if rows:
            rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2}
            df = pd.DataFrame(rows)
            df['_s'] = df['Impact'].apply(lambda x: next((v for k, v in rank.items() if k in str(x)), 99))
            df = df.sort_values(['_s', 'Weight'], ascending=[True, False]).drop(columns=['_s']).reset_index(drop=True)
            result_placeholder.table(get_styled_table(df))

        status_placeholder.info(
            f"🤖 {i+1}/{total} headlines processed | "
            f"{new_calls} new Gemini calls | {cached_count} from cache"
        )

    # Final status
    pending = total - (i + 1) if new_calls >= MAX_PER_RUN else 0
    if pending > 0:
        status_placeholder.warning(
            f"✅ {len(rows)} events shown | {cached_count} cached | "
            f"{new_calls} new calls | ⏳ {pending} headlines queued for next refresh"
        )
    else:
        model_set = set()
        for _, info in st.session_state["hcache"].items():
            if info and info.get("_model"):
                model_set.add(info["_model"])
        status_placeholder.success(
            f"✅ {len(rows)} relevant events | {cached_count} cached | "
            f"{new_calls} new calls | Models: {', '.join(model_set) or 'Gemini'}"
        )

    return rows

# ─── 7. STYLED TABLE ─────────────────────────────────────────────────────────
def get_styled_table(df: pd.DataFrame):
    cols = ["Topic", "Timing", "Impact", "Weight", "Logic Behind Impact", "Source"]
    cols = [c for c in cols if c in df.columns]

    def color_impact(v):
        if 'Critical' in str(v): return 'color:red;font-weight:bold;'
        if 'High'     in str(v): return 'color:orange;font-weight:bold;'
        if 'Moderate' in str(v): return 'color:goldenrod;font-weight:bold;'
        return ''

    return df[cols].style \
        .map(color_impact, subset=['Impact']) \
        .map(lambda _: 'font-weight:bold;', subset=['Topic'])

# ─── 8. UI ────────────────────────────────────────────────────────────────────
st.title("🏛️ Nifty 50: Strategic Event Monitor")

gemini_key = st.secrets.get("gemini_api_key", "")
news_key   = st.secrets.get("news_api_key", "")

if not gemini_key:
    st.error(
        "⚠️ Gemini API key not set. "
        "Add `gemini_api_key` to Streamlit Secrets. "
        "Free key → https://aistudio.google.com/app/apikey"
    )
    st.stop()

now_ist = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")
st.info(f"📍 Bengaluru | Gemini AI | {now_ist} | Auto-Refresh: 2 min")

# ── FUTURE EVENTS (fetched first — just 1 Gemini call, 6h cache) ─────────────
st.header("📅 Upcoming Events — Next 30 Days")
fut_status = st.empty()
fut_table  = st.empty()

date_key = datetime.now(IST).strftime("%Y-%m-%d")

# Check if future events already in cache before calling
fut_status.info("📅 Loading upcoming events calendar...")
future_events = gemini_future(gemini_key, date_key)

if future_events:
    fut_rows = []
    model_f = future_events[0].get("_model", "Gemini")
    for e in future_events:
        sentiment = e.get("sentiment", "Mixed")
        s_icon = "🟢" if sentiment == "Positive" else "🔴" if sentiment == "Negative" else "🟡"
        fut_rows.append({
            "Topic":               e.get("topic", "—"),
            "Timing":              e.get("timing", "Upcoming"),
            "Impact":              f"{e.get('impact_level','🟡 Moderate')} ({s_icon} {sentiment})",
            "Weight":              e.get("weight", 5),
            "Logic Behind Impact": e.get("logic", "—"),
            "Source":              "Gemini AI",
        })
    df_fut = pd.DataFrame(fut_rows).drop_duplicates(subset=["Topic"])
    rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2}
    df_fut['_s'] = df_fut['Impact'].apply(lambda x: next((v for k, v in rank.items() if k in str(x)), 99))
    df_fut = df_fut.sort_values(['_s', 'Weight'], ascending=[True, False]).drop(columns=['_s']).reset_index(drop=True)
    fut_table.table(get_styled_table(df_fut))
    fut_status.success(f"✅ {len(fut_rows)} upcoming events | Model: {model_f} | Cached 6h")
else:
    fut_status.warning("⏳ Upcoming events loading — Gemini processing, will appear on next refresh.")

st.markdown("---")

# ── ACTIVE EVENTS (progressive, rate-limit aware) ────────────────────────────
st.header("🔴 Active & Recent Events")

with st.spinner("Fetching live headlines from RSS & NewsAPI..."):
    raw_news = fetch_raw_news(news_key)

total_raw = len(raw_news)
cached_already = sum(
    1 for (title, _, _) in raw_news
    if st.session_state.get("hcache", {}).get(hashlib.md5(title.encode()).hexdigest())
)
new_needed = total_raw - cached_already

st.caption(
    f"{total_raw} headlines fetched | "
    f"{cached_already} already cached (instant) | "
    f"{new_needed} new → Gemini (7s apart, max 10/run)"
)

# Placeholders for live updates
act_status = st.empty()
act_table  = st.empty()

process_headlines_progressively(raw_news, gemini_key, act_table, act_status)

# ── SENTIMENT GAUGE ───────────────────────────────────────────────────────────
st.markdown("---")
st.header("📊 Today's Market Intensity")

today_str = datetime.now(IST).strftime("%d %b")
hcache = st.session_state.get("hcache", {})
today_weight = 0
for (title, ts, _) in raw_news:
    if today_str in ts:
        h = hashlib.md5(title.encode()).hexdigest()
        info = hcache.get(h, {})
        if info and info.get("relevant"):
            today_weight += info.get("weight", 0)

gauge_color = "red" if today_weight > 30 else "orange" if today_weight > 15 else "green"
st.subheader(f"Intensity Score: :{gauge_color}[{today_weight} / 50]")
st.progress(min(today_weight / 50, 1.0))

c1, c2 = st.columns(2)
with c1:
    st.write("**0–15:** Sideways; narrow range.")
    st.write("**16–30:** Trend forming; 100–200 pt moves.")
with c2:
    st.write("**31–45:** High volatility; 300+ pt gaps.")
    st.write("**46–50:** Black Swan; circuit breaker risk.")

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
st.sidebar.header("🔧 System Status")

st.sidebar.subheader("🤖 Gemini AI")
st.sidebar.success("✅ Active (free tier)")
st.sidebar.write("**Model fallback:** gemini-2.0-flash → gemini-1.5-flash-8b → gemini-1.0-pro")
st.sidebar.write("**Rate strategy:** 1 headline/7s = ~8 calls/min (limit: 15/min)")
st.sidebar.write("**Per headline:** cached 24h — never re-called for same headline")
st.sidebar.write("**Future events:** cached 6h — 1 call per 6 hours")

hcache_size = len(st.session_state.get("hcache", {}))
st.sidebar.write(f"**Session cache:** {hcache_size} headlines stored")

if st.sidebar.button("🗑️ Clear Headline Cache"):
    st.session_state["hcache"] = {}
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("📰 NewsAPI")
if news_key:
    st.sidebar.success("✅ Connected (7-day history)")
else:
    st.sidebar.warning("⚠️ Not set — RSS only")
    st.sidebar.write("Add `news_api_key` → https://newsapi.org/register")

st.sidebar.subheader("⚖️ Weight Guide")
st.sidebar.write("**9–10** Critical: 200+ pt swing")
st.sidebar.write("**7–8** High: 100–200 pt swing")
st.sidebar.write("**5–6** Moderate: stock-level move")

st.sidebar.markdown("---")
st.sidebar.subheader("🔬 API Health Check")
if st.sidebar.button("▶ Run Diagnostics"):
    active_model = None
    for model in FREE_MODELS:
        try:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={gemini_key}"
            )
            r = requests.post(
                url,
                json={"contents": [{"parts": [{"text": "Say OK"}]}],
                      "generationConfig": {"maxOutputTokens": 5}},
                timeout=10
            )
            if r.status_code == 200:
                active_model = model
                break
            elif r.status_code == 429:
                st.sidebar.info(f"`{model}` rate limited → next model...")
                time.sleep(2)
        except Exception:
            continue

    if active_model:
        st.sidebar.success(f"✅ Gemini active on `{active_model}`")
    else:
        st.sidebar.warning("⚠️ All models rate-limited — wait 60s")

    if news_key:
        try:
            r = requests.get(
                f"https://newsapi.org/v2/everything?q=Nifty&pageSize=1&apiKey={news_key}",
                timeout=10
            )
            d = r.json()
            if r.status_code == 200 and d.get("status") == "ok":
                st.sidebar.success(f"✅ NewsAPI OK — {d.get('totalResults', 0)} results")
            else:
                st.sidebar.error(f"❌ NewsAPI {r.status_code}: {d.get('message', '')}")
        except Exception as e:
            st.sidebar.error(f"❌ {e}")

    ok, fail = 0, []
    for name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                ok += 1
            else:
                fail.append(name)
        except Exception:
            fail.append(name)
    st.sidebar.success(f"✅ {ok}/{len(RSS_FEEDS)} RSS feeds live")
    if fail:
        st.sidebar.warning(f"⚠️ Failed: {', '.join(fail)}")
