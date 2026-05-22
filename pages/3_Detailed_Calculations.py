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
        width:100%; border-collapse:collapse; font-size:14px;
        background:white; box-shadow:0 2px 8px rgba(0,0,0,0.1);
    }
    .calc-table th {
        background:#1565C0; color:white; padding:12px 10px;
        text-align:center; font-size:13px; font-weight:800;
        border:1px solid #1976D2;
    }
    .calc-table td {
        padding:10px 8px; text-align:center; border:1px solid #E0E0E0;
        font-size:13px; font-weight:600;
    }
    .calc-table tr:nth-child(even) td { background:#F8F9FA; }
    .calc-table tr:first-child td { background:#E3F2FD !important; font-weight:800 !important; }
    .strike-col { background:#1565C0 !important; color:white !important; font-weight:800 !important; }
    .pos-val { color:#2E7D32; font-weight:800; }
    .neg-val { color:#C62828; font-weight:800; }
    .total-row td { background:#1565C0 !important; color:white !important; font-weight:800 !important; }
    .itm-header { background:#FFE0B2 !important; font-weight:800 !important; }
    div[data-testid="metric-container"] {
        background:#F8F9FA; border:1px solid #E0E0E0;
        border-radius:8px; padding:12px !important;
    }
    div[data-testid="stMetricValue"] {
        font-size:24px !important; font-weight:800 !important; color:#1565C0 !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="calc-header">🧮 Detailed Calculations & Growth Analysis</div>',
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
    """
    Excel Formula: =IFERROR(((OI)/( IFERROR(IF(COI>0, OI-COI, OI+(-COI)),"") )-1)*SIGN( IFERROR(IF(COI>0, OI-COI, OI+(-COI)),"") ),"")*100
    Simplified: ((OI / |OI-COI|) - 1) * SIGN(OI-COI) * 100
    """
    try:
        oi = float(oi)
        coi = float(coi)
        if coi == 0 or oi == 0:
            return 0.0
        diff = oi - coi  # IFERROR(IF(COI>0, OI-COI, OI+(-COI)),"")
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
atm_strike = mround(spot, 50)
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
        "CE_VOL": ce.get("totalTradedVolume", 0),
        "CE_IV": ce.get("impliedVolatility", 0),
        "PE_OI": pe.get("openInterest", 0),
        "PE_COI": pe.get("changeinOpenInterest", 0),
        "PE_PCOI": pe.get("pchangeinOpenInterest", 0),
        "PE_VOL": pe.get("totalTradedVolume", 0),
        "PE_IV": pe.get("impliedVolatility", 0),
    })

df = pd.DataFrame(rows)
lo = open_price - 250
hi = open_price + 250
df_f = df[(df["STRIKE"] >= lo) & (df["STRIKE"] <= hi)].copy().reset_index(drop=True)

# ── Apply Growth Formula ──────────────────────────────────
df_f["PE_GROWTH"] = df_f.apply(lambda r: excel_growth_formula(r["PE_OI"], r["PE_COI"]), axis=1)
df_f["CE_GROWTH"] = df_f.apply(lambda r: excel_growth_formula(r["CE_OI"], r["CE_COI"]), axis=1)

# ── Get sorted strikes for ITM calculation ────────────────
all_strikes = sorted(df_f["STRIKE"].unique())
atm_idx = next((i for i, s in enumerate(all_strikes) if s >= atm_strike), len(all_strikes) // 2)

# ITM PE = 6 strikes below ATM (and ATM itself)
itm_pe_strikes = all_strikes[max(0, atm_idx-6):atm_idx+1]
itm_pe_df = df_f[df_f["STRIKE"].isin(itm_pe_strikes)].copy()

# ITM CE = 6 strikes above ATM (and ATM itself)
itm_ce_strikes = all_strikes[atm_idx:min(len(all_strikes), atm_idx+7)]
itm_ce_df = df_f[df_f["STRIKE"].isin(itm_ce_strikes)].copy()

itm_pe_total = itm_pe_df["PE_GROWTH"].sum()
itm_ce_total = itm_ce_df["CE_GROWTH"].sum()

# ── Display Summary Metrics ───────────────────────────────
st.markdown('<div class="section-hdr">📊 Summary Metrics</div>', unsafe_allow_html=True)
m1, m2, m3, m4, m5, m6 = st.columns(6)
tot_pe_oi = df_f["PE_OI"].sum()
tot_ce_oi = df_f["CE_OI"].sum()
tot_pe_coi = df_f["PE_COI"].sum()
tot_ce_coi = df_f["CE_COI"].sum()
pe_coi_growth_total = df_f["PE_GROWTH"].sum()
ce_coi_growth_total = df_f["CE_GROWTH"].sum()

m1.metric("🔺 PE COI Growth (Total)", f"{pe_coi_growth_total:+.2f}%", delta="▲ Bullish" if pe_coi_growth_total >= 0 else "▼ Bearish", delta_color="normal" if pe_coi_growth_total >= 0 else "inverse")
m2.metric("🔻 CE COI Growth (Total)", f"{ce_coi_growth_total:+.2f}%", delta="▲ Bullish" if ce_coi_growth_total >= 0 else "▼ Bearish", delta_color="normal" if ce_coi_growth_total >= 0 else "inverse")
m3.metric("💰 ITM PE", f"{itm_pe_total:+.2f}%", delta_color="normal" if itm_pe_total >= 0 else "inverse")
m4.metric("💰 ITM CE", f"{itm_ce_total:+.2f}%", delta_color="normal" if itm_ce_total >= 0 else "inverse")
m5.metric("📍 Spot", f"₹{spot:,.2f}")
m6.metric("🎯 ATM Strike", f"₹{int(atm_strike):,}")

# ── COI GROWTH CALCULATION TABLE (11 ROWS) ────────────────
st.markdown('<div class="section-hdr">📈 PE/CE COI Growth Calculation (11 Strikes)</div>', unsafe_allow_html=True)
st.caption("""
**Formula Explanation:**
- **PE_GROWTH[i]** = ((PE_OI[i] / |PE_OI[i] - PE_COI[i]|) - 1) × SIGN(PE_OI[i] - PE_COI[i]) × 100
- **CE_GROWTH[i]** = ((CE_OI[i] / |CE_OI[i] - CE_COI[i]|) - 1) × SIGN(CE_OI[i] - CE_COI[i]) × 100
""")

# Get 11 closest strikes to ATM (5 below, ATM, 5 above)
center_idx = (abs(df_f["STRIKE"] - atm_strike)).argmin()
start_idx = max(0, center_idx - 5)
end_idx = min(len(df_f), center_idx + 6)
growth_df = df_f.iloc[start_idx:end_idx].copy().reset_index(drop=True)

# Ensure exactly 11 rows
if len(growth_df) < 11:
    # Pad if needed
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

# Create HTML table
growth_html = ['<table class="calc-table"><thead><tr>']
growth_html.append('<th>Row</th>')
growth_html.append('<th>Strike</th>')
growth_html.append('<th>PE OI</th>')
growth_html.append('<th>PE COI</th>')
growth_html.append('<th>PE Growth %</th>')
growth_html.append('<th>CE OI</th>')
growth_html.append('<th>CE COI</th>')
growth_html.append('<th>CE Growth %</th>')
growth_html.append('</tr></thead><tbody>')

for idx, row in growth_df.iterrows():
    strike = int(row["STRIKE"])
    pe_oi = row["PE_OI"]
    pe_coi = row["PE_COI"]
    pe_gr = row["PE_GROWTH"]
    ce_oi = row["CE_OI"]
    ce_coi = row["CE_COI"]
    ce_gr = row["CE_GROWTH"]
    
    row_num = idx + 1
    is_atm = strike == int(atm_strike)
    row_class = "itm-header" if is_atm else ""
    
    growth_html.append(f'<tr class="{row_class}">')
    growth_html.append(f'<td><b>{row_num}</b></td>')
    growth_html.append(f'<td class="strike-col">{strike:,}</td>')
    growth_html.append(f'<td>{fmt_oi(pe_oi)}</td>')
    growth_html.append(f'<td><span class="{"pos-val" if pe_coi >= 0 else "neg-val"}">{fmt_oi(pe_coi)}</span></td>')
    growth_html.append(f'<td><span class="{"pos-val" if pe_gr >= 0 else "neg-val"}">{pe_gr:+.4f}%</span></td>')
    growth_html.append(f'<td>{fmt_oi(ce_oi)}</td>')
    growth_html.append(f'<td><span class="{"pos-val" if ce_coi >= 0 else "neg-val"}">{fmt_oi(ce_coi)}</span></td>')
    growth_html.append(f'<td><span class="{"pos-val" if ce_gr >= 0 else "neg-val"}">{ce_gr:+.4f}%</span></td>')
    growth_html.append('</tr>')

# Add TOTAL row
growth_html.append('<tr class="total-row">')
growth_html.append(f'<td colspan="2"><b>TOTAL (SUM of 11 rows)</b></td>')
growth_html.append(f'<td>{fmt_oi(growth_df["PE_OI"].sum())}</td>')
growth_html.append(f'<td>{fmt_oi(growth_df["PE_COI"].sum())}</td>')
growth_html.append(f'<td><b>{growth_df["PE_GROWTH"].sum():+.4f}%</b></td>')
growth_html.append(f'<td>{fmt_oi(growth_df["CE_OI"].sum())}</td>')
growth_html.append(f'<td>{fmt_oi(growth_df["CE_COI"].sum())}</td>')
growth_html.append(f'<td><b>{growth_df["CE_GROWTH"].sum():+.4f}%</b></td>')
growth_html.append('</tr>')

growth_html.append('</tbody></table>')
st.markdown("".join(growth_html), unsafe_allow_html=True)

# ── ITM PE CALCULATION ────────────────────────────────────
st.markdown('<div class="section-hdr">💰 ITM PE Calculation (6 Strikes Below ATM)</div>', unsafe_allow_html=True)
st.caption(f"""
**Formula:** ITM PE = SUM(PE_GROWTH for strikes below ATM)
- Takes 6 strikes BELOW ATM (₹{int(atm_strike):,})
- Rows: R10:R15 in Excel
""")

itm_pe_html = ['<table class="calc-table"><thead><tr>']
itm_pe_html.append('<th>Row</th>')
itm_pe_html.append('<th>Strike</th>')
itm_pe_html.append('<th>PE OI</th>')
itm_pe_html.append('<th>PE COI</th>')
itm_pe_html.append('<th>PE Growth %</th>')
itm_pe_html.append('</tr></thead><tbody>')

for idx, (_, row) in enumerate(itm_pe_df.iterrows()):
    strike = int(row["STRIKE"])
    pe_oi = row["PE_OI"]
    pe_coi = row["PE_COI"]
    pe_gr = row["PE_GROWTH"]
    
    itm_pe_html.append('<tr>')
    itm_pe_html.append(f'<td><b>R{10+idx}</b></td>')
    itm_pe_html.append(f'<td class="strike-col">{strike:,}</td>')
    itm_pe_html.append(f'<td>{fmt_oi(pe_oi)}</td>')
    itm_pe_html.append(f'<td><span class="{"pos-val" if pe_coi >= 0 else "neg-val"}">{fmt_oi(pe_coi)}</span></td>')
    itm_pe_html.append(f'<td><span class="{"pos-val" if pe_gr >= 0 else "neg-val"}">{pe_gr:+.4f}%</span></td>')
    itm_pe_html.append('</tr>')

itm_pe_html.append('<tr class="total-row">')
itm_pe_html.append(f'<td colspan="2"><b>SUM (R10:R15) = ITM PE</b></td>')
itm_pe_html.append(f'<td>{fmt_oi(itm_pe_df["PE_OI"].sum())}</td>')
itm_pe_html.append(f'<td>{fmt_oi(itm_pe_df["PE_COI"].sum())}</td>')
itm_pe_html.append(f'<td><b>{itm_pe_total:+.4f}%</b></td>')
itm_pe_html.append('</tr>')
itm_pe_html.append('</tbody></table>')

st.markdown("".join(itm_pe_html), unsafe_allow_html=True)

# ── ITM CE CALCULATION ────────────────────────────────────
st.markdown('<div class="section-hdr">💰 ITM CE Calculation (6 Strikes Above ATM)</div>', unsafe_allow_html=True)
st.caption(f"""
**Formula:** ITM CE = SUM(CE_GROWTH for strikes above ATM)
- Takes 6 strikes ABOVE ATM (₹{int(atm_strike):,})
- Rows: D5:D10 in Excel
""")

itm_ce_html = ['<table class="calc-table"><thead><tr>']
itm_ce_html.append('<th>Row</th>')
itm_ce_html.append('<th>Strike</th>')
itm_ce_html.append('<th>CE OI</th>')
itm_ce_html.append('<th>CE COI</th>')
itm_ce_html.append('<th>CE Growth %</th>')
itm_ce_html.append('</tr></thead><tbody>')

for idx, (_, row) in enumerate(itm_ce_df.iterrows()):
    strike = int(row["STRIKE"])
    ce_oi = row["CE_OI"]
    ce_coi = row["CE_COI"]
    ce_gr = row["CE_GROWTH"]
    
    itm_ce_html.append('<tr>')
    itm_ce_html.append(f'<td><b>D{5+idx}</b></td>')
    itm_ce_html.append(f'<td class="strike-col">{strike:,}</td>')
    itm_ce_html.append(f'<td>{fmt_oi(ce_oi)}</td>')
    itm_ce_html.append(f'<td><span class="{"pos-val" if ce_coi >= 0 else "neg-val"}">{fmt_oi(ce_coi)}</span></td>')
    itm_ce_html.append(f'<td><span class="{"pos-val" if ce_gr >= 0 else "neg-val"}">{ce_gr:+.4f}%</span></td>')
    itm_ce_html.append('</tr>')

itm_ce_html.append('<tr class="total-row">')
itm_ce_html.append(f'<td colspan="2"><b>SUM (D5:D10) = ITM CE</b></td>')
itm_ce_html.append(f'<td>{fmt_oi(itm_ce_df["CE_OI"].sum())}</td>')
itm_ce_html.append(f'<td>{fmt_oi(itm_ce_df["CE_COI"].sum())}</td>')
itm_ce_html.append(f'<td><b>{itm_ce_total:+.4f}%</b></td>')
itm_ce_html.append('</tr>')
itm_ce_html.append('</tbody></table>')

st.markdown("".join(itm_ce_html), unsafe_allow_html=True)

# ── Full Reference Table ──────────────────────────────────
st.markdown('<div class="section-hdr">📋 Full Data Reference (All Strikes in Range)</div>', unsafe_allow_html=True)
with st.expander("View complete strike data", expanded=False):
    ref_df = df_f[["STRIKE", "PE_OI", "PE_COI", "PE_PCOI", "PE_VOL", "PE_IV", 
                   "CE_OI", "CE_COI", "CE_PCOI", "CE_VOL", "CE_IV", "PE_GROWTH", "CE_GROWTH"]].copy()
    ref_df.columns = ["Strike", "PE OI", "PE COI", "PE %COI", "PE Vol", "PE IV",
                      "CE OI", "CE COI", "CE %COI", "CE Vol", "CE IV", "PE Growth%", "CE Growth%"]
    
    st.dataframe(
        ref_df.style
        .format({
            "PE OI": "{:,.0f}",
            "PE COI": "{:,.0f}",
            "PE %COI": "{:.2f}",
            "PE Vol": "{:,.0f}",
            "PE IV": "{:.2f}",
            "CE OI": "{:,.0f}",
            "CE COI": "{:,.0f}",
            "CE %COI": "{:.2f}",
            "CE Vol": "{:,.0f}",
            "CE IV": "{:.2f}",
            "PE Growth%": "{:+.4f}",
            "CE Growth%": "{:+.4f}",
        })
        .background_gradient(subset=["PE Growth%", "CE Growth%"], cmap="RdYlGn", vmin=-100, vmax=100),
        use_container_width=True,
        height=500
    )

# ── Export Data ───────────────────────────────────────────
st.markdown('<div class="section-hdr">⬇️ Export Calculation Data</div>', unsafe_allow_html=True)

export_df = df_f[["STRIKE", "PE_OI", "PE_COI", "PE_GROWTH", "CE_OI", "CE_COI", "CE_GROWTH"]].copy()
export_df.columns = ["Strike", "PE OI", "PE COI", "PE Growth%", "CE OI", "CE COI", "CE Growth%"]

csv = export_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Download Calculations CSV",
    csv,
    f"nifty_calculations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    "text/csv"
)

st.success(f"""
✅ **Current Session Values:**
- **PE COI Growth (Total):** {pe_coi_growth_total:+.2f}%
- **CE COI Growth (Total):** {ce_coi_growth_total:+.2f}%
- **ITM PE:** {itm_pe_total:+.2f}%
- **ITM CE:** {itm_ce_total:+.2f}%
- **Spot:** ₹{spot:,.2f}
- **ATM Strike:** ₹{int(atm_strike):,}
- **Data Range:** ₹{int(lo):,} to ₹{int(hi):,}
""")
