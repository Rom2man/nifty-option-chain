import streamlit as st
import requests
import pandas as pd
import time
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="AI Card | Nifty Option Chain", page_icon="🤖", layout="wide")

st.markdown("""
<style>
    .cookie-ok {
        background:#E8F5E9; padding:5px 12px; border-radius:6px;
        color:#2E7D32; font-weight:700; display:inline-block; font-size:13px;
    }
    .ai-card {
        border:2px solid #1565C0; border-radius:14px; overflow:hidden;
        font-family:'Segoe UI', sans-serif; margin-top:10px; box-shadow:0 4px 16px rgba(0,0,0,0.08);
    }
    .ai-header {
        background:linear-gradient(90deg,#0D47A1,#1976D2); color:white;
        padding:14px 20px; font-size:19px; font-weight:800; letter-spacing:0.5px;
    }
    .ai-reco {
        padding:16px 20px; font-size:22px; font-weight:800; color:white; text-align:center;
    }
    .ai-body { padding:16px 22px; background:#FAFCFF; }
    .ai-row {
        display:flex; justify-content:space-between; padding:6px 0;
        border-bottom:1px dashed #E0E0E0; font-size:15px;
    }
    .ai-row:last-child { border-bottom:none; }
    .ai-label { color:#555; font-weight:600; }
    .ai-value { font-weight:800; color:#0D47A1; }
    .ai-section-title {
        background:#EEF3FB; padding:8px 22px; font-weight:800; font-size:14px;
        color:#0D47A1; border-top:1px solid #D0DCEE; border-bottom:1px solid #D0DCEE;
    }
    .ev-table { width:auto; border-collapse:collapse; font-size:14px; }
    .ev-table td { padding:7px 22px; border-bottom:1px solid #F0F0F0; }
    .ev-table td.ev-score { text-align:right; font-weight:800; padding-right:22px; }
    .ev-pos { color:#2E7D32; }
    .ev-neg { color:#C62828; }
    .prob-wrap { padding:16px 22px 20px 22px; }
    .prob-row { display:flex; align-items:center; margin-bottom:10px; font-size:14px; font-weight:700; }
    .prob-label { width:auto; color:#333; }
    .prob-bar-bg { flex:1; background:#ECEFF1; border-radius:6px; height:18px; overflow:hidden; margin:0 10px; }
    .prob-bar-fill { height:100%; border-radius:6px; }
    .stars { color:#F9A825; font-size:18px; letter-spacing:2px; }
</style>
""", unsafe_allow_html=True)

st.title("🤖 AI Decision Engine")
st.caption("A composite, evidence-weighted read of the live option chain. Fully self-contained — fetches its own NSE data independently of other pages.")

