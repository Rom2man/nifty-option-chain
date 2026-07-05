import streamlit as st
import pandas as pd
import math
import time

st.set_page_config(page_title="Decision 2", page_icon="🎯", layout="wide")

# ── Compact CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 0.8rem !important; padding-bottom: 0.8rem !important; }
    h1 { font-size: 1.25rem !important; margin-bottom: 0.3rem !important; }
    h2, h3 { font-size: 1rem !important; margin: 0.4rem 0 0.2rem 0 !important; }
    [data-testid="metric-container"] { padding: 4px 8px !important; }
    [data-testid="metric-container"] label { font-size: 0.68rem !important; }
    [data-testid="metric-container"] [data-testid="metric-value"] { font-size: 1rem !important; }
    div[data-testid="stDataFrame"] { margin-top: 0 !important; }
    .stDataFrame { font-size: 0.78rem !important; }
    .signal-box {
        text-align: center; padding: 6px 12px; border-radius: 8px;
        font-size: 1.1rem; font-weight: 700; margin: 4px 0;
    }
    .gauge-wrap { display: flex; justify-content: center; margin: 0px 0 4px 0; }
    .section-label {
        font-size: 0.7rem; font-weight: 600; color: #888;
        text-transform: uppercase; letter-spacing: 0.05em;
        margin: 6px 0 2px 0;
    }
</style>
""", unsafe_allow_html=True)

# ── Helpers ──────────────────────────────────────────────────────────────────
def mround(val, multiple):
    return math.floor(val / multiple + 0.5) * multiple

def build_gauge(score, max_score=80):
    """SVG semicircular riskometer. score in [-max_score, +max_score].
    Negative = PE bias (bearish / HIGH risk for CE buyer)
    Positive = CE bias (bullish / LOW risk for CE buyer)
    We map score → angle 0°(left=VERY HIGH risk) to 180°(right=LOW risk).
    """
    # Normalise score to 0‥1  (score=-80 → 0, score=+80 → 1)
    norm = (score + max_score) / (2 * max_score)
    norm = max(0.0, min(1.0, norm))

    # Needle angle: 0° = left (VERY HIGH / strong PE)  →  180° = right (LOW / strong CE)
    # SVG arc goes from 180° (left) to 0° (right) at top; we compute in standard math coords.
    # In SVG: angle measured from positive‑x; needle at norm=0 points left (180°), norm=1 right (0°)
    needle_deg = 180 - norm * 180          # 180→0
    needle_rad = math.radians(needle_deg)

    cx, cy, r = 200, 190, 150
    # Needle endpoint
    nx = cx + r * 0.82 * math.cos(needle_rad)
    ny = cy - r * 0.82 * math.sin(needle_rad)   # SVG y inverted

    # Build arc segments (6 zones, each 30°)
    colors = ["#e60026", "#e6370a", "#e67c00", "#e6b800", "#8db600", "#3a7d00"]
    # Zones from left (180°) to right (0°)
    segments = []
    num = len(colors)
    for i, color in enumerate(colors):
        a1 = math.radians(180 - i * 30)
        a2 = math.radians(180 - (i + 1) * 30)
        x1 = cx + r * math.cos(a1)
        y1 = cy - r * math.sin(a1)
        x2 = cx + r * math.cos(a2)
        y2 = cy - r * math.sin(a2)
        # Inner points (hub)
        ri = 55
        xi1 = cx + ri * math.cos(a1)
        yi1 = cy - ri * math.sin(a1)
        xi2 = cx + ri * math.cos(a2)
        yi2 = cy - ri * math.sin(a2)
        path = (
            f"M {xi1:.1f} {yi1:.1f} "
            f"L {x1:.1f} {y1:.1f} "
            f"A {r} {r} 0 0 0 {x2:.1f} {y2:.1f} "
            f"L {xi2:.1f} {yi2:.1f} "
            f"A {ri} {ri} 0 0 1 {xi1:.1f} {yi1:.1f} Z"
        )
        segments.append((path, color))

    zone_labels = [
        (165, "STRONG\nPE", 0.55),
        (135, "BUY PE", 0.72),
        (105, "MILD PE", 0.72),
        (75,  "MILD CE", 0.72),
        (45,  "BUY CE", 0.72),
        (15,  "STRONG\nCE", 0.55),
    ]

    label_svgs = []
    for ang_deg, text, rf in zone_labels:
        a = math.radians(ang_deg)
        lx = cx + r * rf * math.cos(a)
        ly = cy - r * rf * math.sin(a)
        lines = text.split("\n")
        if len(lines) == 2:
            tsvg = (f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle" '
                    f'font-size="9" fill="white" font-weight="700">'
                    f'<tspan x="{lx:.0f}" dy="-5">{lines[0]}</tspan>'
                    f'<tspan x="{lx:.0f}" dy="12">{lines[1]}</tspan>'
                    f'</text>')
        else:
            tsvg = (f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle" '
                    f'font-size="9" fill="white" font-weight="700">{text}</text>')
        label_svgs.append(tsvg)

    seg_svg = "\n".join(
        f'<path d="{p}" fill="{c}" stroke="white" stroke-width="1.5"/>'
        for p, c in segments
    )
    labels_svg = "\n".join(label_svgs)

    # Score label colour
    if score >= 50:   sc = "#3a7d00"
    elif score >= 25: sc = "#8db600"
    elif score <= -50: sc = "#e60026"
    elif score <= -25: sc = "#e6370a"
    else:              sc = "#e6b800"

    confidence = min(100, round(abs(score) / max_score * 100, 1))

    svg = f"""
