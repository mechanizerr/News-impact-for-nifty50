import streamlit as st
import pandas as pd
import feedparser
import requests
import json
import re
import time
import hashlib
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh

# ─── 1. SETUP ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Nifty 50 Hybrid Hub", layout="wide")
st_autorefresh(interval=120000, key="nifty_v8")
IST = pytz.timezone('Asia/Kolkata')
FREE_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash-8b", "gemini-1.0-pro"]

# ─── 2. GEMINI CALLER ────────────────────────────────────────────────────────
def call_gemini(prompt: str, gemini_key: str, max_tokens: int = 400) -> tuple:
    """Try each free model in order. On 429 move to next model immediately."""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens}
    }
    for model in FREE_MODELS:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={gemini_key}"
        )
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                return text, model
            if resp.status_code in (404, 400):
                continue   # model not found, try next
            if resp.status_code == 429:
                continue   # rate limited, try next model immediately
        except Exception:
            continue
    return None, None

# ─── 3. SESSION CACHE HELPERS ────────────────────────────────────────────────
def get_cache() -> dict:
    if "hcache" not in st.session_state:
        st.session_state["hcache"] = {}
    return st.session_state["hcache"]

def headline_hash(title: str) -> str:
    return hashlib.md5(title.encode()).hexdigest()

# ─── 4. SINGLE HEADLINE ANALYSIS — 24H CACHED ────────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def gemini_one(h_hash: str, headline: str, gemini_key: str) -> dict:
    """One Gemini call per unique headline. Result cached 24h by content hash."""
    today = datetime.now(IST).strftime("%d %b %Y")
    prompt = f"""Nifty 50 analyst. Today: {today}.
Headline: "{headline}"

Return JSON only (no markdown):
{{"relevant":true/false,"topic":"2-5 word label","sentiment":"Positive/Negative/Mixed","impact_level":"🔴 Critical/🟠 High/🟡 Moderate","weight":5-10,"logic":"2-3 sentences: exact Nifty mechanism, sectors, stock names, any numbers from headline."}}

relevant=true only if direct Nifty 50 impact: RBI/Fed policy, FII flows, crude/rupee, India macro data, Nifty constituent earnings, US market moves, tariffs on India, geopolitical events affecting oil/exports, SEBI, NSE IPO.
relevant=false: cricket, Bollywood, crime, lifestyle, real estate, foreign company news with no India angle."""

    text, model = call_gemini(prompt, gemini_key, max_tokens=300)
    if not text:
        return {"relevant": False, "_error": "no_response"}
    try:
        clean = re.sub(r"```json|```", "", text).strip()
        result = json.loads(clean)
        result["_model"] = model
        return result
    except Exception:
        return {"relevant": False, "_error": "parse_failed"}

# ─── 5. FUTURE EVENTS — 6H CACHED ────────────────────────────────────────────
@st.cache_data(ttl=21600, show_spinner=False)
def gemini_future(gemini_key: str, date_key: str) -> list:
    """One call for 30-day event calendar. Cached 6h. No sleep — just call."""
    if not gemini_key:
        return []
    today = datetime.now(IST).strftime("%d %b %Y")
    prompt = f"""Nifty 50 strategist. Today: {today}.

List 8 scheduled events in the next 30 days that will most move the Nifty 50 index.
Include: RBI/Fed meetings, major Nifty 50 earnings (TCS, Infosys, HDFCBANK etc), India CPI/GDP/IIP releases, SEBI events.

Return JSON array only (no markdown):
[{{"topic":"2-5 word label","timing":"e.g. 09 Apr 2026","sentiment":"Positive/Negative/Mixed","impact_level":"🔴 Critical/🟠 High/🟡 Moderate","weight":5-10,"logic":"2-3 sentences: which Nifty stocks/sectors affected, expected move size, why."}}]"""

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

