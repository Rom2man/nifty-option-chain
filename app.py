import streamlit as st
import requests
import pandas as pd
import time
import math
from datetime import datetime
import plotly.graph_objects as go

st.set_page_config(page_title="Nifty Option Chain", page_icon="📈", layout="wide")

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
    .oc-table { width:100%; border-collapse:collapse; font-size:13px; font-weight:600; }
    .oc-table th { background:#1565C0; color:white; padding:6px 4px; text-align:center; font-size:12px; font-weight:700; border:1px solid #1976D2; }
    .oc-table td { padding:4px 5px; text-align:center; border:1px solid #E0E0E0; font-size:13px; font-weight:600; white-space:nowrap; }
    .oc-table tr:hover td { filter:brightness(0.96); }
    .strike-col { background:#1565C0 !important; color:white !important; font-weight:800 !important; font-size:14px !important; }
    .atm-row td { background:#FFF9C4 !important; font-weight:800 !important; }
    .pivot-row td { background:#FFE0B2 !important; font-weight:800 !important; }
    .total-row td { background:#1565C0 !important; color:white !important; font-weight:800 !important; font-size:13px !important; }
    .vol-max { background:#A5D6A7 !important; color:#1B5E20 !important; font-weight:800 !important; }
    .bar-cell { position:relative; min-width:70px; }
    .bar-bg-blue   { position:absolute; left:0; top:0; bottom:0; background:rgba(21,101,192,0.20); border-radius:2px; z-index:0; }
    .bar-bg-green  { position:absolute; left:0; top:0; bottom:0; background:rgba(46,125,50,0.20);  border-radius:2px; z-index:0; }
    .bar-bg-red    { position:absolute; left:0; top:0; bottom:0; background:rgba(198,40,40,0.20);  border-radius:2px; z-index:0; }
    .bar-bg-orange { position:absolute; left:0; top:0; bottom:0; background:rgba(255,152,0,0.24);  border-radius:2px; z-index:0; }
    .bar-text { position:relative; z-index:1; }
    div[data-testid="metric-container"] { background:#F8F9FA; border:1px solid #E0E0E0; border-radius:8px; padding:8px !important; text-align:center; }
    div[data-testid="stMetricValue"] { font-size:22px !important; font-weight:800 !important; color:#1565C0 !important; }
    div[data-testid="stMetricLabel"] { font-size:13px !important; font-weight:700 !important; }
    .rec-link {
        background:#E3F2FD; padding:8px 14px; border-radius:8px; color:#1565C0;
        font-weight:700; display:inline-block; font-size:13px; border:1px solid #BBDEFB;
    }
</style>
""", unsafe_allow_html=True)

st.title("📈 Nifty Option Chain")

for k,v in {"cookie":"","cookie_time":0,"raw_data":None,"last_fetch":0,"open_price":0,"oi_multiplier":50,"prev_close":0,"open_spot":0}.items():
    if k not in st.session_state: st.session_state[k]=v

COOKIE_REFRESH=300; DATA_REFRESH=60

def mround(val,multiple): return math.floor(val/multiple+0.5)*multiple

def fetch_fresh_cookie():
    try:
        s=requests.Session()
        h={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0","Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Encoding":"gzip, deflate","Accept-Language":"en-US,en;q=0.9","Connection":"keep-alive"}
        s.get("https://www.nseindia.com",headers=h,timeout=15); time.sleep(1.5)
        h["Referer"]="https://www.nseindia.com/"
        s.get("https://www.nseindia.com/option-chain",headers=h,timeout=15); time.sleep(1)
        ck="; ".join([f"{k}={v}" for k,v in s.cookies.items()])
        return (ck,None) if ck else (None,"No cookies")
    except Exception as e: return None,str(e)

def filter_future_expiries(dates):
    today = datetime.now().date()
    valid = []
    for d in dates:
        try:
            if datetime.strptime(d, "%d-%b-%Y").date() >= today: valid.append(d)
        except: valid.append(d)
    return valid

def fetch_expiry_dates(symbol, cookie):
    url = f"https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol={symbol}"
    h={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0","Accept":"application/json, text/plain, */*","Accept-Encoding":"gzip, deflate","Accept-Language":"en-US,en;q=0.9","Referer":"https://www.nseindia.com/option-chain","Cookie":cookie,"X-Requested-With":"XMLHttpRequest","Connection":"keep-alive"}
    try:
        r=requests.get(url,headers=h,timeout=15)
        if r.status_code==200: return filter_future_expiries(r.json().get("records",{}).get("expiryDates",[]))
        return []
    except: return []

def fetch_option_chain(symbol,expiry,cookie):
    url=f"https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol={symbol}&expiry={expiry}"
    h={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0","Accept":"application/json, text/plain, */*","Accept-Encoding":"gzip, deflate","Accept-Language":"en-US,en;q=0.9","Referer":"https://www.nseindia.com/option-chain","Cookie":cookie,"X-Requested-With":"XMLHttpRequest","Connection":"keep-alive"}
    try:
        r=requests.get(url,headers=h,timeout=15)
        return (r.json(),None) if r.status_code==200 else (None,f"Status {r.status_code}")
    except Exception as e: return None,str(e)

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
    # Method 1: equity-stockIndices (most reliable)
    try:
        r = requests.get("https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050", headers=h, timeout=15)
        if r.status_code == 200:
            for row in r.json().get("data", []):
                name = row.get("index","") or row.get("indexSymbol","")
                if "NIFTY 50" in name.upper() and "BANK" not in name.upper():
                    op = float(row.get("open", 0) or 0)
                    pc = float(row.get("previousClose", 0) or 0)
                    if op > 0 and pc > 0: return op, pc
    except: pass
    # Method 2: allIndices
    try:
        r2 = requests.get("https://www.nseindia.com/api/allIndices", headers=h, timeout=15)
        if r2.status_code == 200:
            for row in r2.json().get("data", []):
                name = row.get("index","") or row.get("indexSymbol","")
                if "NIFTY 50" in name.upper() and "BANK" not in name.upper():
                    op = float(row.get("open", 0) or 0)
                    pc = float(row.get("previousClose", 0) or 0)
                    if op > 0 and pc > 0: return op, pc
    except: pass
    # Method 3: index-tracker API
    try:
        r3 = requests.get("https://www.nseindia.com/api/index-tracker?indexSymbol=NIFTY%2050", headers=h, timeout=15)
        if r3.status_code == 200:
            d = r3.json()
            op = float(d.get("open",0) or d.get("opn",0) or d.get("Open",0) or 0)
            pc = float(d.get("previousClose",0) or d.get("prevClose",0) or d.get("PrevClose",0) or 0)
            if op > 0 and pc > 0: return op, pc
    except: pass
    return 0, 0

def parse_data(json_data):
    rec=json_data.get("records",{}); spot=rec.get("underlyingValue",0); rows=[]
    for item in rec.get("data",[]):
        ce=item.get("CE",{}); pe=item.get("PE",{})
        rows.append({"STRIKE":item.get("strikePrice",0),
            "CE_OI":ce.get("openInterest",0), "CE_COI":ce.get("changeinOpenInterest",0),
            "CE_PCOI":ce.get("pchangeinOpenInterest",0), "CE_VOL":ce.get("totalTradedVolume",0),
            "CE_IV":ce.get("impliedVolatility",0), "CE_LTP":ce.get("lastPrice",0),
            "PE_OI":pe.get("openInterest",0), "PE_COI":pe.get("changeinOpenInterest",0),
            "PE_PCOI":pe.get("pchangeinOpenInterest",0), "PE_VOL":pe.get("totalTradedVolume",0),
            "PE_IV":pe.get("impliedVolatility",0), "PE_LTP":pe.get("lastPrice",0)})
    return pd.DataFrame(rows),spot

def fmt_oi(v):
    try:
        v=float(v)
        if v>=10_000_000: return f"{v/10_000_000:.2f}Cr"
        if v>=100_000: return f"{v/100_000:.2f}L"
        return f"{int(v):,}"
    except: return str(v)

def cov(coi,vol):
    try: return f"{coi/vol:.3f}" if vol else "0.000"
    except: return "0.000"

def bar_cell(value, max_val, fmt_val, color="blue"):
    pct_w = min(100, abs(value)/max_val*100) if max_val else 0
    return f'<td class="bar-cell"><div class="bar-bg-{color}" style="width:{pct_w:.1f}%"></div><span class="bar-text">{fmt_val}</span></td>'

# ── Controls ──────────────────────────────────────────────────
c1,c2,c3,c4 = st.columns([1, 1.5, 1, 1])
with c1: symbol = st.selectbox("Symbol",["NIFTY","BANKNIFTY","FINNIFTY"])

if "expiry_dates" not in st.session_state: st.session_state.expiry_dates=[]
with c2:
    expiry_list = st.session_state.expiry_dates if st.session_state.expiry_dates else ["30-Jun-2026"]
    expiry = st.selectbox("Expiry Date", expiry_list)

with c3: auto_refresh = st.toggle("🔄 Auto Refresh", value=True)
with c4: manual_btn = st.button("⚡ Refresh Now", use_container_width=True)

st.markdown('<span class="rec-link">⏺️ Live time-series recording has moved to the <b>Recording</b> page — see the sidebar</span>', unsafe_allow_html=True)

cs1, cs2, cs3 = st.columns([2,1,1])
with cs1:
    age=int(time.time()-st.session_state.cookie_time)
    if st.session_state.cookie: st.markdown(f'<span class="cookie-ok">🍪 Cookie OK — age: {age}s</span>',unsafe_allow_html=True)
    else: st.markdown('<span style="color:red;font-weight:bold">🍪 Fetching cookie...</span>',unsafe_allow_html=True)
with cs2: force_cookie=st.button("🔑 Refresh Cookie",use_container_width=True)
with cs3:
    mult=st.number_input("OI Tracker Multiplier",min_value=1,max_value=1000,value=st.session_state.oi_multiplier,step=1)
    st.session_state.oi_multiplier=mult

# ── Cookie & Fetch Logic ──────────────────────────────────────────
if age>COOKIE_REFRESH or not st.session_state.cookie or force_cookie:
    with st.spinner("🍪 Getting fresh cookie..."):
        ck,_=fetch_fresh_cookie()
        if ck:
            st.session_state.cookie=ck; st.session_state.cookie_time=time.time()
            dates=fetch_expiry_dates(symbol,ck)
            if dates: st.session_state.expiry_dates=dates

data_age=int(time.time()-st.session_state.last_fetch)
should_fetch=manual_btn or (auto_refresh and data_age>=DATA_REFRESH) or st.session_state.raw_data is None

if should_fetch and st.session_state.cookie:
    data,err=fetch_option_chain(symbol,expiry,st.session_state.cookie)
    if data:
        st.session_state.raw_data=data; st.session_state.last_fetch=time.time()
        _,spot=parse_data(data)
        if st.session_state.open_price==0:
            day_open, day_prev_close = fetch_nifty_open(st.session_state.cookie)
            if day_open > 0:
                st.session_state.open_spot  = day_open
                st.session_state.open_price = mround(day_open, 50)
            else:
                st.session_state.open_spot  = spot
                st.session_state.open_price = mround(spot, 50)
            if st.session_state.prev_close == 0 and day_prev_close > 0:
                st.session_state.prev_close = day_prev_close
        dates=data.get("records",{}).get("expiryDates",[])
        if dates: st.session_state.expiry_dates=filter_future_expiries(dates)

# ── Display ───────────────────────────────────────────────
open_price = st.session_state.get("open_price", 0)

if st.session_state.raw_data:
    df,spot=parse_data(st.session_state.raw_data)
    last=int(time.time()-st.session_state.last_fetch)
    atm_strike  = mround(spot, 50)
    open_strike = st.session_state.open_price if st.session_state.open_price > 0 else atm_strike
    open_actual = st.session_state.open_spot

    st.markdown(f'''<div class="spot-bar">
        📊 LTP: <b>₹{spot:,.2f}</b> &nbsp;|&nbsp;
        Day Open: <b>₹{open_actual:,.2f}</b> &nbsp;|&nbsp;
        Pivot (Rounded): <b>₹{open_strike:,}</b> &nbsp;|&nbsp;
        ATM: <b>₹{atm_strike:,}</b> &nbsp;|&nbsp;
        {symbol} &nbsp;|&nbsp; Expiry: {expiry} &nbsp;|&nbsp;
        Updated: {last}s ago
    </div>''',unsafe_allow_html=True)

    lo=open_strike-250; hi=open_strike+250
    df_f=df[(df["STRIKE"]>=lo)&(df["STRIKE"]<=hi)].copy().reset_index(drop=True)

    if df_f.empty:
        st.warning("No data in ±250 range.")
    else:
        tot={k:df_f[k].sum() for k in ["CE_OI","CE_COI","CE_VOL","PE_OI","PE_COI","PE_VOL"]}
        pcr = tot["PE_OI"] / tot["CE_OI"] if tot["CE_OI"] else 0

        # ── Derived calculations — EXACT same formulas as 2_Calculations.py ───
        prev_close = st.session_state.prev_close

        # ITM PE / ITM CE — EXACT same formula as Detailed_Calculations_fixed.py
        # ATM here = MROUND(open_price, 50) matching DC page's atm_strike
        # ITM PE: ATM + 5 strikes ABOVE (6 total including ATM)
        # ITM CE: 5 strikes BELOW + ATM (6 total including ATM)
        dc_atm = mround(open_strike, 50)   # same as DC page: mround(open_price, 50)
        all_s  = sorted(df_f["STRIKE"].unique())
        try:    dc_atm_idx = all_s.index(dc_atm)
        except: dc_atm_idx = next((i for i,s in enumerate(all_s) if s>=dc_atm), len(all_s)//2)
        itm_pe_strikes = all_s[dc_atm_idx : dc_atm_idx+6]
        itm_ce_strikes = all_s[max(0, dc_atm_idx-5) : dc_atm_idx+1]
        itm_pe_pct = round(df_f[df_f["STRIKE"].isin(itm_pe_strikes)]["PE_PCOI"].sum(), 2)
        itm_ce_pct = round(df_f[df_f["STRIKE"].isin(itm_ce_strikes)]["CE_PCOI"].sum(), 2)
        # Always sync to session_state so DC page & Recording table agree
        st.session_state["dc_itm_pe"] = itm_pe_pct
        st.session_state["dc_itm_ce"] = itm_ce_pct

        def get_decision(pcr_val):
            if pcr_val >= 1.5:    return "Strong Buy CE"
            elif pcr_val >= 1.2:  return "Buy CE"
            elif pcr_val <= 0.5:  return "Super Strong Buy PE"
            elif pcr_val <= 0.65: return "Strong Buy PE"
            elif pcr_val <= 0.8:  return "Buy PE"
            else:                 return "Neutral"
        decision = get_decision(pcr)

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Total Call OI", fmt_oi(tot["CE_OI"]))
        m2.metric("Total Put OI", fmt_oi(tot["PE_OI"]))
        m3.metric("PCR", f"{pcr:.4f}")
        m4.metric("ATM Strike", f"₹{atm_strike:,}")
        m5.metric("ITM PE / ITM CE", f"{itm_pe_pct:+.2f}% / {itm_ce_pct:+.2f}%")
        m6.metric("Decision", decision)

        max_ce_vol_s=df_f.loc[df_f["CE_VOL"].idxmax(),"STRIKE"]
        max_pe_vol_s=df_f.loc[df_f["PE_VOL"].idxmax(),"STRIKE"]
        max_ce_oi=df_f["CE_OI"].max(); max_pe_oi=df_f["PE_OI"].max()
        max_ce_coi=df_f["CE_COI"].abs().max(); max_pe_coi=df_f["PE_COI"].abs().max()

        df_f["CE_PCT"] = df_f["CE_PCOI"]; df_f["PE_PCT"] = df_f["PE_PCOI"]
        max_ce_pct = df_f["CE_PCT"].abs().max() if df_f["CE_PCT"].abs().max() > 0 else 1
        max_pe_pct = df_f["PE_PCT"].abs().max() if df_f["PE_PCT"].abs().max() > 0 else 1

        tab1, tab2 = st.tabs(["📋 Option Chain", "📊 Visual Charts"])

        with tab1:
            # ── SPECULATIVE NAKED BUYING ZONES ────────────────────────────────
            otm_ce = df_f[df_f["STRIKE"] > atm_strike]
            otm_pe = df_f[df_f["STRIKE"] < atm_strike]
            if not otm_ce.empty and not otm_pe.empty:
                agg_ce_strike = int(otm_ce.loc[otm_ce["CE_VOL"].idxmax(), "STRIKE"])
                agg_pe_strike = int(otm_pe.loc[otm_pe["PE_VOL"].idxmax(), "STRIKE"])
                ce_vol_str    = fmt_oi(otm_ce["CE_VOL"].max())
                pe_vol_str    = fmt_oi(otm_pe["PE_VOL"].max())
                naked_html = (
                    '<div style="background:#E3F2FD; padding:15px; border-radius:8px;'
                    ' border-left:6px solid #1976D2; margin-bottom:15px;'
                    ' box-shadow:0 2px 4px rgba(0,0,0,0.08);">'
                    '<h4 style="margin:0 0 6px 0; color:#1565C0; font-size:16px;">'
                    '&#128373; Speculative Naked Buying Zones</h4>'
                    '<p style="font-size:12px; color:#555; margin:0 0 10px 0;">'
                    '<i>OTM strike with highest volume = likely naked buyer concentration. '
                    'Calls above ATM = bullish bet; Puts below ATM = bearish bet.</i></p>'
                    '<div style="display:flex; gap:50px; font-size:14px; font-weight:600;">'
                    '<div style="background:#fff; padding:10px 16px; border-radius:6px; border:1px solid #BBDEFB;">'
                    '&#128200; Max Call Buying (Bullish)<br>'
                    '<span style="color:#1565C0; font-size:20px; font-weight:800;">&#8377;' + f"{agg_ce_strike:,}" + '</span>'
                    '&nbsp;&nbsp;<span style="color:#555; font-size:13px; font-weight:500;">Vol: ' + ce_vol_str + '</span>'
                    '</div>'
                    '<div style="background:#fff; padding:10px 16px; border-radius:6px; border:1px solid #FFCDD2;">'
                    '&#128201; Max Put Buying (Bearish)<br>'
                    '<span style="color:#C62828; font-size:20px; font-weight:800;">&#8377;' + f"{agg_pe_strike:,}" + '</span>'
                    '&nbsp;&nbsp;<span style="color:#555; font-size:13px; font-weight:500;">Vol: ' + pe_vol_str + '</span>'
                    '</div>'
                    '</div></div>'
                )
                st.markdown(naked_html, unsafe_allow_html=True)
            # ─────────────────────────────────────────────────────────────────

            st.markdown("""<div style="display:flex;gap:20px;padding:3px 0 6px 0;font-size:13px;font-weight:600">
                <span>🟡 ATM</span><span>🟠 Open/Pivot</span> <span>🟢 Max Volume</span>
                <span style="color:#2E7D32">▲ COI+</span> <span style="color:#C62828">▼ COI−</span>
            </div>""",unsafe_allow_html=True)
            # ── HTML Table ───────────────────────────────────
            html=['<table class="oc-table"><thead><tr>']
            for h,s in [("OI","CE"),("COI","CE"),("%COI","CE"),("C/V","CE"),("VOL","CE"),("IV","CE"),("STRIKE",""),("IV","PE"),("VOL","PE"),("C/V","PE"),("%COI","PE"),("COI","PE"),("OI","PE")]:
                html.append(f'<th>{h}<br><small>{s}</small></th>')
            html.append('</tr></thead><tbody>')

            for i,row in df_f.iterrows():
                s=row["STRIKE"]; ce_coi=row["CE_COI"]; pe_coi=row["PE_COI"]
                ce_pct_r = row["CE_PCOI"]; pe_pct_r = row["PE_PCOI"]
                rc="atm-row" if s==atm_strike else ("pivot-row" if s==open_strike else "")

                html.append(f'<tr class="{rc}">')
                html.append(bar_cell(row["CE_OI"],max_ce_oi,fmt_oi(row["CE_OI"]),"blue"))

                ce_coi_c="green" if ce_coi>=0 else "red"
                ce_coi_fmt='<span style="color:' + ("#2E7D32" if ce_coi>=0 else "#C62828") + ';font-weight:800">' + fmt_oi(ce_coi) + '</span>'
                html.append(f'<td class="bar-cell"><div class="bar-bg-{ce_coi_c}" style="width:{min(100,abs(ce_coi)/max_ce_coi*100 if max_ce_coi else 0):.1f}%"></div><span class="bar-text">{ce_coi_fmt}</span></td>')
                html.append(f'<td class="bar-cell"><div class="bar-bg-orange" style="width:{min(100,abs(ce_pct_r)/max_ce_pct*100 if max_ce_pct else 0):.1f}%"></div><span class="bar-text">{ce_pct_r:.1f}%</span></td>')
                html.append(f'<td>{cov(ce_coi,row["CE_VOL"])}</td>')

                vc="vol-max" if s==max_ce_vol_s else ""
                html.append(f'<td class="{vc}">{fmt_oi(row["CE_VOL"])}</td>')
                html.append(f'<td>{row["CE_IV"]:.1f}</td>')
                html.append(f'<td class="strike-col">{int(s)}</td>')
                html.append(f'<td>{row["PE_IV"]:.1f}</td>')
                vc_pe="vol-max" if s==max_pe_vol_s else ""
                html.append(f'<td class="{vc_pe}">{fmt_oi(row["PE_VOL"])}</td>')
                html.append(f'<td>{cov(pe_coi,row["PE_VOL"])}</td>')
                html.append(f'<td class="bar-cell"><div class="bar-bg-orange" style="width:{min(100,abs(pe_pct_r)/max_pe_pct*100 if max_pe_pct else 0):.1f}%"></div><span class="bar-text">{pe_pct_r:.1f}%</span></td>')

                pe_coi_c="green" if pe_coi>=0 else "red"
                pe_coi_fmt='<span style="color:' + ("#2E7D32" if pe_coi>=0 else "#C62828") + ';font-weight:800">' + fmt_oi(pe_coi) + '</span>'
                html.append(f'<td class="bar-cell"><div class="bar-bg-{pe_coi_c}" style="width:{min(100,abs(pe_coi)/max_pe_coi*100 if max_pe_coi else 0):.1f}%"></div><span class="bar-text">{pe_coi_fmt}</span></td>')
                html.append(bar_cell(row["PE_OI"],max_pe_oi,fmt_oi(row["PE_OI"]),"green"))
                html.append('</tr>')

            html.append('<tr class="total-row">')
            html.append(f'<td>{fmt_oi(tot["CE_OI"])}</td>')
            html.append(f'<td>{fmt_oi(tot["CE_COI"])}</td><td></td><td></td>')
            html.append(f'<td>{fmt_oi(tot["CE_VOL"])}</td><td></td>')
            html.append('<td>TOTAL</td>')
            html.append('<td></td>')
            html.append(f'<td>{fmt_oi(tot["PE_VOL"])}</td><td></td><td></td>')
            html.append(f'<td>{fmt_oi(tot["PE_COI"])}</td>')
            html.append(f'<td>{fmt_oi(tot["PE_OI"])}</td>')
            html.append('</tr></tbody></table>')

            st.markdown("".join(html), unsafe_allow_html=True)

        with tab2:
            st.subheader("Call vs Put Open Interest by Strike")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_f["STRIKE"], y=df_f["CE_OI"], name="Call OI", marker_color='#1565C0'))
            fig.add_trace(go.Bar(x=df_f["STRIKE"], y=df_f["PE_OI"], name="Put OI", marker_color='#2E7D32'))
            fig.update_layout(barmode='group', xaxis_title="Strike Price", yaxis_title="Open Interest",
                              plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=20, r=20, t=30, b=20))
            fig.add_vline(x=atm_strike, line_width=2, line_dash="dash", line_color="orange", annotation_text="ATM")
            st.plotly_chart(fig, use_container_width=True)

    if auto_refresh:
        nxt=max(0,DATA_REFRESH-int(time.time()-st.session_state.last_fetch))
        st.caption(f"⏱ Next auto-refresh in {nxt}s")
        time.sleep(nxt)
        st.rerun()

else:
    st.info("⏳ Loading data...")
    time.sleep(2)
    st.rerun()