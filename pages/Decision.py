import streamlit as st
import math
import time
from datetime import datetime

st.set_page_config(page_title="Decision — Buy/Sell Qty", page_icon="🛒", layout="wide")

# ── Shared helpers (duplicated from app.py so this page is self-contained) ─────
def mround(val, multiple):
    return math.floor(val / multiple + 0.5) * multiple

def fmt_oi(v):
    try:
        v = float(v)
        if v >= 10_000_000: return f"{v/10_000_000:.2f}Cr"
        if v >= 100_000:    return f"{v/100_000:.2f}L"
        return f"{int(v):,}"
    except:
        return str(v)

def bar_cell(value, max_val, fmt_val, color="blue"):
    pct_w = min(100, abs(value) / max_val * 100) if max_val else 0
    return (
        f'<td class="bar-cell">'
        f'<div class="bar-bg-{color}" style="width:{pct_w:.1f}%"></div>'
        f'<span class="bar-text">{fmt_val}</span>'
        f'</td>'
    )

def net_cell(buy, sell, max_net):
    net   = buy - sell
    pct   = min(100, abs(net) / max_net * 100) if max_net else 0
    color = "#2E7D32" if net >= 0 else "#C62828"
    bg    = "rgba(46,125,50,0.18)" if net >= 0 else "rgba(198,40,40,0.18)"
    sign  = "+" if net >= 0 else ""
    return (
        f'<td class="bar-cell">'
        f'<div style="position:absolute;left:0;top:0;bottom:0;width:{pct:.1f}%;background:{bg};border-radius:2px;z-index:0"></div>'
        f'<span class="bar-text" style="color:{color};font-weight:800">{sign}{fmt_oi(net)}</span>'
        f'</td>'
    )

def chng_cell(chng, max_chng):
    pct   = min(100, abs(chng) / max_chng * 100) if max_chng else 0
    color = "#2E7D32" if chng >= 0 else "#C62828"
    bg    = "rgba(46,125,50,0.15)" if chng >= 0 else "rgba(198,40,40,0.15)"
    sign  = "+" if chng >= 0 else ""
    return (
        f'<td class="bar-cell">'
        f'<div style="position:absolute;left:0;top:0;bottom:0;width:{pct:.1f}%;background:{bg};border-radius:2px;z-index:0"></div>'
        f'<span class="bar-text" style="color:{color};font-weight:800">{sign}{chng:.4f}</span>'
        f'</td>'
    )

