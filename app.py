import streamlit as st
import requests
import pandas as pd
import time
import math
from datetime import datetime

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
    .section-hdr {
        background:#F5F5F5; border-left:4px solid #1565C0;
        padding:7px 14px; font-size:14px; font-weight:700;
        color:#1565C0; margin:12px 0 6px 0; border-radius:0 6px 6px 0;
    }
    .oc-table { width:100%; border-collapse:collapse; font-size:13px; font-weight:600; }
    .oc-table th {
        background:#1565C0; color:white; padding:6px 4px; text-align:center;
        font-size:12px; font-weight:700; border:1px solid #1976D2;
    }
    .oc-table td {
        padding:4px 5px; text-align:center; border:1px solid #E0E0E0;
        font-size:13px; font-weight:600; white-space:nowrap;
    }
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
    /* Metric cards */
    div[data-testid="metric-container"] {
        background:#F8F9FA; border:1px solid #E0E0E0;
        border-radius:8px; padding:8px !important; text-align:center;
    }
    div[data-testid="stMetricValue"] { font-size:22px !important; font-weight:800 !important; color:#1565C0 !important; }
    div[data-testid="stMetricLabel"] { font-size:13px !important; font-weight:700 !important; }
    /* Recording table */
    .rec-table { width:100%; border-collapse:collapse; font-size:14px; }
    .rec-table th { background:#1565C0; color:white; padding:8px 10px; text-align:center; font-size:13px; font-weight:700; border:1px solid #1976D2; }
    .rec-table td { padding:7px 10px; text-align:center; border:1px solid #E0E0E0; font-size:14px; font-weight:600; }
    .rec-table tr:nth-child(even) td { background:#F8F9FA; }
    .rec-table tr:first-child td { background:#E3F2FD !important; font-weight:800 !important; }
    .pos { color:#2E7D32; font-weight:800; }
    .neg { color:#C62828; font-weight:800; }
</style>
""", unsafe_allow_html=True)

st.title("📈 Nifty Option Chain")

for k,v in {"cookie":"","cookie_time":0,"raw_data":None,"last_fetch":0,"open_price":0,"history":[],"oi_multiplier":50,"prev_close":0,"recording":False,"prev_df":None,"futures":[],"open_spot":0}.items():
    if k not in st.session_state: st.session_state[k]=v

COOKIE_REFRESH=90; DATA_REFRESH=60

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

def fetch_expiry_dates(symbol, cookie):
    """Fetch live expiry dates from NSE API"""
    url = f"https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol={symbol}"
    h={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0","Accept":"application/json, text/plain, */*","Accept-Encoding":"gzip, deflate","Accept-Language":"en-US,en;q=0.9","Referer":"https://www.nseindia.com/option-chain","Cookie":cookie,"X-Requested-With":"XMLHttpRequest","Connection":"keep-alive"}
    try:
        r=requests.get(url,headers=h,timeout=15)
        if r.status_code==200:
            data = r.json()
            dates = data.get("records",{}).get("expiryDates",[])
            return dates
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
    """Fetch today's open & prev close from NSE index-tracker page"""
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

    # Method 1: equity-stockIndices (most reliable — same data as index-tracker page)
    try:
        url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050"
        r = requests.get(url, headers=h, timeout=15)
        if r.status_code == 200:
            data = r.json()
            # First row in data[] is always NIFTY 50 index
            rows = data.get("data", [])
            for row in rows:
                name = row.get("index","") or row.get("indexSymbol","")
                if "NIFTY 50" in name.upper() and "BANK" not in name.upper():
                    open_val   = float(row.get("open",0)          or 0)
                    prev_close = float(row.get("previousClose",0) or 0)
                    if open_val > 0 and prev_close > 0:
                        return open_val, prev_close
    except: pass

    # Method 2: allIndices
    try:
        url2 = "https://www.nseindia.com/api/allIndices"
        r2 = requests.get(url2, headers=h, timeout=15)
        if r2.status_code == 200:
            rows2 = r2.json().get("data", [])
            for row in rows2:
                name = row.get("index","") or row.get("indexSymbol","")
                if "NIFTY 50" in name.upper() and "BANK" not in name.upper():
                    open_val   = float(row.get("open",0)          or 0)
                    prev_close = float(row.get("previousClose",0) or 0)
                    if open_val > 0 and prev_close > 0:
                        return open_val, prev_close
    except: pass

    # Method 3: index-tracker API
    try:
        url3 = "https://www.nseindia.com/api/index-tracker?indexSymbol=NIFTY%2050"
        r3 = requests.get(url3, headers=h, timeout=15)
        if r3.status_code == 200:
            d = r3.json()
            # Try multiple key names NSE uses
            open_val   = float(d.get("open",0) or d.get("opn",0) or d.get("Open",0) or 0)
            prev_close = float(d.get("previousClose",0) or d.get("prevClose",0) or d.get("PrevClose",0) or 0)
            if open_val > 0 and prev_close > 0:
                return open_val, prev_close
    except: pass

    return 0, 0

def fetch_nifty_futures(cookie):
    """Fetch Nifty futures data for Chng values"""
    try:
        url="https://www.nseindia.com/api/equity-derivatives-watch?name=NIFTY"
        h={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0","Accept":"application/json, text/plain, */*","Accept-Encoding":"gzip, deflate","Accept-Language":"en-US,en;q=0.9","Referer":"https://www.nseindia.com/market-data/equity-derivatives-watch","Cookie":cookie,"X-Requested-With":"XMLHttpRequest","Connection":"keep-alive"}
        r=requests.get(url,headers=h,timeout=15)
        if r.status_code==200:
            data=r.json()
            rows=data.get("data",[])
            futures=[]
            for row in rows:
                if row.get("instrumentType","")=="Index Futures":
                    futures.append({
                        "expiry": row.get("expiryDate",""),
                        "ltp":    row.get("lastPrice",0),
                        "chng":   row.get("change",0),
                        "pchng":  row.get("pChange",0),
                    })
            return futures[:3]  # top 3
        return []
    except: return []

def parse_data(json_data):
    rec=json_data.get("records",{}); spot=rec.get("underlyingValue",0); rows=[]
    for item in rec.get("data",[]):
        ce=item.get("CE",{}); pe=item.get("PE",{})
        rows.append({"STRIKE":item.get("strikePrice",0),
            "CE_OI":   ce.get("openInterest",0),
            "CE_COI":  ce.get("changeinOpenInterest",0),
            "CE_PCOI": ce.get("pchangeinOpenInterest",0),   # ✅ % COI from NSE
            "CE_VOL":  ce.get("totalTradedVolume",0),
            "CE_IV":   ce.get("impliedVolatility",0),
            "CE_LTP":  ce.get("lastPrice",0),
            "PE_OI":   pe.get("openInterest",0),
            "PE_COI":  pe.get("changeinOpenInterest",0),
            "PE_PCOI": pe.get("pchangeinOpenInterest",0),   # ✅ % COI from NSE
            "PE_VOL":  pe.get("totalTradedVolume",0),
            "PE_IV":   pe.get("impliedVolatility",0),
            "PE_LTP":  pe.get("lastPrice",0)})
    return pd.DataFrame(rows),spot

def fmt_oi(v):
    try:
        v=float(v)
        if v>=10_000_000: return f"{v/10_000_000:.2f}Cr"
        if v>=100_000: return f"{v/100_000:.2f}L"
        return f"{int(v):,}"
    except: return str(v)

def pct(part,total):
    """%COI = COI * 100 / OI"""
    try: return f"{part/total*100:.1f}%" if total else "0%"
    except: return "0%"

def cov(coi,vol):
    try: return f"{coi/vol:.3f}" if vol else "0.000"
    except: return "0.000"

def bar_cell(value, max_val, fmt_val, color="blue"):
    pct_w = min(100, abs(value)/max_val*100) if max_val else 0
    return f'<td class="bar-cell"><div class="bar-bg-{color}" style="width:{pct_w:.1f}%"></div><span class="bar-text">{fmt_val}</span></td>'

def color_val(val, fmt):
    cls = "pos" if val >= 0 else "neg"
    return f'<span class="{cls}">{fmt}</span>'

# ── Controls ──────────────────────────────────────────────
c1,c2,c3,c4=st.columns([1,1.5,1,1])
with c1: symbol=st.selectbox("Symbol",["NIFTY","BANKNIFTY","FINNIFTY"])

# Expiry dates — live from NSE or fallback
if "expiry_dates" not in st.session_state: st.session_state.expiry_dates=[]

with c2:
    expiry_list = st.session_state.expiry_dates if st.session_state.expiry_dates else ["26-May-2026"]
    expiry=st.selectbox("Expiry Date", expiry_list)

with c3: auto_refresh=st.toggle("🔄 Auto Refresh (60s)",value=True)
with c4: manual_btn=st.button("⚡ Refresh Now",use_container_width=True)

cs1,cs2,cs3=st.columns([2,1,1])
with cs1:
    age=int(time.time()-st.session_state.cookie_time)
    if st.session_state.cookie:
        st.markdown(f'<span class="cookie-ok">🍪 Cookie OK — age: {age}s (auto every {COOKIE_REFRESH}s)</span>',unsafe_allow_html=True)
    else:
        st.markdown('<span style="color:red;font-weight:bold">🍪 Fetching cookie...</span>',unsafe_allow_html=True)
with cs2: force_cookie=st.button("🔑 Refresh Cookie",use_container_width=True)
with cs3:
    mult=st.number_input("OI Tracker Multiplier",min_value=1,max_value=1000,
        value=st.session_state.oi_multiplier,step=1,key="oi_mult")
    st.session_state.oi_multiplier=mult

# ── Cookie logic ──────────────────────────────────────────
if age>COOKIE_REFRESH or not st.session_state.cookie or force_cookie:
    with st.spinner("🍪 Getting fresh cookie..."):
        ck,_=fetch_fresh_cookie()
        if ck:
            st.session_state.cookie=ck
            st.session_state.cookie_time=time.time()
            # Fetch live expiry dates after cookie refresh
            dates=fetch_expiry_dates(symbol,ck)
            if dates: st.session_state.expiry_dates=dates

# ── Fetch data ────────────────────────────────────────────
data_age=int(time.time()-st.session_state.last_fetch)
should_fetch=manual_btn or (auto_refresh and data_age>=DATA_REFRESH) or st.session_state.raw_data is None

if should_fetch and st.session_state.cookie:
    if int(time.time()-st.session_state.cookie_time)>COOKIE_REFRESH:
        ck,_=fetch_fresh_cookie()
        if ck: st.session_state.cookie=ck; st.session_state.cookie_time=time.time()
    data,err=fetch_option_chain(symbol,expiry,st.session_state.cookie)
    if data:
        st.session_state.raw_data=data; st.session_state.last_fetch=time.time()
        _,spot=parse_data(data)
        # On first fetch — get real day open & prev close from NSE
        if st.session_state.open_price==0:
            day_open, day_prev_close = fetch_nifty_open(st.session_state.cookie)
            if day_open > 0:
                st.session_state.open_spot  = day_open
                st.session_state.open_price = mround(day_open, 50)
            else:
                # Fallback: use spot
                st.session_state.open_spot  = spot
                st.session_state.open_price = mround(spot, 50)
            # Auto-set prev_close if not already set by user
            if st.session_state.prev_close == 0 and day_prev_close > 0:
                st.session_state.prev_close = day_prev_close
        # Also update expiry dates
        dates=data.get("records",{}).get("expiryDates",[])
        if dates: st.session_state.expiry_dates=dates
        # Fetch futures
        futs=fetch_nifty_futures(st.session_state.cookie)
        if futs: st.session_state.futures=futs
    else:
        ck,_=fetch_fresh_cookie()
        if ck:
            st.session_state.cookie=ck; st.session_state.cookie_time=time.time()
            data,_=fetch_option_chain(symbol,expiry,st.session_state.cookie)
            if data: st.session_state.raw_data=data; st.session_state.last_fetch=time.time()

# Get Day Open value
open_price = st.session_state.get("open_price")

# fallback if open_price not available
if open_price is None:
    open_price = spot

# ATM/Pivot Strike = MROUND(Day Open,50)
atm_strike = mround(open_price, 50)

# ── Display ───────────────────────────────────────────────
if st.session_state.raw_data:
    df,spot=parse_data(st.session_state.raw_data)
    last=int(time.time()-st.session_state.last_fetch)
    open_strike=st.session_state.open_price
    atm_strike = mround(open_price, 50)
    multiplier=st.session_state.oi_multiplier

    open_actual = st.session_state.open_spot

    # ── Manual Open Override (always visible) ─────────────
    ov1, ov2, ov3, ov4 = st.columns([1.5, 0.8, 1.5, 0.8])
    with ov1:
        manual_open = st.number_input(
            "📂 Day Open (override if wrong):",
            min_value=0.0,
            value=float(st.session_state.open_spot) if st.session_state.open_spot > 0 else float(int(spot)),
            step=0.05, format="%.2f", key="manual_open_input"
        )
    with ov2:
        if st.button("✅ Set Open", key="set_open"):
            st.session_state.open_spot  = manual_open
            st.session_state.open_price = mround(manual_open, 50)
            st.rerun()
    with ov3:
        pc_input2 = st.number_input(
            "📌 Prev Close (override if wrong):",
            min_value=0.0,
            value=float(st.session_state.prev_close) if st.session_state.prev_close > 0 else float(int(spot)),
            step=0.05, format="%.2f", key="pc_input2"
        )
    with ov4:
        if st.button("✅ Set PC", key="set_pc2"):
            st.session_state.prev_close = pc_input2
            st.rerun()

    # Recalculate after possible override
    open_strike = st.session_state.open_price
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
        max_ce_vol_s=df_f.loc[df_f["CE_VOL"].idxmax(),"STRIKE"]
        max_pe_vol_s=df_f.loc[df_f["PE_VOL"].idxmax(),"STRIKE"]
        max_ce_oi=df_f["CE_OI"].max(); max_pe_oi=df_f["PE_OI"].max()
        max_ce_coi=df_f["CE_COI"].abs().max(); max_pe_coi=df_f["PE_COI"].abs().max()
        # Use NSE-provided pchangeinOpenInterest directly for %COI
        df_f["CE_PCT"] = df_f["CE_PCOI"]   # direct from NSE API
        df_f["PE_PCT"] = df_f["PE_PCOI"]   # direct from NSE API
        max_ce_pct = df_f["CE_PCT"].abs().max() if df_f["CE_PCT"].abs().max() > 0 else 1
        max_pe_pct = df_f["PE_PCT"].abs().max() if df_f["PE_PCT"].abs().max() > 0 else 1

        st.markdown("""<div style="display:flex;gap:20px;padding:3px 0 6px 0;font-size:13px;font-weight:600">
            <span>🟡 ATM</span><span>🟠 Open/Pivot</span>
            <span>🟢 Max Volume</span>
            <span style="color:#2E7D32">▲ COI+</span>
            <span style="color:#C62828">▼ COI−</span>
        </div>""",unsafe_allow_html=True)

        # ── HTML Table ───────────────────────────────────
        html=['<table class="oc-table"><thead><tr>']
        for h,s in [("OI","CE"),("COI","CE"),("%COI","CE"),("C/V","CE"),("VOL","CE"),("IV","CE"),("STRIKE",""),("IV","PE"),("VOL","PE"),("C/V","PE"),("%COI","PE"),("COI","PE"),("OI","PE")]:
            html.append(f'<th>{h}<br><small>{s}</small></th>')
        html.append('</tr></thead><tbody>')

        for i,row in df_f.iterrows():
            s=row["STRIKE"]; ce_coi=row["CE_COI"]; pe_coi=row["PE_COI"]
            ce_pct_r = row["CE_PCOI"]   # directly from NSE
            pe_pct_r = row["PE_PCOI"]   # directly from NSE
            rc="atm-row" if s==atm_strike else ("pivot-row" if s==open_strike else "")
            html.append(f'<tr class="{rc}">')
            html.append(bar_cell(row["CE_OI"],max_ce_oi,fmt_oi(row["CE_OI"]),"blue"))
            coi_c="green" if ce_coi>=0 else "red"
            ce_coi_fmt=f'<span style="color:{"#2E7D32" if ce_coi>=0 else "#C62828"};font-weight:800">{fmt_oi(ce_coi)}</span>'
            html.append(f'<td class="bar-cell"><div class="bar-bg-{coi_c}" style="width:{min(100,abs(ce_coi)/max_ce_coi*100 if max_ce_coi else 0):.1f}%"></div><span class="bar-text">{ce_coi_fmt}</span></td>')
            html.append(f'<td class="bar-cell"><div class="bar-bg-orange" style="width:{min(100,abs(ce_pct_r)/max_ce_pct*100 if max_ce_pct else 0):.1f}%"></div><span class="bar-text">{ce_pct_r:.1f}%</span></td>')
            html.append(f'<td>{cov(ce_coi,row["CE_VOL"])}</td>')
            vc="vol-max" if s==max_ce_vol_s else ""
            html.append(f'<td class="{vc}">{fmt_oi(row["CE_VOL"])}</td>')
            html.append(f'<td>{row["CE_IV"]:.1f}</td>')
            html.append(f'<td class="strike-col">{int(s)}</td>')
            html.append(f'<td>{row["PE_IV"]:.1f}</td>')
            vp="vol-max" if s==max_pe_vol_s else ""
            html.append(f'<td class="{vp}">{fmt_oi(row["PE_VOL"])}</td>')
            html.append(f'<td>{cov(pe_coi,row["PE_VOL"])}</td>')
            html.append(f'<td class="bar-cell"><div class="bar-bg-orange" style="width:{min(100,abs(pe_pct_r)/max_pe_pct*100 if max_pe_pct else 0):.1f}%"></div><span class="bar-text">{pe_pct_r:.1f}%</span></td>')
            pe_coi_fmt=f'<span style="color:{"#2E7D32" if pe_coi>=0 else "#C62828"};font-weight:800">{fmt_oi(pe_coi)}</span>'
            html.append(f'<td class="bar-cell"><div class="bar-bg-{"green" if pe_coi>=0 else "red"}" style="width:{min(100,abs(pe_coi)/max_pe_coi*100 if max_pe_coi else 0):.1f}%"></div><span class="bar-text">{pe_coi_fmt}</span></td>')
            html.append(bar_cell(row["PE_OI"],max_pe_oi,fmt_oi(row["PE_OI"]),"blue"))
            html.append('</tr>')

        # Total row
        html.append('<tr class="total-row">')
        for v in [fmt_oi(tot["CE_OI"]),fmt_oi(tot["CE_COI"]),"100%",
                  cov(tot["CE_COI"],tot["CE_VOL"]),fmt_oi(tot["CE_VOL"]),"—",
                  "▼ TOTAL","—",fmt_oi(tot["PE_VOL"]),
                  cov(tot["PE_COI"],tot["PE_VOL"]),"100%",
                  fmt_oi(tot["PE_COI"]),fmt_oi(tot["PE_OI"])]:
            html.append(f'<td>{v}</td>')
        html.append('</tr></tbody></table>')
        st.markdown("".join(html),unsafe_allow_html=True)

        # ── Calculations ──────────────────────────────────
        # Max Pain
        mp_data=[]
        for s in df_f["STRIKE"]:
            mp_data.append({"STRIKE":s,"LOSS":((s-df_f["STRIKE"]).clip(lower=0)*df_f["CE_OI"]).sum()+((df_f["STRIKE"]-s).clip(lower=0)*df_f["PE_OI"]).sum()})
        mp_df=pd.DataFrame(mp_data)
        max_pain=mp_df.loc[mp_df["LOSS"].idxmin(),"STRIKE"]

        support=df_f.loc[df_f["PE_OI"].idxmax(),"STRIKE"]
        resistance=df_f.loc[df_f["CE_OI"].idxmax(),"STRIKE"]
        top_sup=df_f.nlargest(2,"PE_OI")["STRIKE"].tolist()
        top_res=df_f.nlargest(2,"CE_OI")["STRIKE"].tolist()
        pcr_oi_v=tot["PE_OI"]/tot["CE_OI"] if tot["CE_OI"] else 0
        trend="Sideways ↔" if 0.8<=pcr_oi_v<=1.2 else ("Bullish 📈" if pcr_oi_v>1.2 else "Bearish 📉")
        atm_r=df_f.iloc[(abs(df_f["STRIKE"]-atm_strike)).argmin()]
        ce_ca=atm_r["CE_COI"]; pe_ca=atm_r["PE_COI"]
        signal=("Long Build-up 📈" if pe_ca>0 and ce_ca<=0 else
                "Short Build-up 📉" if ce_ca>0 and pe_ca<=0 else
                "Both Rising ↔" if pe_ca>0 and ce_ca>0 else "Both Falling ⚠️")

        st.markdown('<div class="section-hdr">🧮 Analysis</div>',unsafe_allow_html=True)
        a1,a2,a3,a4=st.columns(4)
        a1.metric("📌 Max Pain",f"{int(max_pain)}")
        a2.metric("📌 Support",f"{int(support)}",delta=f"2nd: {int(top_sup[1])}" if len(top_sup)>1 else "")
        a3.metric("📌 Resistance",f"{int(resistance)}",delta=f"2nd: {int(top_res[1])}" if len(top_res)>1 else "")
        a4.metric("📌 Trend",trend)
        st.info(f"ATM Signal: {signal}  |  Expected Range: {int(support)} → {int(resistance)}")

        # ── Live Metrics ──────────────────────────────────
        st.markdown('<div class="section-hdr">📡 Live Metrics</div>',unsafe_allow_html=True)
        now_t=datetime.now().strftime("%H:%M:%S")

        # ── Prev Close (fixed at first fetch, never changes) ──
        if st.session_state.prev_close == 0:
            st.session_state.prev_close = spot  # set once at app start
        prev_close = st.session_state.prev_close

        # Chng = Spot - Prev Close (fixed baseline)
        chng = round(spot - prev_close, 2)

        # Avijit OP = (Sum of PE COI/VOL - Sum of CE COI/VOL) * 65
        df_f["CE_COV"] = df_f.apply(lambda r: r["CE_COI"]/r["CE_VOL"] if r["CE_VOL"] else 0, axis=1)
        df_f["PE_COV"] = df_f.apply(lambda r: r["PE_COI"]/r["PE_VOL"] if r["PE_VOL"] else 0, axis=1)
        avijit_op = round((df_f["PE_COV"].sum() - df_f["CE_COV"].sum()) * 65, 2)

        # OI Tracker = ((Total PE OI - Total CE OI) / 100000) * multiplier
        oi_tracker = round(((tot["PE_OI"] - tot["CE_OI"]) / 100000) * multiplier, 2)

        pcr_v   = round(tot["PE_OI"]/tot["CE_OI"], 4) if tot["CE_OI"] else 0
        pe_iv_sum = round(df_f["PE_IV"].sum(), 2)
        ce_iv_sum = round(df_f["CE_IV"].sum(), 2)

        # ── COI Growth formula (matches Excel W5/X5) ──────
        # W5 = IFERROR(((T5)/(IFERROR(IF(S5>0,T5-S5,T5+(-S5)),""))-1)
        #       * SIGN(IFERROR(IF(S5>0,T5-S5,T5+(-S5)),""),""))*100
        # Where T5=PE_OI, S5=PE_COI
        # Simplified: ((OI / |COI|) - 1) * SIGN(COI) * 100
        def coi_growth_formula(oi, coi):
            try:
                if coi == 0 or oi == 0: return 0.0
                change = coi if coi > 0 else -coi   # abs(COI) = T5-S5 or T5+(-S5)
                val = ((oi / change) - 1) * (1 if coi > 0 else -1) * 100
                return round(val, 4)
            except: return 0.0

        df_f["PE_GR"] = df_f.apply(lambda r: coi_growth_formula(r["PE_OI"], r["PE_COI"]), axis=1)
        df_f["CE_GR"] = df_f.apply(lambda r: coi_growth_formula(r["CE_OI"], r["CE_COI"]), axis=1)

        # PE COI Growth = SUM(W5:W15) = all strikes in range
        pe_coi_g_local = round(df_f["PE_GR"].sum(), 2)
        # CE COI Growth = SUM(X5:X15) = all strikes in range
        ce_coi_g_local = round(df_f["CE_GR"].sum(), 2)

        # ITM PE = SUM(R10:R15) = PE_GR for ATM strike and 5 below (put ITM)
        # ITM CE = SUM(D5:D10) = CE_GR for ATM strike and 5 above (call ITM)
        atm_idx_f = (abs(df_f["STRIKE"] - atm_strike)).argmin()
        itm_pe_rows = df_f.iloc[max(0, atm_idx_f):min(len(df_f), atm_idx_f+6)]
        itm_ce_rows = df_f.iloc[max(0, atm_idx_f-5):atm_idx_f+1]
        itm_pe_local = round(itm_pe_rows["PE_GR"].sum(), 2)
        itm_ce_local = round(itm_ce_rows["CE_GR"].sum(), 2)

        # ── Use Detailed Calculations page values if available (more accurate) ──
        pe_coi_g = st.session_state.get("dc_pe_growth_total", pe_coi_g_local)
        ce_coi_g = st.session_state.get("dc_ce_growth_total", ce_coi_g_local)
        itm_pe   = st.session_state.get("dc_itm_pe",          itm_pe_local)
        itm_ce   = st.session_state.get("dc_itm_ce",          itm_ce_local)

        # Store prev_df for future use (not needed for this formula but kept for compatibility)
        st.session_state.prev_df = df_f[["STRIKE","CE_OI","CE_COI","CE_VOL","PE_OI","PE_COI","PE_VOL","CE_PCOI","PE_PCOI"]].copy()

        # Prev Close input (fixed once per session)
        if st.session_state.prev_close == 0:
            pc_col1, pc_col2 = st.columns([2,3])
            with pc_col1:
                pc_input = st.number_input("📌 Enter Previous Close (fixed):",
                    min_value=0.0, value=float(int(spot)), step=0.05, format="%.2f",
                    key="pc_input")
            with pc_col2:
                if st.button("✅ Set Prev Close", key="set_pc"):
                    st.session_state.prev_close = pc_input
                    st.rerun()
            chng = 0.0
        else:
            chng = round(spot - st.session_state.prev_close, 2)
            st.caption(f"📌 Prev Close: ₹{st.session_state.prev_close:,.2f} (fixed) | Chng = {st.session_state.prev_close:,.2f} − {spot:,.2f} = {chng:+.2f}")

        # Futures data
        futs=st.session_state.futures
        fut1_c=futs[0]["chng"] if len(futs)>0 else 0
        fut2_c=futs[1]["chng"] if len(futs)>1 else 0
        fut3_c=futs[2]["chng"] if len(futs)>2 else 0
        fut1_e=futs[0]["expiry"][:6] if len(futs)>0 else "Fut1"
        fut2_e=futs[1]["expiry"][:6] if len(futs)>1 else "Fut2"
        fut3_e=futs[2]["expiry"][:6] if len(futs)>2 else "Fut3"

        r1=st.columns(6)
        r1[0].metric("📍 Spot",f"₹{spot:,.2f}")
        r1[1].metric("📉 Chng",f"{chng:+.2f}",delta="▲ Prev" if chng>=0 else "▼ Prev",delta_color="normal" if chng>=0 else "inverse")
        r1[2].metric("🕐 Time",now_t)
        r1[3].metric("🎯 Avijit OP",f"{avijit_op:,.2f}",delta="Bull" if avijit_op>=0 else "Bear",delta_color="normal" if avijit_op>=0 else "inverse")
        r1[4].metric("📊 OI Tracker",f"{oi_tracker:,.2f}",delta="Bull" if oi_tracker>=0 else "Bear",delta_color="normal" if oi_tracker>=0 else "inverse")
        r1[5].metric("⚖️ PCR",f"{pcr_v:.4f}",delta="Bull" if pcr_v>=1 else "Bear",delta_color="normal" if pcr_v>=1 else "inverse")

        r2=st.columns(6)
        r2[0].metric("📈 PE IV Fluct",f"{pe_iv_sum:.1f}")
        r2[1].metric("📉 CE IV Fluct",f"{ce_iv_sum:.1f}")
        r2[2].metric("🔺 PE COI Growth",f"{pe_coi_g:+.2f}",delta="▲" if pe_coi_g>=0 else "▼",delta_color="normal" if pe_coi_g>=0 else "inverse")
        r2[3].metric("🔻 CE COI Growth",f"{ce_coi_g:+.2f}",delta="▲" if ce_coi_g>=0 else "▼",delta_color="normal" if ce_coi_g>=0 else "inverse")
        r2[4].metric("💰 ITM PE",f"{itm_pe:+.2f}")
        r2[5].metric("💰 ITM CE",f"{itm_ce:+.2f}")

        # Futures row
        st.markdown('<div class="section-hdr">📊 Nifty Futures</div>',unsafe_allow_html=True)
        f1,f2,f3=st.columns(3)
        f1.metric(f"🔵 Fut {fut1_e}",f"{futs[0]['ltp']:,.2f}" if futs else "—",
                  delta=f"{fut1_c:+.2f}" if futs else "",
                  delta_color="normal" if fut1_c>=0 else "inverse")
        f2.metric(f"🔵 Fut {fut2_e}",f"{futs[1]['ltp']:,.2f}" if len(futs)>1 else "—",
                  delta=f"{fut2_c:+.2f}" if len(futs)>1 else "",
                  delta_color="normal" if fut2_c>=0 else "inverse")
        f3.metric(f"🔵 Fut {fut3_e}",f"{futs[2]['ltp']:,.2f}" if len(futs)>2 else "—",
                  delta=f"{fut3_c:+.2f}" if len(futs)>2 else "",
                  delta_color="normal" if fut3_c>=0 else "inverse")

        # ── Recording Controls ────────────────────────────
        rc1,rc2,rc3=st.columns([1,1,2])
        with rc1:
            if st.button("▶ Start Recording" if not st.session_state.recording else "⏹ Stop Recording",
                         use_container_width=True,
                         type="primary" if not st.session_state.recording else "secondary"):
                st.session_state.recording=not st.session_state.recording
                if st.session_state.recording:
                    st.success("✅ Recording started!")
                else:
                    st.warning("⏹ Recording stopped.")
        with rc2:
            if st.button("🗑 Clear History",use_container_width=True):
                st.session_state.history=[]
                st.info("History cleared.")
        with rc3:
            st.caption(f"{'🔴 Recording ON' if st.session_state.recording else '⚪ Recording OFF'} — {len(st.session_state.history)} rows saved")

        # Only record when recording is ON
        if st.session_state.recording:
            rec={
                "Time":now_t,"Spot":spot,"Chng":chng,
                "Avijit OP":avijit_op,"OI Tracker":oi_tracker,"PCR":pcr_v,
                "PE IV":pe_iv_sum,"CE IV":ce_iv_sum,
                "PE COI Gr":pe_coi_g,"CE COI Gr":ce_coi_g,
                "ITM PE":itm_pe,"ITM CE":itm_ce,
                "F1 Chng":round(fut1_c,2),"F2 Chng":round(fut2_c,2),"F3 Chng":round(fut3_c,2),
            }
            st.session_state.history.append(rec)
            if len(st.session_state.history)>30:
                st.session_state.history=st.session_state.history[-30:]

        st.markdown('<div class="section-hdr">🗂️ Recording (Last 30 — Newest First)</div>',unsafe_allow_html=True)
        hist=list(reversed(st.session_state.history))

        def grade_color(val, all_vals, reverse=False):
            """Excel-style graded 3-color scale: Red(low)→Yellow(mid)→Green(high)"""
            try:
                vals=[float(v) for v in all_vals if v is not None]
                vals=[v for v in vals if v==v]  # remove NaN
                if not vals or max(vals)==min(vals): return "#FFFDE7"
                mn,mx=min(vals),max(vals)
                mid=(mn+mx)/2
                v=float(val)
                if reverse:
                    # Reverse: high value = red (bad for CE side)
                    v = mn + mx - v
                if v <= mid:
                    ratio = (v-mn)/(mid-mn) if (mid-mn)!=0 else 0
                    ratio = max(0, min(1, ratio))
                    r=255; g=int(255*ratio); b=0
                else:
                    ratio = (v-mid)/(mx-mid) if (mx-mid)!=0 else 1
                    ratio = max(0, min(1, ratio))
                    r=int(255*(1-ratio)); g=int(180+75*ratio); b=0
                # Make text dark for readability
                return f"rgb({r},{g},{b})"
            except: return "#FFFDE7"

        cols=["Time","Spot","Chng","Avijit OP","OI Tracker","PCR","PE IV","CE IV","PE COI Gr","CE COI Gr","ITM PE","ITM CE","F1 Chng","F2 Chng","F3 Chng"]
        # Pre-collect column values for grading
        col_vals={c:[row[c] for row in hist] for c in cols}

        rec_html=['<table class="rec-table"><thead><tr>']
        for c in cols: rec_html.append(f'<th>{c}</th>')
        rec_html.append('</tr></thead><tbody>')

        grade_cols={"Chng":False,"Avijit OP":False,"OI Tracker":False,
                    "PCR":False,"PE IV":False,"CE IV":True,
                    "PE COI Gr":False,"CE COI Gr":True,"ITM PE":False,"ITM CE":True,
                    "F1 Chng":False,"F2 Chng":False,"F3 Chng":False}

        for idx,row in enumerate(hist):
            rec_html.append('<tr>')
            for c in cols:
                v=row[c]
                if c=="Time":
                    rec_html.append(f'<td><b>{v}</b></td>')
                elif c=="Spot":
                    rec_html.append(f'<td><b>₹{v:,.2f}</b></td>')
                elif c in grade_cols:
                    bg=grade_color(v, col_vals[c], reverse=grade_cols[c])
                    if c in ["Chng","Avijit OP","OI Tracker","PE COI Gr","CE COI Gr"]:
                        fmt=f"{float(v):+.2f}"
                    elif c=="PCR":
                        fmt=f"{float(v):.4f}"
                    else:
                        fmt=f"{float(v):.2f}"
                    rec_html.append(f'<td style="background:{bg};font-weight:700">{fmt}</td>')
                else:
                    rec_html.append(f'<td>{v}</td>')
            rec_html.append('</tr>')

        rec_html.append('</tbody></table>')
        st.markdown("".join(rec_html),unsafe_allow_html=True)

        # Download CSV
        hist_df=pd.DataFrame(hist)
        csv=hist_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download History CSV",csv,"nifty_oc_history.csv","text/csv")

    if auto_refresh:
        nxt=max(0,DATA_REFRESH-int(time.time()-st.session_state.last_fetch))
        st.caption(f"⏱ Next auto-refresh in {nxt}s")
        time.sleep(nxt)
        st.rerun()

else:
    st.info("⏳ Loading data...")
    time.sleep(2)
    st.rerun()
