import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="Scorecard", page_icon="📊", layout="wide")

st.title("📊 Scorecard")

def mround(val, multiple):
    return math.floor(val / multiple + 0.5) * multiple

raw_data = st.session_state.get("raw_data")

if raw_data is None:
    st.warning("Open the main Option Chain page first.")
    st.stop()

rec  = raw_data.get("records", {})
spot = rec.get("underlyingValue", 0)

rows = []
for item in rec.get("data", []):
    ce = item.get("CE", {})
    pe = item.get("PE", {})
    rows.append({
        "STRIKE" : item.get("strikePrice", 0),
        "CE_OI"  : ce.get("openInterest", 0),
        "CE_COI" : ce.get("changeinOpenInterest", 0),
        "CE_VOL" : ce.get("totalTradedVolume", 0),
        "CE_IV"  : ce.get("impliedVolatility", 0),
        "PE_OI"  : pe.get("openInterest", 0),
        "PE_COI" : pe.get("changeinOpenInterest", 0),
        "PE_VOL" : pe.get("totalTradedVolume", 0),
        "PE_IV"  : pe.get("impliedVolatility", 0),
    })

df = pd.DataFrame(rows)

open_strike = st.session_state.get("open_price", mround(spot, 50))
atm_strike  = mround(spot, 50)

df_f = df[
    (df["STRIKE"] >= open_strike - 250) &
    (df["STRIKE"] <= open_strike + 250)
].copy()

if df_f.empty:
    st.warning("No strikes available in range.")
    st.stop()

# ── Totals ────────────────────────────────────────────────────────────────────
tot_ce_oi  = df_f["CE_OI"].sum()
tot_pe_oi  = df_f["PE_OI"].sum()
tot_ce_coi = df_f["CE_COI"].sum()
tot_pe_coi = df_f["PE_COI"].sum()
tot_ce_vol = df_f["CE_VOL"].sum()
tot_pe_vol = df_f["PE_VOL"].sum()

# ── PCR ───────────────────────────────────────────────────────────────────────
# FIX #2: both numerator and denominator treated consistently (raw, signed).
# A negative COI PCR is meaningful — it tells you one side is unwinding.
oi_pcr  = tot_pe_oi  / max(tot_ce_oi, 1)
coi_pcr = tot_pe_coi / tot_ce_coi if tot_ce_coi != 0 else 0.0
vol_pcr = tot_pe_vol / max(tot_ce_vol, 1)

# ── Strike Score ──────────────────────────────────────────────────────────────
# FIX #1: use max(coi, 0) instead of abs(coi).
#   • Positive COI = new writing  → contributes to score  (bullish for support,
#     bearish for resistance)
#   • Negative COI = unwinding    → does NOT add to score  (wall is weakening)
# Weights: COI direction 50 | OI wall size 30 | ATM proximity 20
def strike_score(oi, coi, strike, max_oi, max_coi):
    doi  = (max(coi, 0) / max_coi) * 50 if max_coi else 0   # directional only
    oi_s = (oi / max_oi) * 30            if max_oi  else 0
    prox = max(0, 1 - abs(strike - atm_strike) / 250) * 20
    return round(doi + oi_s + prox, 2)

max_pe_oi  = df_f["PE_OI"].max()
max_pe_coi = max(df_f["PE_COI"].max(), 1)   # positive-only max

max_ce_oi  = df_f["CE_OI"].max()
max_ce_coi = max(df_f["CE_COI"].max(), 1)   # positive-only max

support = df_f.copy()
support["Score"] = support.apply(
    lambda r: strike_score(
        r["PE_OI"], r["PE_COI"], r["STRIKE"],
        max_pe_oi, max_pe_coi
    ), axis=1
)

resistance = df_f.copy()
resistance["Score"] = resistance.apply(
    lambda r: strike_score(
        r["CE_OI"], r["CE_COI"], r["STRIKE"],
        max_ce_oi, max_ce_coi
    ), axis=1
)

top_support    = support.sort_values("Score", ascending=False).head(5)
top_resistance = resistance.sort_values("Score", ascending=False).head(5)

bull_score = round(top_support["Score"].head(3).mean(), 1)
bear_score = round(top_resistance["Score"].head(3).mean(), 1)

# ── Confidence ────────────────────────────────────────────────────────────────
# FIX #3: confidence = how decisively one side dominates,
#   NOT the average of both sides.
#   When both sides are strong → market is split → low confidence.
#   When one side clearly dominates → high confidence.
total_score = bull_score + bear_score
dominance   = abs(bull_score - bear_score)
confidence  = round(min(100, (dominance / total_score) * 100), 1) if total_score > 0 else 0.0

# ── Bias ──────────────────────────────────────────────────────────────────────
# FIX #4: incorporate OI PCR into bias so it is not solely from strike scores.
#   OI PCR > 1.2 → PCR says bullish (+1)
#   OI PCR < 0.8 → PCR says bearish (-1)
#   Otherwise neutral (0)
pcr_vote   = 1 if oi_pcr > 1.2 else (-1 if oi_pcr < 0.8 else 0)
score_vote = 1 if bull_score > bear_score else -1
combined   = pcr_vote + score_vote