# ── Styles ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .spot-bar {
        background:linear-gradient(90deg,#1565C0,#1976D2);
        padding:10px 18px; border-radius:10px; color:white;
        font-size:15px; font-weight:bold; margin-bottom:12px;
    }
    .oc-table { width:100%; border-collapse:collapse; font-size:13px; font-weight:600; }
    .oc-table th {
        background:#1565C0; color:white; padding:6px 4px;
        text-align:center; font-size:11px; font-weight:700;
        border:1px solid #1976D2;
    }
    .oc-table td {
        padding:4px 5px; text-align:center; border:1px solid #E0E0E0;
        font-size:13px; font-weight:600; white-space:nowrap;
    }
    .oc-table tr:hover td { filter:brightness(0.96); }
    .strike-col  { background:#1565C0 !important; color:white !important; font-weight:800 !important; font-size:14px !important; }
    .atm-row  td { background:#FFF9C4 !important; font-weight:800 !important; }
    .pivot-row td{ background:#FFE0B2 !important; font-weight:800 !important; }
    .total-row td{ background:#1565C0 !important; color:white !important; font-weight:800 !important; font-size:13px !important; }
    .bar-cell    { position:relative; min-width:65px; }
    .bar-bg-blue  { position:absolute; left:0; top:0; bottom:0; background:rgba(21,101,192,0.20); border-radius:2px; z-index:0; }
    .bar-bg-green { position:absolute; left:0; top:0; bottom:0; background:rgba(46,125,50,0.20);  border-radius:2px; z-index:0; }
    .bar-bg-red   { position:absolute; left:0; top:0; bottom:0; background:rgba(198,40,40,0.20);  border-radius:2px; z-index:0; }
    .bar-text     { position:relative; z-index:1; }
    .signal-box   {
        padding:16px 24px; border-radius:12px; font-size:22px; font-weight:800;
        text-align:center; margin:14px 0; letter-spacing:0.5px;
    }
    .sig-strong-bull { background:#C8E6C9; color:#1B5E20; border:2px solid #2E7D32; }
    .sig-bull        { background:#DCEDC8; color:#33691E; border:2px solid #558B2F; }
    .sig-neutral     { background:#FFF9C4; color:#F57F17; border:2px solid #F9A825; }
    .sig-bear        { background:#FFCDD2; color:#B71C1C; border:2px solid #C62828; }
    .sig-strong-bear { background:#FFCDD2; color:#7F0000; border:2px solid #B71C1C; }
    div[data-testid="metric-container"] {
        background:#F8F9FA; border:1px solid #E0E0E0;
        border-radius:8px; padding:8px !important; text-align:center;
    }
    div[data-testid="stMetricValue"] { font-size:20px !important; font-weight:800 !important; color:#1565C0 !important; }
    div[data-testid="stMetricLabel"] { font-size:12px !important; font-weight:700 !important; }
    .pos { color:#2E7D32; font-weight:800; }
    .neg { color:#C62828; font-weight:800; }
    .legend-row { display:flex; gap:18px; padding:5px 0 8px 0; font-size:12px; font-weight:600; flex-wrap:wrap; }
</style>
""", unsafe_allow_html=True)

# ── Page title ──────────────────────────────────────────────────────────────────
st.title("🛒 Decision — Buy / Sell Qty")

# ── Guard: need raw_data from main app ─────────────────────────────────────────
if not st.session_state.get("raw_data"):
    st.warning("⚠️ No data yet. Please open the main **Nifty Option Chain** page first so data is loaded, then come back here.")
    st.stop()

# ── Pull shared state ───────────────────────────────────────────────────────────
raw_data    = st.session_state.raw_data
open_price  = st.session_state.get("open_price", 0)
open_spot   = st.session_state.get("open_spot",  0)
last_fetch  = st.session_state.get("last_fetch",  0)
prev_close  = st.session_state.get("prev_close",  0)

# ── Parse ───────────────────────────────────────────────────────────────────────
import pandas as pd

rec  = raw_data.get("records", {})
spot = rec.get("underlyingValue", 0)
rows = []
for item in rec.get("data", []):
    ce = item.get("CE", {})
    pe = item.get("PE", {})
    rows.append({
        "STRIKE":   item.get("strikePrice", 0),
        # LTP & change
        "CE_LTP":   ce.get("lastPrice", 0),
        # Change (absolute ₹ price change — NSE field: "change")
        "CE_CHNG":  float(ce.get("change") or 0),
        "PE_LTP":   pe.get("lastPrice", 0),
        "PE_CHNG":  float(pe.get("change") or 0),
        # Buy / Sell Qty
        "CE_BUY":   ce.get("totalBuyQuantity",  0),
        "CE_SELL":  ce.get("totalSellQuantity", 0),
        "PE_BUY":   pe.get("totalBuyQuantity",  0),
        "PE_SELL":  pe.get("totalSellQuantity", 0),
        # OI (needed for PCR signal)
        "CE_OI":    ce.get("openInterest", 0),
        "PE_OI":    pe.get("openInterest", 0),
    })

df = pd.DataFrame(rows)

atm_strike  = mround(spot, 50)
open_strike = open_price if open_price > 0 else atm_strike
lo = open_strike - 250
hi = open_strike + 250
df_f = df[(df["STRIKE"] >= lo) & (df["STRIKE"] <= hi)].copy().reset_index(drop=True)

if df_f.empty:
    st.warning("No strike data in ±250 range.")
    st.stop()

# ── Spot bar ────────────────────────────────────────────────────────────────────
chng_spot = round(spot - prev_close, 2) if prev_close > 0 else 0
last_s    = int(time.time() - last_fetch)
st.markdown(f'''<div class="spot-bar">
    📊 LTP: <b>₹{spot:,.2f}</b> &nbsp;|&nbsp;
    Chng: <b>{chng_spot:+.2f}</b> &nbsp;|&nbsp;
    Day Open: <b>₹{open_spot:,.2f}</b> &nbsp;|&nbsp;
    Pivot: <b>₹{open_strike:,}</b> &nbsp;|&nbsp;
    ATM: <b>₹{atm_strike:,}</b> &nbsp;|&nbsp;
    Updated: {last_s}s ago
</div>''', unsafe_allow_html=True)

# ── Totals ──────────────────────────────────────────────────────────────────────
tot_ce_buy   = df_f["CE_BUY"].sum()
tot_ce_sell  = df_f["CE_SELL"].sum()
tot_pe_buy   = df_f["PE_BUY"].sum()
tot_pe_sell  = df_f["PE_SELL"].sum()
tot_ce_oi    = df_f["CE_OI"].sum()
tot_pe_oi    = df_f["PE_OI"].sum()

import numpy as np

def excel_trend(series):
    """Equivalent of Excel =TREND(values) — linear regression, returns predicted value at last position."""
    vals = [float(v) for v in series if v is not None]
    if len(vals) < 2:
        return vals[0] if vals else 0.0
    x = np.arange(1, len(vals) + 1, dtype=float)
    coeffs = np.polyfit(x, vals, 1)          # slope, intercept
    return round(float(np.polyval(coeffs, len(vals))), 7)  # predict at last x

tot_ce_chng  = excel_trend(df_f["CE_CHNG"].values)
tot_pe_chng  = excel_trend(df_f["PE_CHNG"].values)

ce_bs  = round(tot_ce_buy  / tot_ce_sell,  3) if tot_ce_sell  else 0
pe_bs  = round(tot_pe_buy  / tot_pe_sell,  3) if tot_pe_sell  else 0
pcr    = round(tot_pe_oi   / tot_ce_oi,    4) if tot_ce_oi    else 0

# ── Signal logic ────────────────────────────────────────────────────────────────
# Combines PCR + CE B/S ratio + PE B/S ratio for a composite signal
# High PE B/S (put buyers > sellers) = bearish pressure
# High CE B/S (call buyers > sellers) = bullish pressure
# PCR > 1 = more puts written = bullish (writers selling puts = expect up)

def compute_signal(pcr, ce_bs, pe_bs):
    score = 0
    # PCR component (-2 to +2)
    if   pcr >= 1.5:  score += 2
    elif pcr >= 1.2:  score += 1
    elif pcr <= 0.5:  score -= 2
    elif pcr <= 0.8:  score -= 1

    # CE B/S: more CE buyers = bullish (+1), more CE sellers = bearish (-1)
    if ce_bs >= 1.1:  score += 1
    elif ce_bs <= 0.9: score -= 1

    # PE B/S: more PE buyers = bearish (-1), more PE sellers = bullish (+1)
    if pe_bs >= 1.1:  score -= 1
    elif pe_bs <= 0.9: score += 1

    if   score >= 3:  return "⬆️ Strong Buy CE (Bullish)",  "sig-strong-bull"
    elif score >= 1:  return "↗️ Buy CE (Mild Bullish)",     "sig-bull"
    elif score <= -3: return "⬇️ Strong Buy PE (Bearish)",  "sig-strong-bear"
    elif score <= -1: return "↘️ Buy PE (Mild Bearish)",     "sig-bear"
    else:             return "↔️ Neutral",                   "sig-neutral"

signal_text, signal_cls = compute_signal(pcr, ce_bs, pe_bs)

# ── Signal box ──────────────────────────────────────────────────────────────────
st.markdown(f'<div class="signal-box {signal_cls}">🎯 Signal: {signal_text}</div>',
            unsafe_allow_html=True)

# ── Metrics row ─────────────────────────────────────────────────────────────────
m1, m2, m3, m4, m5, m6, m7, m8, m9 = st.columns(9)
m1.metric("CE Buy Qty",   fmt_oi(tot_ce_buy))
m2.metric("CE Sell Qty",  fmt_oi(tot_ce_sell))
m3.metric("CE B/S Ratio", f"{ce_bs:.3f}",
          delta="Buyers lead" if ce_bs >= 1 else "Sellers lead",
          delta_color="normal" if ce_bs >= 1 else "inverse")
m4.metric("CE Chng (Σ)",  f"{tot_ce_chng:+.4f}",
          delta_color="normal" if tot_ce_chng >= 0 else "inverse")
m5.metric("PCR", f"{pcr:.4f}")
m6.metric("PE Chng (Σ)",  f"{tot_pe_chng:+.4f}",
          delta_color="normal" if tot_pe_chng >= 0 else "inverse")
m7.metric("PE Buy Qty",   fmt_oi(tot_pe_buy))
m8.metric("PE Sell Qty",  fmt_oi(tot_pe_sell))
m9.metric("PE B/S Ratio", f"{pe_bs:.3f}",
          delta="Buyers lead" if pe_bs >= 1 else "Sellers lead",
          delta_color="normal" if pe_bs >= 1 else "inverse")

# ── Legend ──────────────────────────────────────────────────────────────────────
st.markdown("""<div class="legend-row">
    <span>🟡 ATM</span><span>🟠 Pivot/Open</span>
    <span style="color:#1565C0">■ Buy Qty bar</span>
    <span style="color:#C62828">■ Sell Qty bar</span>
    <span style="color:#2E7D32">■ Net Buy / CE Chng+</span>
    <span style="color:#B71C1C">■ Net Sell / CE Chng−</span>
    <span style="color:#555">CHNG = absolute ₹ price change (NSE field)</span>
</div>""", unsafe_allow_html=True)

# ── Max values for bar scaling ───────────────────────────────────────────────────
max_ce_buy   = df_f["CE_BUY"].max()   or 1
max_ce_sell  = df_f["CE_SELL"].max()  or 1
max_pe_buy   = df_f["PE_BUY"].max()   or 1
max_pe_sell  = df_f["PE_SELL"].max()  or 1
max_ce_net   = df_f.apply(lambda r: abs(r["CE_BUY"] - r["CE_SELL"]), axis=1).max() or 1
max_pe_net   = df_f.apply(lambda r: abs(r["PE_BUY"] - r["PE_SELL"]), axis=1).max() or 1
max_ce_chng  = df_f["CE_CHNG"].abs().max() or 1
max_pe_chng  = df_f["PE_CHNG"].abs().max() or 1

# ── HTML Table ───────────────────────────────────────────────────────────────────
# Columns: CE LTP(Chng) | CE BUY | CE SELL | CE NET | CE B/S || STRIKE || PE B/S | PE NET | PE SELL | PE BUY | PE LTP(Chng)
html = ['<table class="oc-table"><thead><tr>']
headers = [
    ("CHNG",     "CE"),
    ("BUY QTY",  "CE"),
    ("SELL QTY", "CE"),
    ("NET",      "CE"),
    ("B/S",      "CE"),
    ("STRIKE",   ""),
    ("B/S",      "PE"),
    ("NET",      "PE"),
    ("SELL QTY", "PE"),
    ("BUY QTY",  "PE"),
    ("CHNG",     "PE"),
]
for h_lbl, h_side in headers:
    html.append(f'<th>{h_lbl}<br><small style="font-weight:500">{h_side}</small></th>')
html.append('</tr></thead><tbody>')

for _, row in df_f.iterrows():
    s        = row["STRIKE"]
    ce_buy   = row["CE_BUY"];   ce_sell  = row["CE_SELL"]
    pe_buy   = row["PE_BUY"];   pe_sell  = row["PE_SELL"]
    ce_chng  = row["CE_CHNG"]
    pe_chng  = row["PE_CHNG"]
    ce_ratio = f"{ce_buy/ce_sell:.2f}" if ce_sell else "—"
    pe_ratio = f"{pe_buy/pe_sell:.2f}" if pe_sell else "—"
    rc       = "atm-row" if s == atm_strike else ("pivot-row" if s == open_strike else "")

    ce_r_col = "#1565C0" if ce_buy >= ce_sell else "#C62828"
    pe_r_col = "#1565C0" if pe_buy >= pe_sell else "#C62828"

    html.append(f'<tr class="{rc}">')
    html.append(chng_cell(ce_chng, max_ce_chng))                                 # CE Chng
    html.append(bar_cell(ce_buy,  max_ce_buy,  fmt_oi(ce_buy),  "blue"))         # CE Buy
    html.append(bar_cell(ce_sell, max_ce_sell, fmt_oi(ce_sell), "red"))          # CE Sell
    html.append(net_cell(ce_buy, ce_sell, max_ce_net))                           # CE Net
    html.append(f'<td style="color:{ce_r_col};font-weight:800">{ce_ratio}</td>') # CE B/S
    html.append(f'<td class="strike-col">{int(s)}</td>')                         # Strike
    html.append(f'<td style="color:{pe_r_col};font-weight:800">{pe_ratio}</td>') # PE B/S
    html.append(net_cell(pe_buy, pe_sell, max_pe_net))                           # PE Net
    html.append(bar_cell(pe_sell, max_pe_sell, fmt_oi(pe_sell), "red"))          # PE Sell
    html.append(bar_cell(pe_buy,  max_pe_buy,  fmt_oi(pe_buy),  "green"))        # PE Buy
    html.append(chng_cell(pe_chng, max_pe_chng))                                 # PE Chng
    html.append('</tr>')

# Totals row
tot_ce_net     = tot_ce_buy - tot_ce_sell
tot_pe_net     = tot_pe_buy - tot_pe_sell
ce_net_sign    = "+" if tot_ce_net >= 0 else ""
pe_net_sign    = "+" if tot_pe_net >= 0 else ""
html.append('<tr class="total-row">')
ce_chng_sign = "+" if tot_ce_chng >= 0 else ""
pe_chng_sign = "+" if tot_pe_chng >= 0 else ""
html.append(f'<td>{ce_chng_sign}{tot_ce_chng:.4f}</td>')
html.append(f'<td>{fmt_oi(tot_ce_buy)}</td>')
html.append(f'<td>{fmt_oi(tot_ce_sell)}</td>')
html.append(f'<td>{ce_net_sign}{fmt_oi(tot_ce_net)}</td>')
html.append(f'<td>{ce_bs:.3f}</td>')
html.append('<td>TOTAL</td>')
html.append(f'<td>{pe_bs:.3f}</td>')
html.append(f'<td>{pe_net_sign}{fmt_oi(tot_pe_net)}</td>')
html.append(f'<td>{fmt_oi(tot_pe_sell)}</td>')
html.append(f'<td>{fmt_oi(tot_pe_buy)}</td>')
html.append(f'<td>{pe_chng_sign}{tot_pe_chng:.4f}</td>')
html.append('</tr></tbody></table>')

st.markdown("".join(html), unsafe_allow_html=True)

# ── Signal explanation ──────────────────────────────────────────────────────────
st.markdown("""
<div style="background:#F8F9FA;border:1px solid #E0E0E0;border-radius:8px;
            padding:14px 18px;margin-top:18px;font-size:13px;line-height:1.7">
<b>📖 Signal Logic (3 factors combined)</b><br>
<b>PCR</b> — Put/Call OI ratio. &gt;1.2 bullish (put writers dominant); &lt;0.8 bearish.<br>
<b>CE B/S Ratio</b> — Call Buy÷Sell. &gt;1.1 = active call buying = bullish. &lt;0.9 = call selling pressure = bearish.<br>
<b>PE B/S Ratio</b> — Put Buy÷Sell. &gt;1.1 = active put buying = bearish. &lt;0.9 = put selling (writing) = bullish.<br><br>
<b>CHNG</b> — Absolute ₹ price change of the option from previous close (NSE <code>change</code> field).
<span style="color:#2E7D32">Green = premium rising</span> &nbsp;|&nbsp;
<span style="color:#C62828">Red = premium falling</span>.
<b>CE Chng (Σ)</b> and <b>PE Chng (Σ)</b> in the metrics are the sum across all strikes in ±250 range.<br><br>
<i>Score −4 to +4 is computed; Strong signals need score ≥ ±3. Refresh data on the main page to update.</i>
</div>
""", unsafe_allow_html=True)