<svg width="400" height="210" viewBox="0 0 400 210" xmlns="http://www.w3.org/2000/svg">
  {seg_svg}
  <!-- hub circle -->
  <circle cx="{cx}" cy="{cy}" r="52" fill="#1a1a2e" stroke="#333" stroke-width="2"/>
  <!-- needle -->
  <line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}"
        stroke="white" stroke-width="3" stroke-linecap="round"/>
  <circle cx="{cx}" cy="{cy}" r="7" fill="white"/>
  <!-- score text in hub -->
  <text x="{cx}" y="{cy-6}" text-anchor="middle" font-size="16"
        fill="{sc}" font-weight="800" font-family="monospace">{score:+d}</text>
  <text x="{cx}" y="{cy+10}" text-anchor="middle" font-size="8"
        fill="#aaa" font-family="sans-serif">SCORE</text>
  <text x="{cx}" y="{cy+22}" text-anchor="middle" font-size="8"
        fill="#ccc" font-family="sans-serif">{confidence:.0f}% conf</text>
  <!-- axis labels -->
  <text x="18" y="{cy+8}" text-anchor="middle" font-size="9" fill="#e60026" font-weight="700">BEARISH</text>
  <text x="382" y="{cy+8}" text-anchor="middle" font-size="9" fill="#3a7d00" font-weight="700">BULLISH</text>
