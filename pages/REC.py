import streamlit as st
import requests
import pandas as pd
import time
import math
import os
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

st.set_page_config(page_title="Recording | Nifty Option Chain", page_icon="⏺️", layout="wide")

st.markdown("""
<style>
    .spot-bar {
        background:linear-gradient(90deg,#1565C0,#1976D2);
        padding:10px 18px; border-radius:10px; color:white;
        font-size:15px; font-weight:bold; margin-bottom:10px;
    }
    .cookie-ok {
        background:#E8F5E9; padding:5px 12px; border-radius:6px;
        color:#2E7D32; font-weight:700; display:inline-block; font-size:13px;
    }
    .rec-table { width:auto; border-collapse:collapse; font-size:95px; margin-top: 19px; table-layout:fixed; }
    .rec-table th { background:#1565C0; color:white; padding:3px 2px; text-align:center; font-size:15px; font-weight:700; border:1px solid #1976D2; line-height:1.15; position:sticky; top:0; overflow:hidden; }
    .rec-table td { padding:2px 3px; text-align:center; border:1px solid #E0E0E0; font-size:19px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .rec-table tr:nth-child(even) td { background:#F8F9FA; }
    .rec-table tr:first-child td { background:#E3F2FD !important; font-weight:800 !important; }
    .pos { color:#2E7D32; font-weight:800; }
    .neg { color:#C62828; font-weight:800; }
    .rec-status-on {
        background:#E8F5E9; padding:5px 12px; border-radius:6px;
        color:#2E7D32; font-weight:700; display:inline-block; font-size:13px;
    }
    .rec-status-off {
        background:#FFEBEE; padding:5px 12px; border-radius:6px;
        color:#C62828; font-weight:700; display:inline-block; font-size:13px;
    }
</style>
""", unsafe_allow_html=True)

st.title("⏺️ Recording & History")
st.caption("This page fetches NSE data and records a time-series snapshot independently of the main Option Chain page. Keep this tab/page open in your browser for recording to keep running.")

# ── Local CSV log so history survives a page reload / app restart ──────────
LOG_FILE = "nifty_recording_log.csv"

# ── Session State (namespaced with rec_ to avoid clashing with app.py) ─────
for k, v in {
    "rec_cookie": "", "rec_cookie_time": 0, "rec_raw_data": None, "rec_last_fetch": 0,
    "rec_open_price": 0, "rec_open_spot": 0, "rec_prev_close": 0,
    "rec_expiry_dates": [], "rec_history": [], "rec_oi_multiplier": 50,
    "rec_is_recording": True,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Load any previously saved history from disk on first run of this session
if not st.session_state.rec_history and os.path.exists(LOG_FILE):
    try:
        _df_log = pd.read_csv(LOG_FILE)
        st.session_state.rec_history = _df_log.to_dict("records")
    except Exception:
        pass

COOKIE_REFRESH = 300
DATA_REFRESH = 60

# ── Helpers (self-contained — duplicated from app.py so this page works standalone) ──
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
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/",
        "Cookie": cookie,
        "X-Requested-With": "XMLHttpRequest",
        "Connection": "keep-alive",
    }
    try:
        r = requests.get("https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050", headers=h, timeout=15)
        if r.status_code == 200:
            for row in r.json().get("data", []):
                name = row.get("index", "") or row.get("indexSymbol", "")
                if "NIFTY 50" in name.upper() and "BANK" not in name.upper():
                    op = float(row.get("open", 0) or 0)
                    pc = float(row.get("previousClose", 0) or 0)
                    if op > 0 and pc > 0: return op, pc
    except: pass
    try:
        r2 = requests.get("https://www.nseindia.com/api/allIndices", headers=h, timeout=15)
        if r2.status_code == 200:
            for row in r2.json().get("data", []):
                name = row.get("index", "") or row.get("indexSymbol", "")
                if "NIFTY 50" in name.upper() and "BANK" not in name.upper():
                    op = float(row.get("open", 0) or 0)
                    pc = float(row.get("previousClose", 0) or 0)
                    if op > 0 and pc > 0: return op, pc
    except: pass
    try:
        r3 = requests.get("https://www.nseindia.com/api/index-tracker?indexSymbol=NIFTY%2050", headers=h, timeout=15)
        if r3.status_code == 200:
            d = r3.json()
            op = float(d.get("open", 0) or d.get("opn", 0) or d.get("Open", 0) or 0)
            pc = float(d.get("previousClose", 0) or d.get("prevClose", 0) or d.get("PrevClose", 0) or 0)
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
            "CE_BUY": ce.get("totalBuyQuantity", 0), "CE_SELL": ce.get("totalSellQuantity", 0),
            "PE_OI": pe.get("openInterest", 0), "PE_COI": pe.get("changeinOpenInterest", 0),
            "PE_PCOI": pe.get("pchangeinOpenInterest", 0), "PE_VOL": pe.get("totalTradedVolume", 0),
            "PE_IV": pe.get("impliedVolatility", 0), "PE_LTP": pe.get("lastPrice", 0),
            "PE_BUY": pe.get("totalBuyQuantity", 0), "PE_SELL": pe.get("totalSellQuantity", 0)})
    return pd.DataFrame(rows), spot

