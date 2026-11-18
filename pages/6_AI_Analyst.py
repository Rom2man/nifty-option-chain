import os
import time
from datetime import datetime, timezone, timedelta

import pandas as pd
import streamlit as st

IST = timezone(timedelta(hours=5, minutes=30))
LOG_FILE = "nifty_recording_log.csv"   # written by REC.py
MODEL = "claude-sonnet-5-5"
ROWS_TO_SEND = 45                       # recent snapshots sent to the AI

st.set_page_config(page_title="AI Analyst", page_icon="🤖", layout="wide")
st.title("🤖 AI Analyst — Recording Watcher")
st.caption("Reads the recording log written by the Recording page, summarises the trend, "
           "and asks Claude for an interpretation. Analysis only — not trading advice.")

SYSTEM = """You are an options-flow analyst for NSE Nifty intraday data.
You receive a time series of 1-minute snapshots plus pre-computed trend features.
Column meanings: Spot, Chng (vs prev close), PCR (OI put/call), Avijit OP and OI Tracker
(positive = bullish lean, negative = bearish lean), PE/CE IV sums, PE/CE COI Gr (OI growth %),
ITM PE / ITM CE (sum of %COI near ATM), Decision (PCR-based), Score/Conf (Decision 2 engine,
may be blank), Signal (Buy/Sell qty engine, may be blank).
Be concrete and concise. Reference the actual numbers and times. Do not invent data.
If indicators disagree, say so plainly rather than forcing a call. Respond in this format:

**Bias:** Bullish / Bearish / Neutral / Conflicted  (confidence: low/medium/high)
**What changed (last ~10 min):** 2-4 bullets
**Agreement / divergence:** which indicators agree, which contradict price
**Watch next:** 2-3 specific levels or conditions
**What would invalidate this view:** 1-2 bullets
"""


# ── Data loading ───────────────────────────────────────────────────────────
def load_today():
    if not os.path.exists(LOG_FILE):
        return pd.DataFrame()
    try:
        df = pd.read_csv(LOG_FILE, on_bad_lines="skip")
    except Exception:
        return pd.DataFrame()
    if df.empty or "Time" not in df.columns:
        return pd.DataFrame()
    # The log only stores HH:MM:SS, so detect a new trading day by time going backwards.
    t = pd.to_datetime(df["Time"], format="%H:%M:%S", errors="coerce")
    df = df[t.notna()].reset_index(drop=True)
    t = t[t.notna()].reset_index(drop=True)
    back = t < t.shift(1)
    if back.any():
        df = df.iloc[back[back].index[-1]:].reset_index(drop=True)
    return df