</svg>"""
    return svg, confidence

# ── Gate ─────────────────────────────────────────────────────────────────────
if "raw_data" not in st.session_state or st.session_state.raw_data is None:
    st.warning("⚠️ Open main Option Chain page first.")
    st.stop()

raw   = st.session_state.raw_data
records = raw.get("records", {})
spot  = records.get("underlyingValue", 0)
pivot = st.session_state.get("open_price", mround(spot, 50))

# ── Parse rows ────────────────────────────────────────────────────────────────
rows = []
for item in records.get("data", []):
    ce = item.get("CE", {})
    pe = item.get("PE", {})
    rows.append({
        "STRIKE":  item.get("strikePrice", 0),
        "CE_OI":   ce.get("openInterest", 0),
        "CE_COI":  ce.get("changeinOpenInterest", 0),
        "CE_VOL":  ce.get("totalTradedVolume", 0),
        "CE_IV":   ce.get("impliedVolatility", 0),
        "PE_OI":   pe.get("openInterest", 0),
        "PE_COI":  pe.get("changeinOpenInterest", 0),
        "PE_VOL":  pe.get("totalTradedVolume", 0),
        "PE_IV":   pe.get("impliedVolatility", 0),
    })

df = pd.DataFrame(rows)
df = df[(df["STRIKE"] >= pivot - 250) & (df["STRIKE"] <= pivot + 250)].copy()

if df.empty:
    st.warning("No strikes in ±250 range.")
    st.stop()

# ── Aggregates ────────────────────────────────────────────────────────────────
ce_oi  = df["CE_OI"].sum();   pe_oi  = df["PE_OI"].sum()
ce_vol = df["CE_VOL"].sum();  pe_vol = df["PE_VOL"].sum()
ce_coi_abs = df["CE_COI"].abs().sum()
pe_coi_abs = df["PE_COI"].abs().sum()

oi_pcr  = pe_oi  / ce_oi      if ce_oi      else 0
vol_pcr = pe_vol / ce_vol     if ce_vol     else 0
coi_pcr = pe_coi_abs / ce_coi_abs if ce_coi_abs else 0
ce_iv   = df["CE_IV"].sum()
pe_iv   = df["PE_IV"].sum()

# ── Scoring ───────────────────────────────────────────────────────────────────
score = 0
if   oi_pcr  > 1.2: score += 20
elif oi_pcr  < 0.8: score -= 20
if   coi_pcr > 1.2: score += 25
elif coi_pcr < 0.8: score -= 25
if   vol_pcr > 1.0: score += 10
elif vol_pcr < 0.9: score -= 10
score += 10 if ce_iv > pe_iv else -10

strong_ce = (df["CE_VOL"] > df["CE_COI"].abs() * 1.5).sum()
strong_pe = (df["PE_VOL"] > df["PE_COI"].abs() * 1.5).sum()
if   strong_ce > strong_pe: score += 10
elif strong_pe > strong_ce: score -= 10
score += 5 if spot > pivot else -5

if   score >=  50: signal = "🚀 STRONG BUY CE"; sig_color = "#1a5c1a"
elif score >=  25: signal = "🟢 BUY CE";         sig_color = "#2d6e2d"
elif score <= -50: signal = "🚨 STRONG BUY PE";  sig_color = "#6e0000"
elif score <= -25: signal = "🔴 BUY PE";         sig_color = "#8b2020"
else:               signal = "🟡 NEUTRAL";        sig_color = "#5c5c00"

# ── Max COI strikes ───────────────────────────────────────────────────────────
max_ce_coi_row = df.loc[df["CE_COI"].abs().idxmax()]
max_pe_coi_row = df.loc[df["PE_COI"].abs().idxmax()]

# ── Layout ────────────────────────────────────────────────────────────────────
st.markdown("### 🎯 Decision 2 — Advanced Engine")

# Row 1: PCR metrics + signal
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("OI PCR",       f"{oi_pcr:.3f}")
m2.metric("COI PCR (abs)",f"{coi_pcr:.3f}")
m3.metric("VOL PCR",      f"{vol_pcr:.3f}")
m4.metric("CE IV Σ",      f"{ce_iv:.1f}")
m5.metric("PE IV Σ",      f"{pe_iv:.1f}")

st.markdown("---")

# Row 2: Gauge + right panel
gcol, rcol = st.columns([2, 3])

with gcol:
    svg, confidence = build_gauge(score)

    # ── Publish to session_state so the Recording page can pick this up ────────
    st.session_state["dc2_score"] = score
    st.session_state["dc2_confidence"] = confidence
    st.session_state["dc2_signal"] = signal
    st.session_state["dc2_time"] = time.time()

    st.markdown(f'<div class="gauge-wrap">{svg}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="signal-box" style="background:{sig_color};color:white">{signal}</div>',
        unsafe_allow_html=True
    )

with rcol:
    # Max COI section
    st.markdown('<p class="section-label">Max Change in OI (Key Strikes)</p>', unsafe_allow_html=True)
    coi_data = pd.DataFrame({
        "Side":   ["CE (Resistance)", "PE (Support)"],
        "Strike": [int(max_ce_coi_row["STRIKE"]), int(max_pe_coi_row["STRIKE"])],
        "Δ OI":   [int(max_ce_coi_row["CE_COI"]),  int(max_pe_coi_row["PE_COI"])],
        "OI":     [int(max_ce_coi_row["CE_OI"]),    int(max_pe_coi_row["PE_OI"])],
        "Volume": [int(max_ce_coi_row["CE_VOL"]),   int(max_pe_coi_row["PE_VOL"])],
    })
    st.dataframe(coi_data, hide_index=True, use_container_width=True)

    # Support / Resistance
    st.markdown('<p class="section-label">Top 2 Support & Resistance (by OI)</p>', unsafe_allow_html=True)
    sup = df.nlargest(2, "PE_OI")[["STRIKE", "PE_OI", "PE_COI", "PE_VOL"]].reset_index(drop=True)
    res = df.nlargest(2, "CE_OI")[["STRIKE", "CE_OI", "CE_COI", "CE_VOL"]].reset_index(drop=True)
    sup.columns = ["Strike", "PE OI", "PE ΔCOI", "PE Vol"]
    res.columns = ["Strike", "CE OI", "CE ΔCOI", "CE Vol"]
    sc1, sc2 = st.columns(2)
    with sc1:
        st.markdown("**🟢 Supports**")
        st.dataframe(sup, hide_index=True, use_container_width=True)
    with sc2:
        st.markdown("**🔴 Resistances**")
        st.dataframe(res, hide_index=True, use_container_width=True)

st.markdown("---")

# Row 3: Vol vs COI ratio table (compact)
st.markdown('<p class="section-label">Vol / COI Strength by Strike</p>', unsafe_allow_html=True)
tmp = df[["STRIKE", "CE_VOL", "CE_COI", "PE_VOL", "PE_COI"]].copy()
tmp["CE_R"] = (tmp["CE_VOL"] / tmp["CE_COI"].abs().replace(0, 1)).round(2)
tmp["PE_R"] = (tmp["PE_VOL"] / tmp["PE_COI"].abs().replace(0, 1)).round(2)
display = tmp[["STRIKE", "CE_VOL", "CE_R", "PE_VOL", "PE_R"]].copy()
display.columns = ["Strike", "CE Vol", "CE V/COI", "PE Vol", "PE V/COI"]

# Highlight ATM
atm = mround(spot, 50)
def highlight_atm(row):
    if row["Strike"] == atm:
        return ["background-color: #2a2a4a; font-weight: bold"] * len(row)
    return [""] * len(row)

st.dataframe(
    display.style.apply(highlight_atm, axis=1).format({
        "CE Vol": "{:,.0f}", "PE Vol": "{:,.0f}",
        "CE V/COI": "{:.2f}", "PE V/COI": "{:.2f}"
    }),
    hide_index=True,
    use_container_width=True,
    height=250
)

st.caption(f"Spot: {spot} | Pivot/ATM: {pivot} | Range: {pivot-250}–{pivot+250} | Score: {score:+d}/80 | Conf: {confidence:.0f}%")
