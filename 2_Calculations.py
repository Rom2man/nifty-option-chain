import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="Calculations", page_icon="📊", layout="wide")

st.markdown("""
<style>
    .calc-header {
        background:linear-gradient(90deg,#1565C0,#1976D2);
        padding:12px 20px; border-radius:10px; color:white;
        font-size:20px; font-weight:bold; margin-bottom:16px;
    }
    .section-hdr {
        background:#F5F5F5; border-left:4px solid #1565C0;
        padding:8px 14px; font-size:15px; font-weight:700;
        color:#1565C0; margin:14px 0 8px 0; border-radius:0 6px 6px 0;
    }
    div[data-testid="metric-container"] {
        background:#F8F9FA; border:1px solid #E0E0E0;
        border-radius:8px; padding:10px !important;
    }
    div[data-testid="stMetricValue"] {
        font-size:20px !important; font-weight:800 !important; color:#1565C0 !important;
    }
    .rec-table { width:100%; border-collapse:collapse; }
    .rec-table th {
        background:#1565C0; color:white; padding:8px 10px;
        text-align:center; font-size:13px; font-weight:700; border:1px solid #1976D2;
    }
    .rec-table td {
        padding:7px 10px; text-align:center;
        border:1px solid #E0E0E0; font-size:13px; font-weight:600;
    }
    /* Force centering on Streamlit Dataframes */
    [data-testid="stDataFrame"] td { text-align: center !important; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="calc-header">📊 Calculations & Analysis Dashboard</div>',
            unsafe_allow_html=True)

# ── Check data ────────────────────────────────────────────
if "raw_data" not in st.session_state or st.session_state.raw_data is None:
    st.warning("⚠️ No data yet! Please go to the **Main Page** first and wait for data to load.")
    st.stop()

def mround(val,multiple): return math.floor(val/multiple+0.5)*multiple
def fmt_oi(v):
    try:
        v=float(v)
        if v>=10_000_000: return f"{v/10_000_000:.2f}Cr"
        if v>=100_000: return f"{v/100_000:.2f}L"
        return f"{int(v):,}"
    except: return str(v)
def excel_growth(oi,coi):
    try:
        oi=float(oi); coi=float(coi); diff=oi-coi
        if diff==0: return 0.0
        return round(((oi/diff)-1.0)*(1.0 if diff>0 else -1.0)*100.0,4)
    except: return 0.0

# Parse
raw=st.session_state.raw_data
records=raw.get("records",{})
spot=records.get("underlyingValue",0)
open_price=st.session_state.get("open_price",mround(spot,50))
open_spot=st.session_state.get("open_spot",spot)
prev_close=st.session_state.get("prev_close",0)
atm_strike=mround(spot,50)
multiplier=st.session_state.get("oi_multiplier",50)
futures=st.session_state.get("futures",[])
history=st.session_state.get("history",[])

rows=[]
for item in records.get("data",[]):
    ce=item.get("CE",{}); pe=item.get("PE",{})
    rows.append({"STRIKE":item.get("strikePrice",0),
        "CE_OI":ce.get("openInterest",0),"CE_COI":ce.get("changeinOpenInterest",0),
        "CE_PCOI":ce.get("pchangeinOpenInterest",0),
        "CE_VOL":ce.get("totalTradedVolume",0),"CE_IV":ce.get("impliedVolatility",0),"CE_LTP":ce.get("lastPrice",0),
        "PE_OI":pe.get("openInterest",0),"PE_COI":pe.get("changeinOpenInterest",0),
        "PE_PCOI":pe.get("pchangeinOpenInterest",0),
        "PE_VOL":pe.get("totalTradedVolume",0),"PE_IV":pe.get("impliedVolatility",0),"PE_LTP":pe.get("lastPrice",0)})
df=pd.DataFrame(rows)
lo=open_price-250; hi=open_price+250
df_f=df[(df["STRIKE"]>=lo)&(df["STRIKE"]<=hi)].copy().reset_index(drop=True)
tot={k:df_f[k].sum() for k in ["CE_OI","CE_COI","CE_VOL","PE_OI","PE_COI","PE_VOL"]}
df_f["PE_GR"]=df_f.apply(lambda r:excel_growth(r["PE_OI"],r["PE_COI"]),axis=1)
df_f["CE_GR"]=df_f.apply(lambda r:excel_growth(r["CE_OI"],r["CE_COI"]),axis=1)
df_f["CE_COV"]=df_f.apply(lambda r:r["CE_COI"]/r["CE_VOL"] if r["CE_VOL"] else 0,axis=1)
df_f["PE_COV"]=df_f.apply(lambda r:r["PE_COI"]/r["PE_VOL"] if r["PE_VOL"] else 0,axis=1)

chng=round(spot-prev_close,2) if prev_close else 0
avijit_op=round((df_f["PE_COV"].sum()-df_f["CE_COV"].sum())*65,2)
oi_tracker=round(((tot["PE_OI"]-tot["CE_OI"])/100000)*multiplier,2)
pcr_oi=round(tot["PE_OI"]/tot["CE_OI"],4) if tot["CE_OI"] else 0
pcr_vol=round(tot["PE_VOL"]/tot["CE_VOL"],4) if tot["CE_VOL"] else 0
pcr_coi=round(tot["PE_COI"]/tot["CE_COI"],4) if tot["CE_COI"] else 0
pe_iv_sum=round(df_f["PE_IV"].sum(),2)
ce_iv_sum=round(df_f["CE_IV"].sum(),2)
pe_coi_g=round(df_f["PE_GR"].sum(),2)
ce_coi_g=round(df_f["CE_GR"].sum(),2)
all_s=df_f.sort_values("STRIKE",ascending=True)["STRIKE"].tolist()

atm_idx=next((i for i,s in enumerate(all_s) if s==atm_strike), None)
if atm_idx is None:
    atm_idx=next((i for i,s in enumerate(all_s) if s>=atm_strike),len(all_s)//2)

itm_pe_strikes=all_s[atm_idx:atm_idx+6]
itm_ce_strikes=all_s[max(0,atm_idx-5):atm_idx+1]
itm_pe=round(df_f[df_f["STRIKE"].isin(itm_pe_strikes)]["PE_PCOI"].sum(),2)
itm_ce=round(df_f[df_f["STRIKE"].isin(itm_ce_strikes)]["CE_PCOI"].sum(),2)

def pcr_signal(v):
    if v>1.2: return "🟢 Bullish"
    if v<0.8: return "🔴 Bearish"
    return "🟡 Sideways"

# ── Section 1: Key Metrics ────────────────────────────────
st.markdown('<div class="section-hdr">📡 Key Metrics</div>',unsafe_allow_html=True)
r1=st.columns(6)
r1[0].metric("📍 Spot",f"₹{spot:,.2f}")
r1[1].metric("📉 Chng",f"{chng:+.2f}",delta_color="normal" if chng>=0 else "inverse")
r1[2].metric("🎯 Avijit OP",f"{avijit_op:+.2f}",delta="Bull" if avijit_op>=0 else "Bear",delta_color="normal" if avijit_op>=0 else "inverse")
r1[3].metric("📊 OI Tracker",f"{oi_tracker:+.2f}",delta="Bull" if oi_tracker>=0 else "Bear",delta_color="normal" if oi_tracker>=0 else "inverse")
r1[4].metric("🔺 PE COI Gr",f"{pe_coi_g:+.2f}",delta_color="normal" if pe_coi_g>=0 else "inverse")
r1[5].metric("🔻 CE COI Gr",f"{ce_coi_g:+.2f}",delta_color="normal" if ce_coi_g>=0 else "inverse")
r2=st.columns(6)
r2[0].metric("📈 PE IV",f"{pe_iv_sum:.1f}")
r2[1].metric("📉 CE IV",f"{ce_iv_sum:.1f}")
r2[2].metric("💰 ITM PE",f"{itm_pe:+.2f}",delta_color="normal" if itm_pe>=0 else "inverse")
r2[3].metric("💰 ITM CE",f"{itm_ce:+.2f}",delta_color="normal" if itm_ce>=0 else "inverse")
r2[4].metric("⚖️ PCR OI",f"{pcr_oi:.4f}",delta=pcr_signal(pcr_oi))
r2[5].metric("⚖️ PCR VOL",f"{pcr_vol:.4f}",delta=pcr_signal(pcr_vol))

# ── Section 2: PCR Dashboard ──────────────────────────────
st.markdown('<div class="section-hdr">⚖️ PCR Dashboard</div>',unsafe_allow_html=True)
p1,p2,p3,p4=st.columns(4)
p1.metric("PCR OI",   f"{pcr_oi:.4f}",  delta=pcr_signal(pcr_oi))
p2.metric("PCR COI",  f"{pcr_coi:.4f}", delta=pcr_signal(pcr_coi))
p3.metric("PCR VOL",  f"{pcr_vol:.4f}", delta=pcr_signal(pcr_vol))
p4.metric("OI-PCR×100",f"{pcr_oi*100:.2f}")

# ── Section 3: Max Pain ───────────────────────────────────
st.markdown('<div class="section-hdr">📌 Max Pain</div>',unsafe_allow_html=True)
mp_data=[]
for s in df_f["STRIKE"]:
    ce_l=((s-df_f["STRIKE"]).clip(lower=0)*df_f["CE_OI"]).sum()
    pe_l=((df_f["STRIKE"]-s).clip(lower=0)*df_f["PE_OI"]).sum()
    mp_data.append({"STRIKE":int(s),"CE Loss":int(ce_l),"PE Loss":int(pe_l),"Total":int(ce_l+pe_l)})
mp_df=pd.DataFrame(mp_data)
max_pain=mp_df.loc[mp_df["Total"].idxmin(),"STRIKE"]
mp1,mp2,mp3=st.columns(3)
mp1.metric("🎯 Max Pain",f"₹{int(max_pain):,}")
mp2.metric("📍 Spot",f"₹{spot:,.2f}")
mp3.metric("📏 Distance",f"{abs(spot-max_pain):,.1f} pts",
    delta="Above" if spot>max_pain else "Below",
    delta_color="normal" if spot>max_pain else "inverse")
with st.expander("📋 Full Max Pain Table"):
    st.dataframe(mp_df.set_index("STRIKE").style
        .highlight_min(subset=["Total"],color="#A5D6A7")
        .format("{:,.0f}"),use_container_width=True)

# ── Section 4: Support & Resistance ──────────────────────
st.markdown('<div class="section-hdr">🧱 Support & Resistance</div>',unsafe_allow_html=True)
top_pe=df_f.nlargest(3,"PE_OI")[["STRIKE","PE_OI","PE_COI"]].reset_index(drop=True)
top_ce=df_f.nlargest(3,"CE_OI")[["STRIKE","CE_OI","CE_COI"]].reset_index(drop=True)
sr1,sr2=st.columns(2)
with sr1:
    st.markdown("**🟢 Support (High PE OI)**")
    for i,row in top_pe.iterrows():
        st.metric("Primary" if i==0 else f"Secondary {i}",
            f"₹{int(row['STRIKE']):,}",
            delta=f"OI:{fmt_oi(row['PE_OI'])} COI:{fmt_oi(row['PE_COI'])}")
with sr2:
    st.markdown("**🔴 Resistance (High CE OI)**")
    for i,row in top_ce.iterrows():
        st.metric("Primary" if i==0 else f"Secondary {i}",
            f"₹{int(row['STRIKE']):,}",
            delta=f"OI:{fmt_oi(row['CE_OI'])} COI:{fmt_oi(row['CE_COI'])}")

# ── Section 5: ITM Growth Table ───────────────────────────
st.markdown('<div class="section-hdr">💰 ITM Growth Detail</div>',unsafe_allow_html=True)
ig1,ig2=st.columns(2)
with ig1:
    st.markdown(f"**PE ITM — ATM({int(atm_strike)}) + 5 above | Strikes: {[int(s) for s in itm_pe_strikes]} | Total: {itm_pe:+.2f}%**")
    itm_pe_show=df_f[df_f["STRIKE"].isin(itm_pe_strikes)][["STRIKE","PE_OI","PE_COI","PE_PCOI"]].copy()
    itm_pe_show.columns=["Strike","PE OI","PE COI","%COI PE"]
    st.dataframe(itm_pe_show.style
        .format({"PE OI":"{:,.0f}","PE COI":"{:,.0f}","%COI PE":"{:+.4f}"})
        .background_gradient(subset=["%COI PE"],cmap="RdYlGn"),
        use_container_width=True,hide_index=True)
with ig2:
    st.markdown(f"**CE ITM — ATM({int(atm_strike)}) + 5 below | Strikes: {[int(s) for s in itm_ce_strikes]} | Total: {itm_ce:+.2f}%**")
    itm_ce_show=df_f[df_f["STRIKE"].isin(itm_ce_strikes)][["STRIKE","CE_OI","CE_COI","CE_PCOI"]].copy()
    itm_ce_show.columns=["Strike","CE OI","CE COI","%COI CE"]
    st.dataframe(itm_ce_show.style
        .format({"CE OI":"{:,.0f}","CE COI":"{:,.0f}","%COI CE":"{:+.4f}"})
        .background_gradient(subset=["%COI CE"],cmap="RdYlGn"),
        use_container_width=True,hide_index=True)

# ── Section 6: Futures ────────────────────────────────────
if futures:
    st.markdown('<div class="section-hdr">📊 Nifty Futures</div>',unsafe_allow_html=True)
    fc=st.columns(len(futures))
    for i,fut in enumerate(futures):
        fc[i].metric(f"Fut {fut.get('expiry','')[:6]}",
            f"₹{fut.get('ltp',0):,.2f}",
            delta=f"{fut.get('chng',0):+.2f}",
            delta_color="normal" if fut.get('chng',0)>=0 else "inverse")

# ── Section 7: Reference Values ──────────────────────────
st.markdown('<div class="section-hdr">📋 Reference Values (for formula building)</div>',unsafe_allow_html=True)
with st.expander("View all live values",expanded=False):
    ref1,ref2=st.columns(2)
    with ref1:
        st.code(f"""
Spot         = {spot:,.2f}
Day Open     = {open_spot:,.2f}
Prev Close   = {prev_close:,.2f}
ATM Strike   = {atm_strike:,}
Pivot(Open)  = {open_price:,}
Range        = {open_price-250:,} to {open_price+250:,}
Total CE OI  = {fmt_oi(tot['CE_OI'])}
Total PE OI  = {fmt_oi(tot['PE_OI'])}
Total CE COI = {fmt_oi(tot['CE_COI'])}
Total PE COI = {fmt_oi(tot['PE_COI'])}
Total CE VOL = {fmt_oi(tot['CE_VOL'])}
Total PE VOL = {fmt_oi(tot['PE_VOL'])}
PCR OI       = {pcr_oi:.4f}
PCR COI      = {pcr_coi:.4f}
PCR VOL      = {pcr_vol:.4f}
Avijit OP    = {avijit_op:+.2f}
OI Tracker   = {oi_tracker:+.2f}
        """)
    with ref2:
        st.dataframe(
            df_f[["STRIKE","CE_OI","CE_COI","CE_PCOI","CE_VOL","CE_IV",
                  "PE_OI","PE_COI","PE_PCOI","PE_VOL","PE_IV","PE_GR","CE_GR"]]
            .rename(columns={"CE_PCOI":"%COI_CE","PE_PCOI":"%COI_PE","PE_GR":"PE_Gr%","CE_GR":"CE_Gr%"})
            .set_index("STRIKE").style.format("{:.2f}")
            .background_gradient(subset=["PE_Gr%","CE_Gr%"],cmap="RdYlGn"),
            use_container_width=True,height=320)

# ── Section 8: Recording History ─────────────────────────
# 🆕 FIXED: Completely replaced manual HTML building with robust native Pandas Styler
if history:
    st.markdown('<div class="section-hdr">🗂️ Full Recording History</div>',unsafe_allow_html=True)
    
    # 1. Convert history to DataFrame and reverse to show newest first
    hist_df = pd.DataFrame(list(reversed(history)))
    
    # Ensure expected columns exist
    cols_order = ["Spot", "Chng", "Time", "Avijit OP", "OI Tracker", "PCR", 
                  "PE IV", "CE IV", "PE COI Gr", "CE COI Gr", "ITM PE", "ITM CE"]
    # Only keep columns that actually exist in the history dictionary
    cols_order = [c for c in cols_order if c in hist_df.columns]
    hist_df = hist_df[cols_order]

    # 2. Clean Data: Convert to numeric so the color gradient doesn't crash on text ("None")
    for c in hist_df.columns:
        if c not in ["Time", "Spot"]:
            hist_df[c] = pd.to_numeric(hist_df[c], errors='coerce')
            
    if "Spot" in hist_df.columns:
        hist_df["Spot"] = pd.to_numeric(hist_df["Spot"], errors='coerce')

    # 3. Define the columns to apply gradient to based on your logic
    normal_cols = [c for c in hist_df.columns if c in ["Chng", "Avijit OP", "OI Tracker", "PCR", "PE IV", "PE COI Gr", "ITM PE"]]
    reverse_cols = [c for c in hist_df.columns if c in ["CE IV", "CE COI Gr", "ITM CE"]] 

    # 4. Build the Styler (Center Text + Precision)
    styler = hist_df.style.format(precision=2, na_rep="None").set_properties(**{'text-align': 'center'})
    
    if "Spot" in hist_df.columns:
        styler = styler.format({"Spot": "₹{:,.2f}"})
        
    # Apply standard Red->Yellow->Green scale to "Bullish" metrics
    if normal_cols:
        styler = styler.background_gradient(subset=normal_cols, cmap="RdYlGn")
    # Apply reversed Green->Yellow->Red scale to "Bearish" metrics
    if reverse_cols:
        styler = styler.background_gradient(subset=reverse_cols, cmap="RdYlGn_r") 

    # 5. Render to Streamlit natively
    st.dataframe(styler, use_container_width=True, hide_index=True)
    
    csv = hist_df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", csv, "nifty_history.csv", "text/csv")
else:
    st.info("No recording history yet. Start recording from the main page.")