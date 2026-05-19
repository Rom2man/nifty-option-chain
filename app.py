import streamlit as st
import requests
import pandas as pd
import time
import math

st.set_page_config(page_title="Nifty Option Chain", page_icon="📈", layout="wide")

st.markdown("""
<style>
    .spot-price {
        background: #E3F2FD; padding: 8px 16px; border-radius: 8px;
        font-size: 18px; font-weight: bold; color: #1565C0; margin-bottom: 10px;
    }
    .cookie-ok { background:#E8F5E9; padding:6px 12px; border-radius:6px; color:#2E7D32; font-weight:bold; display:inline-block; }
</style>
""", unsafe_allow_html=True)

st.title("📈 Nifty Option Chain")

for k, v in {"cookie":"","cookie_time":0,"raw_data":None,"last_fetch":0,"open_price":0}.items():
    if k not in st.session_state: st.session_state[k] = v

COOKIE_REFRESH = 90
DATA_REFRESH   = 60

def mround(val, multiple):
    return math.floor(val / multiple + 0.5) * multiple

def fetch_fresh_cookie():
    try:
        s = requests.Session()
        h = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Encoding":"gzip, deflate","Accept-Language":"en-US,en;q=0.9","Connection":"keep-alive"}
        s.get("https://www.nseindia.com", headers=h, timeout=15)
        time.sleep(1.5)
        h["Referer"] = "https://www.nseindia.com/"
        s.get("https://www.nseindia.com/option-chain", headers=h, timeout=15)
        time.sleep(1)
        ck = "; ".join([f"{k}={v}" for k,v in s.cookies.items()])
        return (ck, None) if ck else (None, "No cookies")
    except Exception as e: return None, str(e)