if combined > 0:
    bias = "BULLISH"
elif combined < 0:
    bias = "BEARISH"
else:
    bias = "NEUTRAL"

# ── Metrics row ───────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Bull Score",  bull_score)
c2.metric("Bear Score",  bear_score)
c3.metric("Confidence",  f"{confidence}%")
c4.metric("Market Bias", bias)

st.divider()

# ── Support / Resistance tables ───────────────────────────────────────────────
c1, c2 = st.columns(2)

with c1:
    st.subheader("🟢 Top 5 Supports")
    st.dataframe(
        top_support[["STRIKE", "PE_OI", "PE_COI", "Score"]],
        use_container_width=True,
        hide_index=True
    )

with c2:
    st.subheader("🔴 Top 5 Resistances")
    st.dataframe(
        top_resistance[["STRIKE", "CE_OI", "CE_COI", "Score"]],
        use_container_width=True,
        hide_index=True
    )

st.divider()

# ── PCR row ───────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.metric("OI PCR",  f"{oi_pcr:.2f}")
# COI PCR shown with sign; negative = CE side is unwinding more than PE
c2.metric("COI PCR", f"{coi_pcr:.2f}")
c3.metric("VOL PCR", f"{vol_pcr:.2f}")

# ── Smart Money ───────────────────────────────────────────────────────────────
# FIX #5: weight by volume (sum of qualifying volumes) rather than a raw count
#   of strikes.  Volume-weighted smart money is far more meaningful than "how
#   many strikes qualify."
#   Condition: Vol > 1.5 × |COI|  AND  COI > 0  (fresh writing with heavy flow)
ce_smart_mask = (df_f["CE_VOL"] > df_f["CE_COI"].abs() * 1.5) & (df_f["CE_COI"] > 0)
pe_smart_mask = (df_f["PE_VOL"] > df_f["PE_COI"].abs() * 1.5) & (df_f["PE_COI"] > 0)

smart_ce_vol = int(df_f.loc[ce_smart_mask, "CE_VOL"].sum())
smart_pe_vol = int(df_f.loc[pe_smart_mask, "PE_VOL"].sum())

st.divider()

c1, c2 = st.columns(2)
c1.metric("🔥 CE Smart Money (Vol)", f"{smart_ce_vol:,}")
c2.metric("🔥 PE Smart Money (Vol)", f"{smart_pe_vol:,}")

# ── Final Signal ──────────────────────────────────────────────────────────────
# FIX #6: normalize score so thresholds are stable regardless of absolute
#   score magnitudes.  Use percentage share of total rather than raw difference.
#   Also fold in smart-money vote so the metric is not wasted.
net_score = bull_score - bear_score

# Normalised score: -100 to +100
norm_score = (net_score / total_score * 100) if total_score > 0 else 0

# Smart money vote: PE > CE → slight bullish lean, vice-versa bearish
sm_vote = 0
if smart_pe_vol > smart_ce_vol * 1.2:
    sm_vote = 1
elif smart_ce_vol > smart_pe_vol * 1.2:
    sm_vote = -1

# Adjusted score with smart-money nudge (10-point nudge at most)
adj_score = norm_score + sm_vote * 10

if adj_score > 30:
    signal = "STRONG BUY CE"
elif adj_score > 10:
    signal = "BUY CE"
elif adj_score < -30:
    signal = "STRONG BUY PE"
elif adj_score < -10:
    signal = "BUY PE"
else:
    signal = "NEUTRAL"

st.divider()

# Show diagnostic details so you can calibrate thresholds from real data
with st.expander("Signal Diagnostics"):
    st.write(f"Raw score diff  : {net_score:.1f}")
    st.write(f"Normalised score: {norm_score:.1f}")
    st.write(f"Smart Money vote: {sm_vote:+d}")
    st.write(f"Adjusted score  : {adj_score:.1f}")
    st.write(f"PCR vote        : {pcr_vote:+d}")
    st.write(f"Score vote      : {score_vote:+d}")

st.success(f"Final Signal : {signal}")

# ==== EARLY SIGNAL IMPROVEMENTS ====
# Fresh writing ratios
df_f["CE_FRESH_RATIO"]=df_f["CE_COI"].clip(lower=0)/(df_f["CE_OI"].replace(0,1))
df_f["PE_FRESH_RATIO"]=df_f["PE_COI"].clip(lower=0)/(df_f["PE_OI"].replace(0,1))

fresh_ce=df_f["CE_FRESH_RATIO"].mean()
fresh_pe=df_f["PE_FRESH_RATIO"].mean()

st.divider()
a,b=st.columns(2)
a.metric("Fresh CE Writing",f"{fresh_ce*100:.1f}%")
b.metric("Fresh PE Writing",f"{fresh_pe*100:.1f}%")

if fresh_pe>fresh_ce*1.2 and bias!="BEARISH":
    st.info("🟢 Early Bullish Build-up: Fresh PE writing is increasing before price confirmation.")
elif fresh_ce>fresh_pe*1.2 and bias!="BULLISH":
    st.info("🔴 Early Bearish Build-up: Fresh CE writing is increasing before price confirmation.")