def trend(series, n=5):
    """Mean of the last n minus mean of the previous n."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 2 * n:
        return None
    return round(s.iloc[-n:].mean() - s.iloc[-2 * n:-n].mean(), 2)


def build_features(df):
    f = {}
    f["snapshots_today"] = len(df)
    f["first_time"] = df["Time"].iloc[0]
    f["last_time"] = df["Time"].iloc[-1]
    spot = pd.to_numeric(df["Spot"], errors="coerce")
    f["spot_last"] = round(float(spot.iloc[-1]), 2)
    f["spot_high"] = round(float(spot.max()), 2)
    f["spot_low"] = round(float(spot.min()), 2)
    f["spot_move_last10"] = round(float(spot.iloc[-1] - spot.iloc[max(0, len(spot) - 10)]), 2)
    for col in ["PCR", "Avijit OP", "OI Tracker", "PE COI Gr", "CE COI Gr", "ITM PE", "ITM CE"]:
        if col in df.columns:
            f[f"{col}_trend(last5-prev5)"] = trend(df[col])
    if "Decision" in df.columns:
        last10 = df["Decision"].tail(10).astype(str)
        f["decision_flips_last10"] = int((last10 != last10.shift(1)).sum() - 1)
        f["decision_mode_last10"] = last10.mode().iloc[0]
    return f


def local_alerts(df):
    """Cheap rule-based flags shown instantly, no API call."""
    out = []
    if len(df) < 4:
        return out
    last, prev = df.iloc[-1], df.iloc[-4]
    try:
        if last["Decision"] != prev["Decision"]:
            out.append(f"Decision changed: {prev['Decision']} → {last['Decision']}")
        if (last["Avijit OP"] >= 0) != (prev["Avijit OP"] >= 0):
            out.append("Avijit OP flipped sign in the last 3 snapshots")
        if (last["OI Tracker"] >= 0) != (prev["OI Tracker"] >= 0):
            out.append("OI Tracker flipped sign in the last 3 snapshots")
        up = last["Spot"] > prev["Spot"]
        if up and last["Avijit OP"] < 0 and last["OI Tracker"] < 0:
            out.append("Spot rising while Avijit OP and OI Tracker are both bearish (divergence)")
        if (not up) and last["Avijit OP"] > 0 and last["OI Tracker"] > 0:
            out.append("Spot falling while Avijit OP and OI Tracker are both bullish (divergence)")
    except Exception:
        pass
    return out


# ── Claude call ────────────────────────────────────────────────────────────
def get_api_key():
    try:
        k = st.secrets.get("ANTHROPIC_API_KEY")
        if k:
            return k
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_API_KEY", "")


def ask_claude(df, features, api_key, extra_q=""):
    import anthropic
    recent = df.tail(ROWS_TO_SEND).copy()
    prompt = (
        f"Current time (IST): {datetime.now(IST).strftime('%H:%M:%S')}\n\n"
        f"Pre-computed features:\n{features}\n\n"
        f"Last {len(recent)} snapshots (oldest first):\n{recent.to_csv(index=False)}\n"
    )
    if extra_q.strip():
        prompt += f"\nUser question: {extra_q.strip()}\n"
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=MODEL, max_tokens=900, system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if b.type == "text")


def market_open():
    n = datetime.now(IST)
    mins = n.hour * 60 + n.minute
    return n.weekday() < 5 and 9 * 60 + 15 <= mins <= 15 * 60 + 30


# ── State ──────────────────────────────────────────────────────────────────
for k, v in {"ai_log": [], "ai_last_time": 0.0, "ai_last_rows": 0, "ai_err": None}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Controls ───────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns([1.2, 1, 1.2, 1])
with c1:
    auto = st.toggle("🔄 Auto-analyze", value=False)
with c2:
    every = st.number_input("Every (min)", 1, 60, 5)
with c3:
    only_market = st.toggle("Only during market hours", value=True)
with c4:
    run_now = st.button("⚡ Analyze now", use_container_width=True)

question = st.text_input("Optional question for the AI (applies to the next analysis)",
                         placeholder="e.g. Is the PE writing at 24500 holding?")

api_key = get_api_key()
if not api_key:
    st.warning("No API key found. Add `ANTHROPIC_API_KEY` to `.streamlit/secrets.toml` "
               "or set it as an environment variable, then reload.")

df = load_today()
if df.empty:
    st.info("No recording data yet. Turn on **Record Data** on the Recording page and keep it open.")
    st.stop()

feats = build_features(df)

# ── Live view (no API cost) ───────────────────────────────────────────────
st.markdown(f"**{feats['snapshots_today']} snapshots today** · {feats['first_time']} → {feats['last_time']} · "
            f"Spot {feats['spot_last']:,.2f} (H {feats['spot_high']:,.2f} / L {feats['spot_low']:,.2f})")
alerts = local_alerts(df)
for a in alerts:
    st.warning(a)

with st.expander("Computed features sent to the AI"):
    st.json(feats)
with st.expander(f"Latest {min(15, len(df))} recorded rows"):
    st.dataframe(df.tail(15).iloc[::-1], hide_index=True, use_container_width=True)

# ── Decide whether to call the AI ─────────────────────────────────────────
due = (time.time() - st.session_state.ai_last_time) >= every * 60
has_new = len(df) > st.session_state.ai_last_rows
auto_ok = auto and due and has_new and (market_open() or not only_market)

if (run_now or auto_ok) and api_key:
    with st.spinner("Claude is analysing the recording table..."):
        try:
            text = ask_claude(df, feats, api_key, question)
            st.session_state.ai_log.insert(0, {
                "time": datetime.now(IST).strftime("%H:%M:%S"),
                "rows": len(df), "text": text,
            })
            st.session_state.ai_log = st.session_state.ai_log[:30]
            st.session_state.ai_err = None
        except Exception as e:
            st.session_state.ai_err = str(e)
        st.session_state.ai_last_time = time.time()
        st.session_state.ai_last_rows = len(df)

if st.session_state.ai_err:
    st.error(f"AI call failed: {st.session_state.ai_err}")

# ── Output ─────────────────────────────────────────────────────────────────
st.subheader("Latest analysis")
if st.session_state.ai_log:
    latest = st.session_state.ai_log[0]
    st.caption(f"Generated {latest['time']} IST from {latest['rows']} snapshots")
    st.markdown(latest["text"])
    if len(st.session_state.ai_log) > 1:
        with st.expander("Earlier analyses"):
            for item in st.session_state.ai_log[1:]:
                st.markdown(f"**{item['time']}** ({item['rows']} snapshots)")
                st.markdown(item["text"])
                st.divider()
else:
    st.info("No analysis yet — click **Analyze now** or enable **Auto-analyze**.")

if auto:
    nxt = max(0, int(every * 60 - (time.time() - st.session_state.ai_last_time)))
    st.caption(f"⏱ Next auto-analysis in about {nxt}s (checks for new rows every 30s)")
    time.sleep(30)
    st.rerun()