def compute_dec_signal(pcr, ce_bs, pe_bs):
    """Exact replica of Decision.py's compute_signal — PCR + CE/PE Buy-Sell ratio composite."""
    score = 0
    if   pcr >= 1.5:  score += 2
    elif pcr >= 1.2:  score += 1
    elif pcr <= 0.5:  score -= 2
    elif pcr <= 0.8:  score -= 1
    if ce_bs >= 1.1:  score += 1
    elif ce_bs <= 0.9: score -= 1
    if pe_bs >= 1.1:  score -= 1
    elif pe_bs <= 0.9: score += 1
    if   score >= 3:  return "⬆️ Strong Buy CE (Bullish)"
    elif score >= 1:  return "↗️ Buy CE (Mild Bullish)"
    elif score <= -3: return "⬇️ Strong Buy PE (Bearish)"
    elif score <= -1: return "↘️ Buy PE (Mild Bearish)"
    else:             return "↔️ Neutral"

def compute_dec2_score(df_f, tot, pe_iv_sum, ce_iv_sum, oi_pcr, spot, pivot):
    """Exact replica of 4_Decision_2.py's scoring engine."""
    vol_pcr = tot["PE_VOL"] / tot["CE_VOL"] if tot["CE_VOL"] else 0
    ce_coi_abs = df_f["CE_COI"].abs().sum()
    pe_coi_abs = df_f["PE_COI"].abs().sum()
    coi_pcr = pe_coi_abs / ce_coi_abs if ce_coi_abs else 0

    score = 0
    if   oi_pcr  > 1.2: score += 20
    elif oi_pcr  < 0.8: score -= 20
    if   coi_pcr > 1.2: score += 25
    elif coi_pcr < 0.8: score -= 25
    if   vol_pcr > 1.0: score += 10
    elif vol_pcr < 0.9: score -= 10
    score += 10 if ce_iv_sum > pe_iv_sum else -10

    strong_ce = (df_f["CE_VOL"] > df_f["CE_COI"].abs() * 1.5).sum()
    strong_pe = (df_f["PE_VOL"] > df_f["PE_COI"].abs() * 1.5).sum()
    if   strong_ce > strong_pe: score += 10
    elif strong_pe > strong_ce: score -= 10
    score += 5 if spot > pivot else -5

    if   score >=  50: signal = "🚀 STRONG BUY CE"
    elif score >=  25: signal = "🟢 BUY CE"
    elif score <= -50: signal = "🚨 STRONG BUY PE"
    elif score <= -25: signal = "🔴 BUY PE"
    else:               signal = "🟡 NEUTRAL"

    confidence = min(100, round(abs(score) / 80 * 100, 1))
    return score, confidence, signal

def excel_growth(oi, coi):
    try:
        oi = float(oi); coi = float(coi); diff = oi - coi
        if diff == 0: return 0.0
        return round(((oi / diff) - 1.0) * (1.0 if diff > 0 else -1.0) * 100.0, 4)
    except: return 0.0