for k, v in {
    "ai_cookie": "", "ai_cookie_time": 0, "ai_raw_data": None, "ai_last_fetch": 0,
    "ai_open_price": 0, "ai_open_spot": 0, "ai_expiry_dates": [],
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

COOKIE_REFRESH = 300
DATA_REFRESH = 60

# ── Self-contained helpers (duplicated so this page works standalone) ──────
def mround(val, multiple): return math.floor(val / multiple + 0.5) * multiple

def fetch_fresh_cookie():
    try:
        s = requests.Session()
        h = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Encoding":"gzip, deflate","Accept-Language":"en-US,en;q=0.9","Connection":"keep-alive"}
        s.get("https://www.nseindia.com", headers=h, timeout=15); time.sleep(1.5)
        h["Referer"] = "https://www.nseindia.com/"
        s.get("https://www.nseindia.com/option-chain", headers=h, timeout=15); time.sleep(1)
        ck = "; ".join([f"{k}={v}" for k, v in s.cookies.items()])
        return (ck, None) if ck else (None, "No cookies")
    except Exception as e:
        return None, str(e)

def filter_future_expiries(dates):
    today = datetime.now(IST).date()
    valid = []
    for d in dates:
        try:
            if datetime.strptime(d, "%d-%b-%Y").date() >= today: valid.append(d)
        except: valid.append(d)
    return valid

def fetch_expiry_dates(symbol, cookie):
    url = f"https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol={symbol}"
    h = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0","Accept":"application/json, text/plain, */*","Accept-Encoding":"gzip, deflate","Accept-Language":"en-US,en;q=0.9","Referer":"https://www.nseindia.com/option-chain","Cookie":cookie,"X-Requested-With":"XMLHttpRequest","Connection":"keep-alive"}
    try:
        r = requests.get(url, headers=h, timeout=15)
        if r.status_code == 200: return filter_future_expiries(r.json().get("records", {}).get("expiryDates", []))
        return []
    except: return []

def fetch_option_chain(symbol, expiry, cookie):
    url = f"https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol={symbol}&expiry={expiry}"
    h = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0","Accept":"application/json, text/plain, */*","Accept-Encoding":"gzip, deflate","Accept-Language":"en-US,en;q=0.9","Referer":"https://www.nseindia.com/option-chain","Cookie":cookie,"X-Requested-With":"XMLHttpRequest","Connection":"keep-alive"}
    try:
        r = requests.get(url, headers=h, timeout=15)
        return (r.json(), None) if r.status_code == 200 else (None, f"Status {r.status_code}")
    except Exception as e:
        return None, str(e)

def fetch_nifty_open(cookie):
    h = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0","Accept":"application/json, text/plain, */*","Accept-Encoding":"gzip, deflate","Accept-Language":"en-US,en;q=0.9","Referer":"https://www.nseindia.com/","Cookie":cookie,"X-Requested-With":"XMLHttpRequest","Connection":"keep-alive"}
    try:
        r = requests.get("https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050", headers=h, timeout=15)
        if r.status_code == 200:
            for row in r.json().get("data", []):
                name = row.get("index", "") or row.get("indexSymbol", "")
                if "NIFTY 50" in name.upper() and "BANK" not in name.upper():
                    op = float(row.get("open", 0) or 0); pc = float(row.get("previousClose", 0) or 0)
                    if op > 0 and pc > 0: return op, pc
    except: pass
    return 0, 0

def parse_data(json_data):
    rec = json_data.get("records", {}); spot = rec.get("underlyingValue", 0); rows = []
    for item in rec.get("data", []):
        ce = item.get("CE", {}); pe = item.get("PE", {})
        rows.append({"STRIKE": item.get("strikePrice", 0),
            "CE_OI": ce.get("openInterest", 0), "CE_COI": ce.get("changeinOpenInterest", 0),
            "CE_PCOI": ce.get("pchangeinOpenInterest", 0), "CE_VOL": ce.get("totalTradedVolume", 0),
            "CE_IV": ce.get("impliedVolatility", 0), "CE_LTP": ce.get("lastPrice", 0),
            "PE_OI": pe.get("openInterest", 0), "PE_COI": pe.get("changeinOpenInterest", 0),
            "PE_PCOI": pe.get("pchangeinOpenInterest", 0), "PE_VOL": pe.get("totalTradedVolume", 0),
            "PE_IV": pe.get("impliedVolatility", 0), "PE_LTP": pe.get("lastPrice", 0)})
    return pd.DataFrame(rows), spot

# ── Controls ─────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns([1, 1.5, 1, 1])
with c1: symbol = st.selectbox("Symbol", ["NIFTY", "BANKNIFTY", "FINNIFTY"], key="ai_symbol")
with c2:
    expiry_list = st.session_state.ai_expiry_dates if st.session_state.ai_expiry_dates else ["07-Jul-2026"]
    expiry = st.selectbox("Expiry Date", expiry_list, key="ai_expiry")
with c3: auto_refresh = st.toggle("🔄 Auto Refresh", value=True, key="ai_auto_refresh")
with c4: manual_btn = st.button("⚡ Refresh Now", use_container_width=True, key="ai_manual_btn")

age = int(time.time() - st.session_state.ai_cookie_time)
if st.session_state.ai_cookie: st.markdown(f'<span class="cookie-ok">🍪 Cookie OK — age: {age}s</span>', unsafe_allow_html=True)
else: st.markdown('<span style="color:red;font-weight:bold">🍪 Fetching cookie...</span>', unsafe_allow_html=True)

if age > COOKIE_REFRESH or not st.session_state.ai_cookie:
    with st.spinner("🍪 Getting fresh cookie..."):
        ck, _ = fetch_fresh_cookie()
        if ck:
            st.session_state.ai_cookie = ck; st.session_state.ai_cookie_time = time.time()
            dates = fetch_expiry_dates(symbol, ck)
            if dates: st.session_state.ai_expiry_dates = dates

data_age = int(time.time() - st.session_state.ai_last_fetch)
should_fetch = manual_btn or (auto_refresh and data_age >= DATA_REFRESH) or st.session_state.ai_raw_data is None

fetch_error = None
if should_fetch and st.session_state.ai_cookie:
    data, err = fetch_option_chain(symbol, expiry, st.session_state.ai_cookie)
    if data:
        st.session_state.ai_raw_data = data; st.session_state.ai_last_fetch = time.time()
        _, spot0 = parse_data(data)
        if st.session_state.ai_open_price == 0:
            day_open, _ = fetch_nifty_open(st.session_state.ai_cookie)
            base = day_open if day_open > 0 else spot0
            st.session_state.ai_open_spot = base
            st.session_state.ai_open_price = mround(base, 50)
        dates = data.get("records", {}).get("expiryDates", [])
        if dates: st.session_state.ai_expiry_dates = filter_future_expiries(dates)
    else:
        fetch_error = err

if fetch_error:
    st.error(f"⚠️ Data fetch failed: {fetch_error}. Try 'Refresh Now' — NSE may be rate-limiting this IP.")

# ── Build the card ─────────────────────────────────────────────────────
if st.session_state.ai_raw_data:
    df, spot = parse_data(st.session_state.ai_raw_data)
    pivot = st.session_state.ai_open_price if st.session_state.ai_open_price > 0 else mround(spot, 50)
    lo, hi = pivot - 250, pivot + 250
    df_f = df[(df["STRIKE"] >= lo) & (df["STRIKE"] <= hi)].copy().reset_index(drop=True)

    if df_f.empty:
        st.warning("No data in ±250 range.")
    else:
        tot = {k: df_f[k].sum() for k in ["CE_OI", "CE_COI", "CE_VOL", "PE_OI", "PE_COI", "PE_VOL"]}

        # ── Core ratios ──────────────────────────────────────────────────
        oi_pcr = tot["PE_OI"] / tot["CE_OI"] if tot["CE_OI"] else 0
        ce_coi_abs = df_f["CE_COI"].abs().sum(); pe_coi_abs = df_f["PE_COI"].abs().sum()
        coi_pcr = pe_coi_abs / ce_coi_abs if ce_coi_abs else 0
        ce_iv_avg = df_f["CE_IV"].mean() if len(df_f) else 0
        pe_iv_avg = df_f["PE_IV"].mean() if len(df_f) else 0

        # ITM build-up (same windowing as Detailed Calculations / REC)
        all_s = sorted(df_f["STRIKE"].unique())
        dc_atm = mround(pivot, 50)
        try: dc_atm_idx = all_s.index(dc_atm)
        except: dc_atm_idx = next((i for i, s in enumerate(all_s) if s >= dc_atm), len(all_s) // 2)
        itm_pe_strikes = all_s[dc_atm_idx: dc_atm_idx + 6]
        itm_ce_strikes = all_s[max(0, dc_atm_idx - 5): dc_atm_idx + 1]
        itm_pe_pct = df_f[df_f["STRIKE"].isin(itm_pe_strikes)]["PE_PCOI"].sum()
        itm_ce_pct = df_f[df_f["STRIKE"].isin(itm_ce_strikes)]["CE_PCOI"].sum()

        # Strongest support / resistance strikes (top-1 by OI, same approach as Decision 2)
        res_row = df_f.loc[df_f["CE_OI"].idxmax()]
        sup_row = df_f.loc[df_f["PE_OI"].idxmax()]
        resistance_strike, resistance_coi = res_row["STRIKE"], res_row["CE_COI"]
        support_strike, support_coi = sup_row["STRIKE"], sup_row["PE_COI"]

        turnover = (tot["CE_VOL"] + tot["PE_VOL"]) / (tot["CE_OI"] + tot["PE_OI"]) if (tot["CE_OI"] + tot["PE_OI"]) else 0

        # ── Evidence checklist (points are signed: + bullish, − bearish) ──
        evidence = []
        if oi_pcr >= 1.2: evidence.append(("PCR Bullish", 10, True))
        elif oi_pcr <= 0.8: evidence.append(("PCR Bearish", -10, True))
        else: evidence.append(("PCR Neutral", 0, False))

        if coi_pcr >= 1.2: evidence.append(("COI Shift Bullish", 15, True))
        elif coi_pcr <= 0.8: evidence.append(("COI Shift Bearish", -15, True))
        else: evidence.append(("COI Shift Neutral", 0, False))

        if itm_ce_pct > itm_pe_pct and itm_ce_pct > 0: evidence.append(("ITM Call Build-up", 15, True))
        elif itm_pe_pct > itm_ce_pct and itm_pe_pct > 0: evidence.append(("ITM Put Build-up", -15, True))
        else: evidence.append(("No Clear ITM Build-up", 0, False))

        if resistance_coi < 0: evidence.append(("OI Resistance Weakening", 10, True))
        elif resistance_coi > 0: evidence.append(("OI Resistance Strengthening", -10, True))
        else: evidence.append(("Resistance Flat", 0, False))

        if support_coi > 0: evidence.append(("Support Strength Increasing", 12, True))
        elif support_coi < 0: evidence.append(("Support Weakening", -12, True))
        else: evidence.append(("Support Flat", 0, False))

        iv_diff_pct = ((ce_iv_avg - pe_iv_avg) / pe_iv_avg * 100) if pe_iv_avg else 0
        if abs(iv_diff_pct) <= 8: evidence.append(("IV Favourable", 6, True))
        elif ce_iv_avg > pe_iv_avg: evidence.append(("IV Skewed vs Calls", -6, True))
        else: evidence.append(("IV Skewed vs Puts", 6, True))

        if turnover >= 0.15: evidence.append(("Volume Expansion", 12 if (oi_pcr + coi_pcr) >= 2 else -12, True))
        else: evidence.append(("Volume Muted", 0, False))

        oi_sign = 1 if oi_pcr >= 1 else -1
        coi_sign = 1 if coi_pcr >= 1 else -1
        if oi_sign == coi_sign:
            label = "No Bearish Divergence" if oi_sign > 0 else "No Bullish Divergence"
            evidence.append((label, 10 * oi_sign, True))
        else:
            evidence.append(("Divergence Present", 0, False))

        total_score = sum(pts for _, pts, active in evidence if active)

        # ── Recommendation ─────────────────────────────────────────────
        if total_score >= 50:   reco, reco_color = "🟢 STRONG BUY CE", "#1B5E20"
        elif total_score >= 20: reco, reco_color = "🟢 BUY CE", "#2E7D32"
        elif total_score <= -50: reco, reco_color = "🔴 STRONG BUY PE", "#B71C1C"
        elif total_score <= -20: reco, reco_color = "🔴 BUY PE", "#C62828"
        else:                    reco, reco_color = "🟡 NEUTRAL / WAIT", "#F9A825"

        confidence = min(99, max(1, round(abs(total_score))))
        stars_n = 5 if confidence >= 85 else 4 if confidence >= 70 else 3 if confidence >= 55 else 2 if confidence >= 40 else 1
        stars_html = "★" * stars_n + "☆" * (5 - stars_n)

        # ── Expected move — IV-implied, 30-minute horizon ───────────────
        avg_iv = (ce_iv_avg + pe_iv_avg) / 2
        move_30 = spot * (avg_iv / 100) * math.sqrt(30 / (365 * 24 * 60)) if avg_iv else 0
        move_lo, move_hi = round(move_30), round(move_30 * 1.5)

        risk_level = "LOW" if (confidence >= 70 and avg_iv < 15) else "HIGH" if (confidence < 40 or avg_iv >= 20) else "MEDIUM"

        # ── Entry / SL / Target (direction-aware, tied to real support/resistance) ──
        if total_score > 20:
            entry_lo = mround(spot, 10); entry_hi = mround(spot + move_lo * 0.15, 10)
            stop_loss = mround(support_strike - 20, 10)
            target1 = int(resistance_strike)
            target2 = mround(resistance_strike + move_hi * 0.4, 10)
            expected_move_str = f"+{move_lo} to +{move_hi} pts"
        elif total_score < -20:
            entry_hi = mround(spot, 10); entry_lo = mround(spot - move_lo * 0.15, 10)
            stop_loss = mround(resistance_strike + 20, 10)
            target1 = int(support_strike)
            target2 = mround(support_strike - move_hi * 0.4, 10)
            expected_move_str = f"-{move_lo} to -{move_hi} pts"
        else:
            entry_lo, entry_hi = mround(spot - 15, 10), mround(spot + 15, 10)
            stop_loss = mround(spot - 40, 10)
            target1, target2 = mround(spot + 40, 10), mround(spot - 40, 10)
            expected_move_str = f"±{move_lo} pts (range-bound)"

        # ── Probability split ───────────────────────────────────────────
        strength = abs(total_score)
        if total_score >= 0:
            bullish = min(96, 50 + strength * 0.6)
            bearish = max(1, round((100 - bullish) * 0.2))
            sideways = 100 - bullish - bearish
        else:
            bearish = min(96, 50 + strength * 0.6)
            bullish = max(1, round((100 - bearish) * 0.2))
            sideways = 100 - bearish - bullish
        bullish, bearish, sideways = round(bullish), round(bearish), round(sideways)

        last = int(time.time() - st.session_state.ai_last_fetch)

        # ── Render card ──────────────────────────────────────────────────
        html = []
        html.append('<div class="ai-card">')
        html.append('<div class="ai-header">🤖 AI DECISION ENGINE v3.0</div>')
        html.append(f'<div class="ai-reco" style="background:{reco_color}">{reco}</div>')
        html.append('<div class="ai-body">')
        rows = [
            ("Confidence", f"{confidence}%"),
            ("Trade Quality", f'<span class="stars">{stars_html}</span>'),
            ("Expected Move", expected_move_str),
            ("Risk Level", risk_level),
            ("Entry Zone", f"{entry_lo:,} – {entry_hi:,}"),
            ("Stop Loss", f"{stop_loss:,}"),
            ("Target", f"{target1:,} / {target2:,}"),
            ("Time Valid", "Next 30 minutes"),
            ("Spot / Updated", f"₹{spot:,.2f}  ·  {last}s ago"),
        ]
        for label, val in rows:
            html.append(f'<div class="ai-row"><span class="ai-label">{label}</span><span class="ai-value">{val}</span></div>')
        html.append('</div>')

        html.append('<div class="ai-section-title">Evidence &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Score</div>')
        html.append('<table class="ev-table">')
        for label, pts, active in evidence:
            mark = "✔" if active else "✖"
            cls = "ev-pos" if pts > 0 else ("ev-neg" if pts < 0 else "")
            sign = f"{pts:+d}" if active else "0"
            html.append(f'<tr><td>{mark} {label}</td><td class="ev-score {cls}">{sign}</td></tr>')
        html.append('</table>')

        html.append('<div class="ai-section-title">Probability</div>')
        html.append('<div class="prob-wrap">')
        html.append(f'<div class="prob-row"><span class="prob-label">Bullish</span><div class="prob-bar-bg"><div class="prob-bar-fill" style="width:{bullish}%;background:#2E7D32"></div></div><span>{bullish}%</span></div>')
        html.append(f'<div class="prob-row"><span class="prob-label">Sideways</span><div class="prob-bar-bg"><div class="prob-bar-fill" style="width:{sideways}%;background:#F9A825"></div></div><span>{sideways}%</span></div>')
        html.append(f'<div class="prob-row"><span class="prob-label">Bearish</span><div class="prob-bar-bg"><div class="prob-bar-fill" style="width:{bearish}%;background:#C62828"></div></div><span>{bearish}%</span></div>')
        html.append('</div>')
        html.append('</div>')

        st.markdown("".join(html), unsafe_allow_html=True)

        with st.expander("ℹ️ Methodology — how these numbers are derived"):
            st.markdown("""
- **PCR / COI Shift**: same ±250-strike PE/CE OI and |ΔOI| ratios used across the other pages.
- **ITM Build-up**: same 6-strike ITM windowing as the Detailed Calculations / Recording pages.
- **Resistance/Support**: single strongest CE-OI / PE-OI strike in range (same method as Decision 2's Top Support & Resistance).
- **IV Favourable**: flags when CE vs PE average IV are within 8% of each other (no strong skew).
- **Volume Expansion**: total traded volume ÷ total OI ("turnover") ≥ 0.15.
- **Expected Move**: IV-implied move for a 30-minute horizon — `spot × (avg IV/100) × √(30min/1yr)`, shown as a 1×–1.5× range.
- **Entry/SL/Target**: anchored to the actual strongest support/resistance strikes found above, not fixed offsets.
- **Confidence/Probability**: derived from the signed sum of active evidence points (max ±90ish) — this weighting is a reasonable default, not a backtested model. Tune the point values in the code if you want to weight factors differently.
            """)

    if auto_refresh:
        nxt = max(0, DATA_REFRESH - int(time.time() - st.session_state.ai_last_fetch))
        st.caption(f"⏱ Next auto-fetch in {nxt}s")
        time.sleep(nxt)
        st.rerun()

else:
    st.info("⏳ Loading data...")
    time.sleep(2)
    st.rerun()