def fetch_option_chain(symbol, expiry, cookie):
    url = f"https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol={symbol}&expiry={expiry}"
    h = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0","Accept":"application/json, text/plain, */*","Accept-Encoding":"gzip, deflate","Accept-Language":"en-US,en;q=0.9","Referer":"https://www.nseindia.com/option-chain","Cookie":cookie,"X-Requested-With":"XMLHttpRequest","Connection":"keep-alive"}
    try:
        r = requests.get(url, headers=h, timeout=15)
        return (r.json(), None) if r.status_code == 200 else (None, f"Status {r.status_code}")
    except Exception as e: return None, str(e)

def parse_data(json_data):
    rec  = json_data.get("records", {})
    spot = rec.get("underlyingValue", 0)
    rows = []
    for item in rec.get("data", []):
        ce = item.get("CE", {}); pe = item.get("PE", {})
        rows.append({"STRIKE":item.get("strikePrice",0),
            "CE_OI":ce.get("openInterest",0),"CE_COI":ce.get("changeinOpenInterest",0),
            "CE_VOL":ce.get("totalTradedVolume",0),"CE_IV":ce.get("impliedVolatility",0),
            "CE_LTP":ce.get("lastPrice",0),
            "PE_OI":pe.get("openInterest",0),"PE_COI":pe.get("changeinOpenInterest",0),
            "PE_VOL":pe.get("totalTradedVolume",0),"PE_IV":pe.get("impliedVolatility",0),
            "PE_LTP":pe.get("lastPrice",0)})
    return pd.DataFrame(rows), spot

def fmt_oi(v):
    try:
        v=float(v)
        if v>=10_000_000: return f"{v/10_000_000:.2f}Cr"
        if v>=100_000: return f"{v/100_000:.2f}L"
        return f"{int(v):,}"
    except: return str(v)

def pct(part, total):
    try: return f"{part/total*100:.1f}%" if total else "0%"
    except: return "0%"

def cov(coi, vol):
    try: return f"{coi/vol:.3f}" if vol else "0.000"
    except: return "0.000"

# Controls
c1,c2,c3,c4 = st.columns([1,1.5,1,1])
with c1: symbol = st.selectbox("Symbol", ["NIFTY","BANKNIFTY","FINNIFTY"])
with c2: expiry = st.selectbox("Expiry Date", ["19-May-2026","22-May-2026","29-May-2026","05-Jun-2026","26-Jun-2026","25-Dec-2026"])
with c3: auto_refresh = st.toggle("🔄 Auto Refresh (60s)", value=True)
with c4: manual_btn = st.button("⚡ Refresh Now", use_container_width=True)

cs1,cs2 = st.columns([3,1])
with cs1:
    age = int(time.time()-st.session_state.cookie_time)
    if st.session_state.cookie:
        st.markdown(f'<span class="cookie-ok">🍪 Cookie OK — age: {age}s (auto every {COOKIE_REFRESH}s)</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span style="color:red">🍪 Fetching cookie...</span>', unsafe_allow_html=True)
with cs2: force_cookie = st.button("🔑 Refresh Cookie", use_container_width=True)

if age > COOKIE_REFRESH or not st.session_state.cookie or force_cookie:
    with st.spinner("🍪 Getting fresh cookie..."):
        ck,_ = fetch_fresh_cookie()
        if ck: st.session_state.cookie=ck; st.session_state.cookie_time=time.time()

data_age     = int(time.time()-st.session_state.last_fetch)
should_fetch = manual_btn or (auto_refresh and data_age>=DATA_REFRESH) or st.session_state.raw_data is None

if should_fetch and st.session_state.cookie:
    if int(time.time()-st.session_state.cookie_time)>COOKIE_REFRESH:
        ck,_=fetch_fresh_cookie()
        if ck: st.session_state.cookie=ck; st.session_state.cookie_time=time.time()
    data,err = fetch_option_chain(symbol, expiry, st.session_state.cookie)
    if data:
        st.session_state.raw_data=data; st.session_state.last_fetch=time.time()
        _,spot=parse_data(data)
        if st.session_state.open_price==0: st.session_state.open_price=mround(spot,50)
    else:
        ck,_=fetch_fresh_cookie()
        if ck:
            st.session_state.cookie=ck; st.session_state.cookie_time=time.time()
            data,_=fetch_option_chain(symbol,expiry,st.session_state.cookie)
            if data: st.session_state.raw_data=data; st.session_state.last_fetch=time.time()

if st.session_state.raw_data:
    df, spot = parse_data(st.session_state.raw_data)
    last         = int(time.time()-st.session_state.last_fetch)
    open_strike  = st.session_state.open_price
    atm_strike   = mround(spot, 50)

    st.markdown(f'<div class="spot-price">📊 LTP: ₹{spot:,.2f} &nbsp;|&nbsp; Open(Pivot): ₹{open_strike:,} &nbsp;|&nbsp; ATM: ₹{atm_strike:,} &nbsp;|&nbsp; {symbol} &nbsp;|&nbsp; Expiry: {expiry} &nbsp;|&nbsp; Updated: {last}s ago</div>', unsafe_allow_html=True)

    lo = open_strike-250; hi = open_strike+250
    df_f = df[(df["STRIKE"]>=lo)&(df["STRIKE"]<=hi)].copy().reset_index(drop=True)

    if df_f.empty:
        st.warning("No data in ±250 range.")
    else:
        tot = {k: df_f[k].sum() for k in ["CE_OI","CE_COI","CE_VOL","PE_OI","PE_COI","PE_VOL"]}

        max_ce_vol_idx = int(df_f["CE_VOL"].idxmax())
        max_pe_vol_idx = int(df_f["PE_VOL"].idxmax())
        max_ce_vol_strike = df_f.loc[max_ce_vol_idx, "STRIKE"]
        max_pe_vol_strike = df_f.loc[max_pe_vol_idx, "STRIKE"]

        # Build display df (display cols only)
        disp_rows = []
        for i, row in df_f.iterrows():
            disp_rows.append({
                "OI(CE)":     fmt_oi(row["CE_OI"]),
                "COI(CE)":    fmt_oi(row["CE_COI"]),
                "%COI(CE)":   pct(row["CE_COI"], tot["CE_COI"]),
                "C/V(CE)":    cov(row["CE_COI"], row["CE_VOL"]),
                "VOL(CE)":    fmt_oi(row["CE_VOL"]),
                "IV(CE)":     f"{row['CE_IV']:.1f}",
                "STRIKE":     int(row["STRIKE"]),
                "IV(PE)":     f"{row['PE_IV']:.1f}",
                "VOL(PE)":    fmt_oi(row["PE_VOL"]),
                "C/V(PE)":    cov(row["PE_COI"], row["PE_VOL"]),
                "%COI(PE)":   pct(row["PE_COI"], tot["PE_COI"]),
                "COI(PE)":    fmt_oi(row["PE_COI"]),
                "OI(PE)":     fmt_oi(row["PE_OI"]),
            })

        # Totals row
        disp_rows.append({
            "OI(CE)":fmt_oi(tot["CE_OI"]),"COI(CE)":fmt_oi(tot["CE_COI"]),
            "%COI(CE)":"100%","C/V(CE)":cov(tot["CE_COI"],tot["CE_VOL"]),
            "VOL(CE)":fmt_oi(tot["CE_VOL"]),"IV(CE)":"—",
            "STRIKE":"TOTAL",
            "IV(PE)":"—","VOL(PE)":fmt_oi(tot["PE_VOL"]),
            "C/V(PE)":cov(tot["PE_COI"],tot["PE_VOL"]),
            "%COI(PE)":"100%","COI(PE)":fmt_oi(tot["PE_COI"]),"OI(PE)":fmt_oi(tot["PE_OI"]),
        })

        df_disp = pd.DataFrame(disp_rows)
        n_data  = len(df_f)   # number of data rows (excluding totals)

        def style_fn(df):
            styles = pd.DataFrame("", index=df.index, columns=df.columns)
            for i in range(len(df)):
                row = df.iloc[i]
                # TOTAL row (last row)
                if i == n_data:
                    styles.iloc[i] = "background-color:#1565C0; color:white; font-weight:bold"
                    continue
                s = df_f.iloc[i]["STRIKE"]
                # ATM — yellow
                if s == atm_strike:
                    styles.iloc[i] = "background-color:#FFF9C4; font-weight:bold"
                # Open/Pivot — orange
                if s == open_strike:
                    styles.iloc[i] = "background-color:#FFE0B2; font-weight:bold"
                # Highest CE VOL — green cell
                if s == max_ce_vol_strike:
                    styles.at[i,"VOL(CE)"] = "background-color:#A5D6A7; color:#1B5E20; font-weight:bold"
                # Highest PE VOL — green cell
                if s == max_pe_vol_strike:
                    styles.at[i,"VOL(PE)"] = "background-color:#A5D6A7; color:#1B5E20; font-weight:bold"
                # COI color
                ce_coi = df_f.iloc[i]["CE_COI"]
                pe_coi = df_f.iloc[i]["PE_COI"]
                styles.at[i,"COI(CE)"] = styles.at[i,"COI(CE)"] + ("; color:#2E7D32; font-weight:bold" if ce_coi>0 else "; color:#C62828; font-weight:bold" if ce_coi<0 else "")
                styles.at[i,"COI(PE)"] = styles.at[i,"COI(PE)"] + ("; color:#2E7D32; font-weight:bold" if pe_coi>0 else "; color:#C62828; font-weight:bold" if pe_coi<0 else "")
            return styles

        st.dataframe(
            df_disp.style.apply(style_fn, axis=None)
                .set_properties(**{"text-align":"center","font-size":"12px"})
                .hide(axis="index"),
            use_container_width=True, height=650
        )

        st.caption("🟡 ATM &nbsp;&nbsp; 🟠 Open/Pivot &nbsp;&nbsp; 🟢 Highest Volume")

        # ── Bar Charts ────────────────────────────────────
        strikes = df_f["STRIKE"].astype(str).tolist()
        st.write("")
        st.subheader("📊 OI & COI Charts")
        ch1, ch2 = st.columns(2)
        with ch1:
            st.markdown("**CE — OI & COI**")
            st.bar_chart(pd.DataFrame({"CE OI":df_f["CE_OI"].tolist(),"CE COI":df_f["CE_COI"].tolist()},index=strikes), color=["#1565C0","#EF9A9A"])
        with ch2:
            st.markdown("**PE — OI & COI**")
            st.bar_chart(pd.DataFrame({"PE OI":df_f["PE_OI"].tolist(),"PE COI":df_f["PE_COI"].tolist()},index=strikes), color=["#C62828","#A5D6A7"])

        st.subheader("📊 Volume Charts")
        ch3, ch4 = st.columns(2)
        with ch3:
            st.markdown("**CE Volume**")
            st.bar_chart(pd.DataFrame({"CE VOL":df_f["CE_VOL"].tolist()},index=strikes), color=["#1976D2"])
        with ch4:
            st.markdown("**PE Volume**")
            st.bar_chart(pd.DataFrame({"PE VOL":df_f["PE_VOL"].tolist()},index=strikes), color=["#D32F2F"])

        # ── PCR Metrics ───────────────────────────────────
        st.write("")
        pcr_oi  = tot["PE_OI"] /tot["CE_OI"]  if tot["CE_OI"]  else 0
        pcr_vol = tot["PE_VOL"]/tot["CE_VOL"] if tot["CE_VOL"] else 0
        pcr_coi = tot["PE_COI"]/tot["CE_COI"] if tot["CE_COI"] else 0
        m1,m2,m3,m4,m5,m6 = st.columns(6)
        m1.metric("CE OI",   fmt_oi(tot["CE_OI"]))
        m2.metric("PE OI",   fmt_oi(tot["PE_OI"]))
        m3.metric("PCR OI",  f"{pcr_oi:.2f}",  delta="Bullish 📈" if pcr_oi>1  else "Bearish 📉")
        m4.metric("CE VOL",  fmt_oi(tot["CE_VOL"]))
        m5.metric("PE VOL",  fmt_oi(tot["PE_VOL"]))
        m6.metric("PCR VOL", f"{pcr_vol:.2f}", delta="Bullish 📈" if pcr_vol>1 else "Bearish 📉")

    if auto_refresh:
        nxt = max(0, DATA_REFRESH - int(time.time()-st.session_state.last_fetch))
        st.caption(f"⏱ Next auto-refresh in {nxt}s")
        time.sleep(nxt)
        st.rerun()
else:
    st.info("⏳ Loading data...")
    time.sleep(2)
    st.rerun()