def fmt_oi(v):
    try:
        v = float(v)
        if v >= 10_000_000: return f"{v/10_000_000:.2f}Cr"
        if v >= 100_000: return f"{v/100_000:.2f}L"
        return f"{int(v):,}"
    except: return str(v)

def get_decision(pcr_val):
    if pcr_val >= 1.5:    return "Strong Buy CE"
    elif pcr_val >= 1.2:  return "Buy CE"
    elif pcr_val <= 0.5:  return "Super Strong Buy PE"
    elif pcr_val <= 0.65: return "Strong Buy PE"
    elif pcr_val <= 0.8:  return "Buy PE"
    else:                 return "Neutral"

# ── Controls ─────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns([1, 1.5, 1, 1, 1])
with c1: symbol = st.selectbox("Symbol", ["NIFTY", "BANKNIFTY", "FINNIFTY"], key="rec_symbol")
with c2:
    expiry_list = st.session_state.rec_expiry_dates if st.session_state.rec_expiry_dates else ["07-Jul-2026"]
    expiry = st.selectbox("Expiry Date", expiry_list, key="rec_expiry")
with c3: auto_refresh = st.toggle("🔄 Auto Fetch", value=True, key="rec_auto_refresh")
with c4: st.session_state.rec_is_recording = st.toggle("⏺️ Record Data", value=st.session_state.rec_is_recording)
with c5: manual_btn = st.button("⚡ Refresh Now", use_container_width=True, key="rec_manual_btn")

cs1, cs2, cs3 = st.columns([2, 1, 1])
with cs1:
    age = int(time.time() - st.session_state.rec_cookie_time)
    if st.session_state.rec_cookie: st.markdown(f'<span class="cookie-ok">🍪 Cookie OK — age: {age}s</span>', unsafe_allow_html=True)
    else: st.markdown('<span style="color:red;font-weight:bold">🍪 Fetching cookie...</span>', unsafe_allow_html=True)
with cs2: force_cookie = st.button("🔑 Refresh Cookie", use_container_width=True, key="rec_force_cookie")
with cs3:
    mult = st.number_input("OI Tracker Multiplier", min_value=1, max_value=1000, value=st.session_state.rec_oi_multiplier, step=1, key="rec_mult")
    st.session_state.rec_oi_multiplier = mult

status_html = '<span class="rec-status-on">⏺️ Recording is ON — capturing a snapshot every refresh</span>' if st.session_state.rec_is_recording else '<span class="rec-status-off">⏸️ Recording is OFF — toggle "Record Data" above to resume</span>'
st.markdown(status_html, unsafe_allow_html=True)

# ── Cookie & Fetch Logic ────────────────────────────────────────────────
if age > COOKIE_REFRESH or not st.session_state.rec_cookie or force_cookie:
    with st.spinner("🍪 Getting fresh cookie..."):
        ck, _ = fetch_fresh_cookie()
        if ck:
            st.session_state.rec_cookie = ck; st.session_state.rec_cookie_time = time.time()
            dates = fetch_expiry_dates(symbol, ck)
            if dates: st.session_state.rec_expiry_dates = dates

data_age = int(time.time() - st.session_state.rec_last_fetch)
should_fetch = manual_btn or (auto_refresh and data_age >= DATA_REFRESH) or st.session_state.rec_raw_data is None

fetch_error = None
if should_fetch and st.session_state.rec_cookie:
    data, err = fetch_option_chain(symbol, expiry, st.session_state.rec_cookie)
    if data:
        st.session_state.rec_raw_data = data; st.session_state.rec_last_fetch = time.time()
        _, spot = parse_data(data)
        if st.session_state.rec_open_price == 0:
            day_open, day_prev_close = fetch_nifty_open(st.session_state.rec_cookie)
            if day_open > 0:
                st.session_state.rec_open_spot = day_open
                st.session_state.rec_open_price = mround(day_open, 50)
            else:
                st.session_state.rec_open_spot = spot
                st.session_state.rec_open_price = mround(spot, 50)
            if st.session_state.rec_prev_close == 0 and day_prev_close > 0:
                st.session_state.rec_prev_close = day_prev_close
        dates = data.get("records", {}).get("expiryDates", [])
        if dates: st.session_state.rec_expiry_dates = filter_future_expiries(dates)
    else:
        fetch_error = err