# ─── 6. RSS + NEWSAPI FETCH — 5 MIN CACHED ───────────────────────────────────
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

    # Deduplicate
    def tok(t): return set(re.sub(r'[^a-z0-9 ]', '', t.lower()).split())
    kept = []
    for item in raw:
        toks = tok(item[0])
        if not any(len(toks & tok(s[0])) / max(len(toks | tok(s[0])), 1) > 0.55 for s in kept):
            kept.append(item)
    return tuple(kept)

# ─── 7. TABLE BUILDER ────────────────────────────────────────────────────────
def build_df(rows: list) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    rank = {"🔴 Critical": 0, "🟠 High": 1, "🟡 Moderate": 2}
    df['_s'] = df['Impact'].apply(lambda x: next((v for k, v in rank.items() if k in str(x)), 99))
    return df.sort_values(['_s', 'Weight'], ascending=[True, False]).drop(columns=['_s']).reset_index(drop=True)

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

# ─── 8. PROGRESSIVE HEADLINE PROCESSOR ───────────────────────────────────────
def process_headlines(raw_news, gemini_key, table_ph, status_ph):
    """
    For each headline:
    1. Check session cache → show immediately if found
    2. Otherwise call Gemini → wait CALL_GAP → store → re-render table
    Max 10 new Gemini calls per run. Remaining queued for next 2-min refresh.
    """
    CALL_GAP    = 7    # seconds between new calls → ~8/min, under 15/min limit
    MAX_PER_RUN = 10   # hard cap per page load

    cache = get_cache()
    rows = []
    new_calls = 0
    cached_hits = 0
    total = len(raw_news)

    for i, (title, ts, source) in enumerate(raw_news):
        h = headline_hash(title)
        info = cache.get(h)

        if info is None:
            # Hit the per-run cap — pause and show queue message
            if new_calls >= MAX_PER_RUN:
                remaining = total - i
                status_ph.warning(
                    f"⏸️ Processed {i}/{total} | {new_calls} new calls | "
                    f"{remaining} headlines queued → next refresh in 2 min"
                )
                break

            # Wait between calls (but not before the first one)
            if new_calls > 0:
                for secs in range(CALL_GAP, 0, -1):
                    status_ph.info(
                        f"🤖 {i}/{total} headlines | {new_calls} new calls | "
                        f"{cached_hits} cached | next call in {secs}s..."
                    )
                    time.sleep(1)

            # Make the Gemini call
            status_ph.info(f"🤖 Analysing headline {i+1}/{total} with Gemini...")
            info = gemini_one(h, title, gemini_key)
            cache[h] = info
            new_calls += 1
        else:
            cached_hits += 1

        # Build row only if relevant and weight >= 5
        if not info or not info.get("relevant"):
            continue
        weight = info.get("weight", 0)
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

        # Re-render table after EVERY relevant result — user sees data arriving live
        df = build_df(rows)
        table_ph.table(get_styled_table(df))
        status_ph.info(
            f"🤖 {i+1}/{total} | {len(rows)} events shown | "
            f"{new_calls} new calls | {cached_hits} cached"
        )

    # Final status
    if rows:
        models = set(cache[headline_hash(t)].get("_model","") for t,_,_ in raw_news if headline_hash(t) in cache and cache[headline_hash(t)])
        models_str = ", ".join(m for m in models if m)
        status_ph.success(
            f"✅ {len(rows)} Nifty 50 events | {cached_hits} from cache | "
            f"{new_calls} new Gemini calls | {models_str}"
        )
    else:
        status_ph.warning(
            f"⚠️ {new_calls} Gemini calls made but no relevant Nifty 50 events found yet. "
            f"{total - min(new_calls + cached_hits, total)} headlines still queued. "
            f"Refreshes in 2 min."
        )

# ─── 9. UI ────────────────────────────────────────────────────────────────────
st.title("🏛️ Nifty 50: Strategic Event Monitor")

gemini_key = st.secrets.get("gemini_api_key", "")
news_key   = st.secrets.get("news_api_key", "")

if not gemini_key:
    st.error("⚠️ Add `gemini_api_key` to Streamlit Secrets → https://aistudio.google.com/app/apikey (free)")
    st.stop()

