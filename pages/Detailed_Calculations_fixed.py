import streamlit as st
import pandas as pd
import math
from datetime import datetime

st.set_page_config(page_title="Detailed Calculations", page_icon="🧮", layout="wide")

st.markdown("""
<style>
    .calc-header {
        background:linear-gradient(90deg,#1565C0,#1976D2);
        padding:15px 22px; border-radius:10px; color:white;
        font-size:22px; font-weight:bold; margin-bottom:18px;
    }
    .section-hdr {
        background:#F5F5F5; border-left:4px solid #1565C0;
        padding:10px 16px; font-size:16px; font-weight:700;
        color:#1565C0; margin:16px 0 10px 0; border-radius:0 6px 6px 0;
    }
    .calc-table {
        width:100%; border-collapse:collapse; font-size:13px;
        background:white; box-shadow:0 2px 8px rgba(0,0,0,0.1);
    }
    .calc-table th {
        background:#1565C0; color:white; padding:8px 6px;
        text-align:center; font-size:11px; font-weight:800;
        border:1px solid #1976D2;
    }
    .calc-table td {
        padding:6px 5px; text-align:center; border:1px solid #E0E0E0;
        font-size:12px; font-weight:600;
    }
    .calc-table tr:nth-child(even) td { background:#F8F9FA; }
    .strike-col { background:#1565C0 !important; color:white !important; font-weight:800 !important; }
    .pos-val { color:#2E7D32; font-weight:800; }
    .neg-val { color:#C62828; font-weight:800; }
    .total-row td { background:#1565C0 !important; color:white !important; font-weight:800 !important; }
    div[data-testid="metric-container"] {
        background:#F8F9FA; border:1px solid #E0E0E0;
        border-radius:8px; padding:12px !important;
    }
    div[data-testid="stMetricValue"] {
        font-size:24px !important; font-weight:800 !important; color:#1565C0 !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="calc-header">🧮 Detailed Calculations & ITM Analysis</div>',
            unsafe_allow_html=True)

# ── Validation ────────────────────────────────────────────
if "raw_data" not in st.session_state or st.session_state.raw_data is None:
    st.warning("⚠️ No data yet! Please go to the **Main Page** first and wait for data to load.")
    st.stop()

def mround(val, multiple):
    return math.floor(val/multiple+0.5)*multiple

def fmt_oi(v):
    try:
        v = float(v)
        if v >= 10_000_000: return f"{v/10_000_000:.2f}Cr"
        if v >= 100_000: return f"{v/100_000:.2f}L"
        return f"{int(v):,}"
    except:
        return str(v)

def excel_growth_formula(oi, coi):
    """Excel: =IFERROR(((OI)/( IFERROR(IF(COI>0, OI-COI, OI+(-COI)),"") )-1)*SIGN( IFERROR(IF(COI>0, OI-COI, OI+(-COI)),"") ),"")*100"""
    try:
        oi = float(oi)
        coi = float(coi)
        if coi == 0 or oi == 0:
            return 0.0
        diff = oi - coi
        if diff == 0:
            return 0.0
        val = ((oi / abs(diff)) - 1) * (1 if diff > 0 else -1) * 100
        return round(val, 4)
    except:
        return 0.0

# ── Parse Data ────────────────────────────────────────────
raw = st.session_state.raw_data
records = raw.get("records", {})
spot = records.get("underlyingValue", 0)
open_price = st.session_state.get("open_price", mround(spot, 50))
open_spot = st.session_state.get("open_spot", spot)
prev_close = st.session_state.get("prev_close", 0)
atm_strike = mround(open_price, 50)  # Pivot Strike = MROUND(Day Open,50)
multiplier = st.session_state.get("oi_multiplier", 50)

rows = []
for item in records.get("data", []):
    ce = item.get("CE", {})
    pe = item.get("PE", {})
    rows.append({
        "STRIKE": item.get("strikePrice", 0),
        "CE_OI": ce.get("openInterest", 0),
        "CE_COI": ce.get("changeinOpenInterest", 0),
        "CE_PCOI": ce.get("pchangeinOpenInterest", 0),
        "PE_OI": pe.get("openInterest", 0),
        "PE_COI": pe.get("changeinOpenInterest", 0),
        "PE_PCOI": pe.get("pchangeinOpenInterest", 0),
    })

df = pd.DataFrame(rows)
lo = open_price - 250
hi = open_price + 250
df_f = df[(df["STRIKE"] >= lo) & (df["STRIKE"] <= hi)].copy().reset_index(drop=True)

# ── Apply Growth Formula ──────────────────────────────────
df_f["PE_GROWTH"] = df_f.apply(lambda r: excel_growth_formula(r["PE_OI"], r["PE_COI"]), axis=1)
df_f["CE_GROWTH"] = df_f.apply(lambda r: excel_growth_formula(r["CE_OI"], r["CE_COI"]), axis=1)

# ── Get sorted strikes ────────────────────────────────────
all_strikes = sorted(df_f["STRIKE"].unique())
atm_idx = next((i for i, s in enumerate(all_strikes) if s >= atm_strike), len(all_strikes) // 2)

# ===== ITM GROWTH CALCULATION (Excel Logic) =====
# ATM = MROUND(Day Open, 50)
# ITM PE = SUM PE_PCOI for ATM + 5 strikes ABOVE (including ATM) → strikes going UP
# ITM CE = SUM CE_PCOI for ATM + 5 strikes BELOW (including ATM) → strikes going DOWN

all_strikes = sorted(df_f["STRIKE"].unique())

try:
    atm_idx = all_strikes.index(atm_strike)
except ValueError:
    atm_idx = next((i for i,s in enumerate(all_strikes) if s >= atm_strike), len(all_strikes)//2)

# ITM PE: ATM included + 5 above (23650,23700,23750,23800,23850,23900)
itm_pe_strikes = all_strikes[atm_idx : atm_idx + 6]

# ITM CE: 5 below + ATM included (23400,23450,23500,23550,23600,23650)
itm_ce_strikes = all_strikes[max(0, atm_idx - 5) : atm_idx + 1]

itm_pe_df = (
    df_f[df_f["STRIKE"].isin(itm_pe_strikes)]
    .copy()
    .sort_values("STRIKE")
)

itm_ce_df = (
    df_f[df_f["STRIKE"].isin(itm_ce_strikes)]
    .copy()
    .sort_values("STRIKE")
)

# Totals using NSE pchangeinOpenInterest (%COI)
itm_pe_total = round(itm_pe_df["PE_PCOI"].sum(), 2)
itm_ce_total = round(itm_ce_df["CE_PCOI"].sum(), 2)

# ── Display Summary Metrics ───────────────────────────────
st.markdown('<div class="section-hdr">📊 Summary Metrics</div>', unsafe_allow_html=True)
m1, m2, m3, m4, m5, m6 = st.columns(6)
tot_pe_growth = df_f["PE_GROWTH"].sum()
tot_ce_growth = df_f["CE_GROWTH"].sum()

m1.metric("🔺 PE Growth (Total)", f"{tot_pe_growth:+.2f}%", delta_color="normal" if tot_pe_growth >= 0 else "inverse")
m2.metric("🔻 CE Growth (Total)", f"{tot_ce_growth:+.2f}%", delta_color="normal" if tot_ce_growth >= 0 else "inverse")
m3.metric("💰 ITM PE", f"{itm_pe_total:+.2f}%", delta_color="normal" if itm_pe_total >= 0 else "inverse")
m4.metric("💰 ITM CE", f"{itm_ce_total:+.2f}%", delta_color="normal" if itm_ce_total >= 0 else "inverse")
m5.metric("📍 Spot", f"₹{spot:,.2f}")
m6.metric("🎯 ATM", f"₹{int(atm_strike):,}")

# ── COI GROWTH CALCULATION TABLE (11 ROWS) ────────────────
st.markdown('<div class="section-hdr">📈 COI Growth % (11 Closest Strikes)</div>', unsafe_allow_html=True)

center_idx = (abs(df_f["STRIKE"] - atm_strike)).argmin()
start_idx = max(0, center_idx - 5)
end_idx = min(len(df_f), center_idx + 6)
growth_df = df_f.iloc[start_idx:end_idx].copy().reset_index(drop=True)

if len(growth_df) < 11:
    while len(growth_df) < 11:
        if start_idx > 0:
            start_idx -= 1
            growth_df = pd.concat([df_f.iloc[[start_idx]], growth_df], ignore_index=True)
        elif end_idx < len(df_f):
            growth_df = pd.concat([growth_df, df_f.iloc[[end_idx]]], ignore_index=True)
            end_idx += 1
        else:
            break

growth_df = growth_df.head(11).reset_index(drop=True)

growth_html = ['<table class="calc-table"><thead><tr>']
growth_html.append('<th>R</th><th>Strike</th><th>PE %COI</th><th>PE Gr%</th><th>CE %COI</th><th>CE Gr%</th>')
growth_html.append('</tr></thead><tbody>')

for idx, row in growth_df.iterrows():
    strike = int(row["STRIKE"])
    pe_pcoi = row["PE_PCOI"]
    pe_gr = row["PE_GROWTH"]
    ce_pcoi = row["CE_PCOI"]
    ce_gr = row["CE_GROWTH"]
    
    is_atm = strike == int(atm_strike)
    row_class = 'style="background:#FFE0B2"' if is_atm else ''
    
    growth_html.append(f'<tr {row_class}>')
    growth_html.append(f'<td><b>{idx+1}</b></td>')
    growth_html.append(f'<td class="strike-col">{strike:,}</td>')
    growth_html.append(f'<td><span class="{"pos-val" if pe_pcoi >= 0 else "neg-val"}">{pe_pcoi:+.2f}%</span></td>')
    growth_html.append(f'<td><span class="{"pos-val" if pe_gr >= 0 else "neg-val"}">{pe_gr:+.2f}%</span></td>')
    growth_html.append(f'<td><span class="{"pos-val" if ce_pcoi >= 0 else "neg-val"}">{ce_pcoi:+.2f}%</span></td>')
    growth_html.append(f'<td><span class="{"pos-val" if ce_gr >= 0 else "neg-val"}">{ce_gr:+.2f}%</span></td>')
    growth_html.append('</tr>')

growth_html.append('<tr class="total-row">')
growth_html.append(f'<td colspan="2"><b>TOTAL</b></td>')
growth_html.append(f'<td><b>{growth_df["PE_PCOI"].sum():+.2f}%</b></td>')
growth_html.append(f'<td><b>{growth_df["PE_GROWTH"].sum():+.2f}%</b></td>')
growth_html.append(f'<td><b>{growth_df["CE_PCOI"].sum():+.2f}%</b></td>')
growth_html.append(f'<td><b>{growth_df["CE_GROWTH"].sum():+.2f}%</b></td>')
growth_html.append('</tr>')
growth_html.append('</tbody></table>')
st.markdown("".join(growth_html), unsafe_allow_html=True)

# ── ITM PE CALCULATION (6 ABOVE ATM) ──────────────────────
st.markdown(f'<div class="section-hdr">💰 ITM PE — ATM({int(atm_strike):,}) + 5 strikes above | SUM(PE %COI)</div>', unsafe_allow_html=True)

itm_pe_html = ['<table class="calc-table"><thead><tr>']
itm_pe_html.append('<th>R</th><th>Strike</th><th>PE %COI</th>')
itm_pe_html.append('</tr></thead><tbody>')

for idx, (_, row) in enumerate(itm_pe_df.iterrows()):
    strike = int(row["STRIKE"])
    pe_pcoi = row["PE_PCOI"]
    
    itm_pe_html.append('<tr>')
    itm_pe_html.append(f'<td>{idx+1}</td>')
    itm_pe_html.append(f'<td class="strike-col">{strike:,}</td>')
    itm_pe_html.append(f'<td><span class="{"pos-val" if pe_pcoi >= 0 else "neg-val"}">{pe_pcoi:+.2f}%</span></td>')
    itm_pe_html.append('</tr>')

itm_pe_html.append('<tr class="total-row">')
itm_pe_html.append(f'<td colspan="2"><b>ITM PE TOTAL</b></td>')
itm_pe_html.append(f'<td><b>{itm_pe_total:+.2f}%</b></td>')
itm_pe_html.append('</tr>')
itm_pe_html.append('</tbody></table>')

st.markdown("".join(itm_pe_html), unsafe_allow_html=True)

# ── ITM CE CALCULATION (6 BELOW ATM) ──────────────────────
st.markdown(f'<div class="section-hdr">💰 ITM CE — 5 strikes below + ATM({int(atm_strike):,}) | SUM(CE %COI)</div>', unsafe_allow_html=True)

itm_ce_html = ['<table class="calc-table"><thead><tr>']
itm_ce_html.append('<th>R</th><th>Strike</th><th>CE %COI</th>')
itm_ce_html.append('</tr></thead><tbody>')

for idx, (_, row) in enumerate(itm_ce_df.iterrows()):
    strike = int(row["STRIKE"])
    ce_pcoi = row["CE_PCOI"]
    
    itm_ce_html.append('<tr>')
    itm_ce_html.append(f'<td>{idx+1}</td>')
    itm_ce_html.append(f'<td class="strike-col">{strike:,}</td>')
    itm_ce_html.append(f'<td><span class="{"pos-val" if ce_pcoi >= 0 else "neg-val"}">{ce_pcoi:+.2f}%</span></td>')
    itm_ce_html.append('</tr>')

itm_ce_html.append('<tr class="total-row">')
itm_ce_html.append(f'<td colspan="2"><b>ITM CE TOTAL</b></td>')
itm_ce_html.append(f'<td><b>{itm_ce_total:+.2f}%</b></td>')
itm_ce_html.append('</tr>')
itm_ce_html.append('</tbody></table>')

st.markdown("".join(itm_ce_html), unsafe_allow_html=True)

# ── Export Data ───────────────────────────────────────────
st.markdown('<div class="section-hdr">⬇️ Export</div>', unsafe_allow_html=True)

export_df = df_f[["STRIKE", "PE_PCOI", "PE_GROWTH", "CE_PCOI", "CE_GROWTH"]].copy()
export_df.columns = ["Strike", "PE %COI", "PE Growth%", "CE %COI", "CE Growth%"]

csv = export_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Download Calculations CSV",
    csv,
    f"nifty_calc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    "text/csv"
)

st.success(f"""
✅ **Session Values:**
- PE Growth (Total 11): {tot_pe_growth:+.2f}%
- CE Growth (Total 11): {tot_ce_growth:+.2f}%
- **ITM PE (6 above): {itm_pe_total:+.2f}%**
- **ITM CE (6 below): {itm_ce_total:+.2f}%**
""")