if fetch_error:
    st.error(f"⚠️ Data fetch failed: {fetch_error}. NSE may be rate-limiting this server's IP — try 'Refresh Cookie', or check the Oracle Cloud / deployment guidance if this persists.")

# ── Display ──────────────────────────────────────────────────────────────
if st.session_state.rec_raw_data:
    df, spot = parse_data(st.session_state.rec_raw_data)
    last = int(time.time() - st.session_state.rec_last_fetch)
    atm_strike = mround(spot, 50)
    open_strike = st.session_state.rec_open_price if st.session_state.rec_open_price > 0 else atm_strike
    open_actual = st.session_state.rec_open_spot

    st.markdown(f'''<div class="spot-bar">
        📊 LTP: <b>₹{spot:,.2f}</b> &nbsp;|&nbsp;
        Day Open: <b>₹{open_actual:,.2f}</b> &nbsp;|&nbsp;
        Pivot (Rounded): <b>₹{open_strike:,}</b> &nbsp;|&nbsp;
        ATM: <b>₹{atm_strike:,}</b> &nbsp;|&nbsp;
        {symbol} &nbsp;|&nbsp; Expiry: {expiry} &nbsp;|&nbsp;
        Updated: {last}s ago
    </div>''', unsafe_allow_html=True)

    lo = open_strike - 250; hi = open_strike + 250
    df_f = df[(df["STRIKE"] >= lo) & (df["STRIKE"] <= hi)].copy().reset_index(drop=True)

    if df_f.empty:
        st.warning("No data in ±250 range.")
    else:
        tot = {k: df_f[k].sum() for k in ["CE_OI", "CE_COI", "CE_VOL", "PE_OI", "PE_COI", "PE_VOL"]}
        pcr = tot["PE_OI"] / tot["CE_OI"] if tot["CE_OI"] else 0

        prev_close = st.session_state.rec_prev_close
        oi_mult = st.session_state.rec_oi_multiplier

        chng = round(spot - prev_close, 2) if prev_close > 0 else 0

        df_f["PE_COV"] = df_f.apply(lambda r: r["PE_COI"] / r["PE_VOL"] if r["PE_VOL"] else 0, axis=1)
        df_f["CE_COV"] = df_f.apply(lambda r: r["CE_COI"] / r["CE_VOL"] if r["CE_VOL"] else 0, axis=1)
        df_f["PE_GR"] = df_f.apply(lambda r: excel_growth(r["PE_OI"], r["PE_COI"]), axis=1)
        df_f["CE_GR"] = df_f.apply(lambda r: excel_growth(r["CE_OI"], r["CE_COI"]), axis=1)

        avijit_op = round((df_f["PE_COV"].sum() - df_f["CE_COV"].sum()) * 65, 2)
        oi_tracker = round(((tot["PE_OI"] - tot["CE_OI"]) / 100000) * oi_mult, 2)
        pe_iv_sum = round(df_f["PE_IV"].sum(), 2)
        ce_iv_sum = round(df_f["CE_IV"].sum(), 2)
        pe_coi_growth = round(df_f["PE_GR"].sum(), 2)
        ce_coi_growth = round(df_f["CE_GR"].sum(), 2)

        dc_atm = mround(open_strike, 50)
        all_s = sorted(df_f["STRIKE"].unique())
        try: dc_atm_idx = all_s.index(dc_atm)
        except: dc_atm_idx = next((i for i, s in enumerate(all_s) if s >= dc_atm), len(all_s) // 2)
        itm_pe_strikes = all_s[dc_atm_idx: dc_atm_idx + 6]
        itm_ce_strikes = all_s[max(0, dc_atm_idx - 5): dc_atm_idx + 1]
        itm_pe_pct = round(df_f[df_f["STRIKE"].isin(itm_pe_strikes)]["PE_PCOI"].sum(), 2)
        itm_ce_pct = round(df_f[df_f["STRIKE"].isin(itm_ce_strikes)]["CE_PCOI"].sum(), 2)

        decision = get_decision(pcr)

        # ── Score/Conf (Decision 2 style) & Signal (Decision-page style) —
        # computed directly from this page's own data, so no need to ever
        # visit the Decision / Decision 2 pages for these to populate.
        tot_ce_buy = df_f["CE_BUY"].sum(); tot_ce_sell = df_f["CE_SELL"].sum()
        tot_pe_buy = df_f["PE_BUY"].sum(); tot_pe_sell = df_f["PE_SELL"].sum()
        ce_bs = tot_ce_buy / tot_ce_sell if tot_ce_sell else 0
        pe_bs = tot_pe_buy / tot_pe_sell if tot_pe_sell else 0
        dec_signal = compute_dec_signal(pcr, ce_bs, pe_bs)
        dec2_score, dec2_conf, dec2_signal = compute_dec2_score(
            df_f, tot, pe_iv_sum, ce_iv_sum, oi_pcr=pcr, spot=spot, pivot=open_strike
        )

        m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
        m1.metric("PCR", f"{pcr:.4f}")
        m2.metric("Avijit OP", f"{avijit_op}")
        m3.metric("OI Tracker", f"{oi_tracker}")
        m4.metric("Decision", decision)
        m5.metric("Score (Dec 2)", f"{dec2_score:+d}/80")
        m6.metric("Conf (Dec 2)", f"{dec2_conf:.0f}%")
        m7.metric("Signal (Dec)", dec_signal)

        # ── Record a snapshot ──────────────────────────────────────────
        if st.session_state.rec_is_recording:
            current_time = datetime.now(IST).strftime("%H:%M:%S")
            if not st.session_state.rec_history or st.session_state.rec_history[-1]["Time"] != current_time:
                new_row = {
                    "Spot": spot,
                    "Chng": chng,
                    "Time": current_time,
                    "Avijit OP": avijit_op,
                    "OI Tracker": oi_tracker,
                    "PCR": round(pcr, 4),
                    "PE IV": pe_iv_sum,
                    "CE IV": ce_iv_sum,
                    "PE COI Gr": pe_coi_growth,
                    "CE COI Gr": ce_coi_growth,
                    "ITM PE": itm_pe_pct,
                    "ITM CE": itm_ce_pct,
                    "Decision": decision,
                    "Score": dec2_score,
                    "Conf": dec2_conf,
                    "Signal": dec_signal,
                }
                st.session_state.rec_history.append(new_row)
                # Persist to disk so history survives a restart/reload
                try:
                    pd.DataFrame([new_row]).to_csv(LOG_FILE, mode="a", header=not os.path.exists(LOG_FILE), index=False)
                except Exception:
                    pass

        st.subheader("Time-Series Data Recording")
        st.caption("Score, Conf & Signal are computed independently on this page using the same formulas as the Decision / Decision 2 pages — no need to visit them for these to populate.")

        top_c1, top_c2 = st.columns([1, 5])
        with top_c1:
            if st.button("🗑️ Clear History", key="clear_hist"):
                st.session_state.rec_history = []
                if os.path.exists(LOG_FILE):
                    try: os.remove(LOG_FILE)
                    except Exception: pass
                st.rerun()
        with top_c2:
            if st.session_state.rec_history:
                csv_bytes = pd.DataFrame(st.session_state.rec_history).to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download CSV", data=csv_bytes, file_name="nifty_recording_log.csv", mime="text/csv", key="dl_hist")

        if not st.session_state.rec_history:
            st.info("No data recorded yet. Toggle '⏺️ Record Data' on at the top to start capturing snapshots.")
        else:
            rec_cols = [
                ("Spot", "Spot"), ("Chng", "Chng"), ("Time", "Time"),
                ("Avijit OP", "Avijit"), ("OI Tracker", "OI Trk"), ("PCR", "PCR"),
                ("PE IV", "PE IV"), ("CE IV", "CE IV"),
                ("PE COI Gr", "PE COI Gr"), ("CE COI Gr", "CE COI Gr"),
                ("ITM PE", "ITM PE"), ("ITM CE", "ITM CE"), ("Decision", "Decision"),
                ("Score", "Score"), ("Conf", "Conf"), ("Signal", "Signal"),
            ]

            html_rec = ['<table class="rec-table"><thead><tr>']
            for _, label in rec_cols:
                html_rec.append(f'<th>{label}</th>')
            html_rec.append('</tr></thead><tbody>')

            for row in reversed(st.session_state.rec_history):
                chng_val = row.get("Chng", 0)
                chng_cls = "pos" if chng_val >= 0 else "neg"
                oi_trk = row.get("OI Tracker", 0)
                oi_trk_cls = "pos" if oi_trk >= 0 else "neg"
                avj = row.get("Avijit OP", 0)
                avj_cls = "pos" if avj >= 0 else "neg"
                pcog = row.get("PE COI Gr", 0)
                ccog = row.get("CE COI Gr", 0)
                pcog_cls = "pos" if pcog >= 0 else "neg"
                ccog_cls = "pos" if ccog >= 0 else "neg"
                dec = row.get("Decision", "")
                dec_cls = "pos" if "CE" in dec else ("neg" if "PE" in dec else "")

                html_rec.append('<tr>')
                html_rec.append(f'<td>₹{row["Spot"]:,.0f}</td>')
                html_rec.append(f'<td class="{chng_cls}">{chng_val:+.0f}</td>')
                html_rec.append(f'<td>{row["Time"]}</td>')
                html_rec.append(f'<td class="{avj_cls}">{avj:+.0f}</td>')
                html_rec.append(f'<td class="{oi_trk_cls}">{oi_trk:+.0f}</td>')
                html_rec.append(f'<td>{row["PCR"]:.0f}</td>')
                html_rec.append(f'<td>{float(row.get("PE IV", 0) or 0):.0f}</td>')
                html_rec.append(f'<td>{float(row.get("CE IV", 0) or 0):.0f}</td>')
                html_rec.append(f'<td class="{pcog_cls}">{pcog:+.0f}%</td>')
                html_rec.append(f'<td class="{ccog_cls}">{ccog:+.0f}%</td>')
                itm_pe_v = row.get("ITM PE", 0)
                itm_ce_v = row.get("ITM CE", 0)
                itm_pe_cls = "pos" if itm_pe_v >= 0 else "neg"
                itm_ce_cls = "pos" if itm_ce_v >= 0 else "neg"
                html_rec.append(f'<td class="{itm_pe_cls}">{itm_pe_v:+.0f}%</td>')
                html_rec.append(f'<td class="{itm_ce_cls}">{itm_ce_v:+.0f}%</td>')
                html_rec.append(f'<td title="{dec}" class="{dec_cls}">{dec}</td>')

                score_v = row.get("Score")
                conf_v = row.get("Conf")
                sig_v = row.get("Signal")
                has_score = score_v is not None and score_v != "" and not (isinstance(score_v, float) and pd.isna(score_v))
                has_conf = conf_v is not None and conf_v != "" and not (isinstance(conf_v, float) and pd.isna(conf_v))
                has_sig = sig_v is not None and sig_v != "" and not (isinstance(sig_v, float) and pd.isna(sig_v))
                score_cls = "pos" if (has_score and float(score_v) >= 0) else ("neg" if has_score else "")
                score_disp = f"{float(score_v):+.0f}" if has_score else "—"
                conf_disp = f"{float(conf_v):.0f}%" if has_conf else "—"
                sig_disp = str(sig_v) if has_sig else "—"
                sig_cls = "pos" if (has_sig and "CE" in sig_disp) else ("neg" if (has_sig and "PE" in sig_disp) else "")

                html_rec.append(f'<td class="{score_cls}">{score_disp}</td>')
                html_rec.append(f'<td>{conf_disp}</td>')
                html_rec.append(f'<td title="{sig_disp}" class="{sig_cls}">{sig_disp}</td>')
                html_rec.append('</tr>')

            html_rec.append('</tbody></table>')
            st.markdown("".join(html_rec), unsafe_allow_html=True)

    if auto_refresh:
        nxt = max(0, DATA_REFRESH - int(time.time() - st.session_state.rec_last_fetch))
        st.caption(f"⏱ Next auto-fetch in {nxt}s")
        time.sleep(nxt)
        st.rerun()

else:
    st.info("⏳ Loading data...")
    time.sleep(2)
    st.rerun()