now_ist = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")
st.info(f"📍 Bengaluru | Gemini AI | {now_ist} | Auto-Refresh: 2 min")

# ── ACTIVE EVENTS — shown first, processes immediately ────────────────────────
st.header("🔴 Active & Recent Events")

with st.spinner("Fetching headlines from RSS & NewsAPI..."):
    raw_news = fetch_raw_news(news_key)

cache = get_cache()
cached_count = sum(1 for (t,_,_) in raw_news if headline_hash(t) in cache)
new_needed   = len(raw_news) - cached_count

st.caption(
    f"{len(raw_news)} headlines fetched | "
    f"{cached_count} cached (show instantly) | "
    f"{new_needed} new → Gemini (7s apart, max 10/run)"
)

act_status = st.empty()
act_table  = st.empty()

# Show cached results immediately before processing new ones
cached_rows = []
for (title, ts, source) in raw_news:
    h = headline_hash(title)
    info = cache.get(h)
    if not info or not info.get("relevant"):
        continue
    weight = info.get("weight", 0)
    if weight < 5:
        continue
    topic = info.get("topic", "").strip() or title[:40]
    sentiment = info.get("sentiment", "Mixed")
    s_icon = "🟢" if sentiment == "Positive" else "🔴" if sentiment == "Negative" else "🟡"
    cached_rows.append({
        "Topic":               topic,
        "Timing":              ts,
        "Impact":              f"{info.get('impact_level','🟡 Moderate')} ({s_icon} {sentiment})",
        "Weight":              weight,
        "Logic Behind Impact": info.get("logic", "—"),
        "Source":              source,
    })

if cached_rows:
    act_table.table(get_styled_table(build_df(cached_rows)))
    act_status.info(f"Showing {len(cached_rows)} cached events. Processing {new_needed} new headlines...")

# Now process all headlines (cached ones skip instantly, new ones call Gemini)
process_headlines(raw_news, gemini_key, act_table, act_status)

# ── FUTURE EVENTS ─────────────────────────────────────────────────────────────
st.markdown("---")
st.header("📅 Upcoming Events — Next 30 Days")
fut_status = st.empty()
fut_table  = st.empty()

date_key = datetime.now(IST).strftime("%Y-%m-%d")
fut_status.info("📅 Fetching upcoming events from Gemini...")
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
    fut_status.warning(
        "⏳ Future events will appear on the next refresh. "
        "Gemini is processing — cached for 6h once loaded."
    )

# ── SENTIMENT GAUGE ───────────────────────────────────────────────────────────
st.markdown("---")
st.header("📊 Today's Market Intensity")
today_str = datetime.now(IST).strftime("%d %b")
hcache = get_cache()
today_weight = 0
for (title, ts, _) in raw_news:
    if today_str in ts:
        info = hcache.get(headline_hash(title), {})
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
st.sidebar.write("Fallback: gemini-2.0-flash → 1.5-flash-8b → 1.0-pro")
st.sidebar.write("Rate: 1 call per 7s = ~8/min (limit: 15/min)")
st.sidebar.write(f"Session cache: {len(get_cache())} headlines stored")

if st.sidebar.button("🗑️ Clear Cache & Re-analyse"):
    st.session_state["hcache"] = {}
    st.cache_data.clear()
    st.rerun()

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
st.sidebar.subheader("🔬 Health Check")
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
                st.sidebar.info(f"`{model}` rate limited")
        except Exception:
            continue
    if active_model:
        st.sidebar.success(f"✅ Active on `{active_model}`")
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
                st.sidebar.error(f"❌ {r.status_code}: {d.get('message', '')}")
        except Exception as e:
            st.sidebar.error(f"❌ {e}")

    ok, fail = 0, []
    for name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            if feed.entries: ok += 1
            else: fail.append(name)
        except Exception:
            fail.append(name)
    st.sidebar.success(f"✅ {ok}/{len(RSS_FEEDS)} RSS feeds live")
    if fail:
        st.sidebar.warning(f"⚠️ Failed: {', '.join(fail)}")
