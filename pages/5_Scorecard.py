
import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="Scorecard", page_icon="📊", layout="wide")

st.title("📊 Scorecard")

def mround(val,multiple):
    return math.floor(val/multiple+0.5)*multiple

raw_data = st.session_state.get("raw_data")

if raw_data is None:
    st.warning("Open the main Option Chain page first.")
    st.stop()

rec = raw_data.get("records",{})
spot = rec.get("underlyingValue",0)

rows=[]
for item in rec.get("data",[]):
    ce=item.get("CE",{})
    pe=item.get("PE",{})
    rows.append({
        "STRIKE":item.get("strikePrice",0),
        "CE_OI":ce.get("openInterest",0),
        "CE_COI":ce.get("changeinOpenInterest",0),
        "CE_VOL":ce.get("totalTradedVolume",0),
        "CE_IV":ce.get("impliedVolatility",0),
        "PE_OI":pe.get("openInterest",0),
        "PE_COI":pe.get("changeinOpenInterest",0),
        "PE_VOL":pe.get("totalTradedVolume",0),
        "PE_IV":pe.get("impliedVolatility",0),
    })

df=pd.DataFrame(rows)

open_strike = st.session_state.get("open_price", mround(spot,50))
atm_strike = mround(spot,50)

df_f = df[(df["STRIKE"]>=open_strike-250) & (df["STRIKE"]<=open_strike+250)].copy()

if df_f.empty:
    st.warning("No strikes available.")
    st.stop()

tot_ce_oi=df_f["CE_OI"].sum()
tot_pe_oi=df_f["PE_OI"].sum()
tot_ce_coi=df_f["CE_COI"].sum()
tot_pe_coi=df_f["PE_COI"].sum()
tot_ce_vol=df_f["CE_VOL"].sum()
tot_pe_vol=df_f["PE_VOL"].sum()

oi_pcr  = tot_pe_oi/max(tot_ce_oi,1)
coi_pcr = tot_pe_coi/max(abs(tot_ce_coi),1)
vol_pcr = tot_pe_vol/max(tot_ce_vol,1)

def strike_score(oi,coi,strike,max_oi,max_coi):
    doi=(abs(coi)/max_coi)*50 if max_coi else 0
    oi_s=(oi/max_oi)*30 if max_oi else 0
    prox=max(0,1-abs(strike-atm_strike)/250)*20
    return round(doi+oi_s+prox,2)

max_pe_oi=df_f["PE_OI"].max()
max_pe_coi=max(df_f["PE_COI"].abs().max(),1)

max_ce_oi=df_f["CE_OI"].max()
max_ce_coi=max(df_f["CE_COI"].abs().max(),1)

support=df_f.copy()
support["Score"]=support.apply(
    lambda r: strike_score(
        r["PE_OI"],r["PE_COI"],r["STRIKE"],
        max_pe_oi,max_pe_coi
    ),axis=1
)

resistance=df_f.copy()
resistance["Score"]=resistance.apply(
    lambda r: strike_score(
        r["CE_OI"],r["CE_COI"],r["STRIKE"],
        max_ce_oi,max_ce_coi
    ),axis=1
)

top_support=support.sort_values("Score",ascending=False).head(5)
top_resistance=resistance.sort_values("Score",ascending=False).head(5)

bull_score=round(top_support["Score"].head(3).mean(),1)
bear_score=round(top_resistance["Score"].head(3).mean(),1)

confidence=round(min(100,(bull_score+bear_score)/2),1)

bias="BULLISH" if bull_score>bear_score else "BEARISH"

c1,c2,c3,c4=st.columns(4)
c1.metric("Bull Score",bull_score)
c2.metric("Bear Score",bear_score)
c3.metric("Confidence",f"{confidence}%")
c4.metric("Market Bias",bias)

st.divider()

c1,c2=st.columns(2)

with c1:
    st.subheader("🟢 Top 5 Supports")
    st.dataframe(
        top_support[["STRIKE","PE_OI","PE_COI","Score"]],
        use_container_width=True,
        hide_index=True
    )

with c2:
    st.subheader("🔴 Top 5 Resistances")
    st.dataframe(
        top_resistance[["STRIKE","CE_OI","CE_COI","Score"]],
        use_container_width=True,
        hide_index=True
    )

st.divider()

c1,c2,c3=st.columns(3)
c1.metric("OI PCR",f"{oi_pcr:.2f}")
c2.metric("COI PCR",f"{coi_pcr:.2f}")
c3.metric("VOL PCR",f"{vol_pcr:.2f}")

smart_ce=((df_f["CE_VOL"] > abs(df_f["CE_COI"])*1.5) & (df_f["CE_COI"]>0)).sum()
smart_pe=((df_f["PE_VOL"] > abs(df_f["PE_COI"])*1.5) & (df_f["PE_COI"]>0)).sum()

st.divider()

c1,c2=st.columns(2)
c1.metric("🔥 CE Smart Money",int(smart_ce))
c2.metric("🔥 PE Smart Money",int(smart_pe))

score=(bull_score-bear_score)

if score>15:
    signal="STRONG BUY CE"
elif score>5:
    signal="BUY CE"
elif score<-15:
    signal="STRONG BUY PE"
elif score<-5:
    signal="BUY PE"
else:
    signal="NEUTRAL"

st.divider()
st.success(f"Final Signal : {signal}")
