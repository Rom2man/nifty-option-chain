import streamlit as st
import pandas as pd
import math

st.set_page_config(page_title="Chart", page_icon="📈", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 0.6rem !important; padding-bottom: 0.5rem !important; }
    .stTabs [data-baseweb="tab"] { font-size: 0.82rem; padding: 4px 16px; }
</style>
""", unsafe_allow_html=True)

def mround(val, multiple):
    return math.floor(val / multiple + 0.5) * multiple

# ── Gate: same pattern as Decision 2 ─────────────────────────────────────────
if "raw_data" not in st.session_state or st.session_state.raw_data is None:
    st.warning("Open the main Option Chain page first to load live data.")
    st.stop()

raw     = st.session_state.raw_data
records = raw.get("records", {})
spot    = records.get("underlyingValue", 0)
pivot   = st.session_state.get("open_price", mround(spot, 50))
atm     = mround(spot, 50)

# ── Parse: identical to Decision 2 ───────────────────────────────────────────
rows = []
for item in records.get("data", []):
    ce     = item.get("CE", {})
    pe     = item.get("PE", {})
    strike = item.get("strikePrice", 0)
    if strike == 0:
        continue
    rows.append({
        "STRIKE": strike,
        "CE_OI":  ce.get("openInterest", 0),
        "CE_COI": ce.get("changeinOpenInterest", 0),
        "CE_VOL": ce.get("totalTradedVolume", 0),
        "CE_IV":  ce.get("impliedVolatility", 0),
        "PE_OI":  pe.get("openInterest", 0),
        "PE_COI": pe.get("changeinOpenInterest", 0),
        "PE_VOL": pe.get("totalTradedVolume", 0),
        "PE_IV":  pe.get("impliedVolatility", 0),
    })

df_full = pd.DataFrame(rows).sort_values("STRIKE").reset_index(drop=True)

if df_full.empty:
    st.error("No strike data found in raw_data. Check main page fetch.")
    st.stop()

# ── Header metrics ────────────────────────────────────────────────────────────
st.markdown("### 📈 Option Chain Charts")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Spot",    f"{spot:,.0f}")
c2.metric("ATM",     f"{atm:,.0f}")
c3.metric("Pivot",   f"{pivot:,.0f}")
c4.metric("Strikes", len(df_full))
c5.metric("Chain",   f"{df_full['STRIKE'].min():.0f}–{df_full['STRIKE'].max():.0f}")
st.markdown("---")

# ── Strike range control ──────────────────────────────────────────────────────
rng_col, _, _ = st.columns([2, 2, 3])
with rng_col:
    strike_range = st.select_slider(
        "Strike range around ATM",
        options=[100, 150, 200, 250, 300, 400, 500],
        value=250,
    )

df = df_full[
    (df_full["STRIKE"] >= atm - strike_range) &
    (df_full["STRIKE"] <= atm + strike_range)
].copy().reset_index(drop=True)

if df.empty:
    st.error(f"No strikes in range {atm-strike_range}–{atm+strike_range}. Increase range.")
    st.stop()

df["COI_DIFF"] = df["PE_COI"] - df["CE_COI"]
strikes = df["STRIKE"].tolist()

# ── Plotly availability ───────────────────────────────────────────────────────
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False
    st.info("Plotly not available — using built-in charts. Add `plotly` to requirements.txt")

# ── Constants ─────────────────────────────────────────────────────────────────
PAPER_BG  = "rgba(14,17,23,1)"
PLOT_BG   = "rgba(20,24,33,1)"
GRID_COL  = "rgba(255,255,255,0.07)"
CE_COL    = "#ef5350"
PE_COL    = "#26a69a"
DIFF_COL  = "#ab47bc"
SPOT_COL  = "#ffd54f"
ATM_FILL  = "rgba(255,213,79,0.07)"

def base_layout(title, height=420):
    return dict(
        template="plotly_dark",
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        height=height,
        margin=dict(l=65, r=25, t=42, b=45),
        title=dict(text=title, font=dict(size=13, color="#cccccc"), x=0.01),
        legend=dict(orientation="h", x=0, y=1.14,
                    font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=True, gridcolor=GRID_COL, zeroline=False,
                   tickfont=dict(size=10), title="Strike Price"),
        yaxis=dict(showgrid=True, gridcolor=GRID_COL, zeroline=False,
                   tickfont=dict(size=10)),
        hovermode="x unified",
    )

def vlines(fig, row=None, col=None):
    kw = {"row": row, "col": col} if row else {}
    fig.add_vline(x=spot, line_dash="dash", line_color=SPOT_COL,
                  line_width=1.8, opacity=0.9,
                  annotation_text=f"Spot {spot:.0f}",
                  annotation_font=dict(size=9, color=SPOT_COL),
                  annotation_position="top right", **kw)
    fig.add_vrect(x0=atm-25, x1=atm+25,
                  fillcolor=ATM_FILL, line_width=0, **kw)

# ═══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 OI — CE vs PE",
    "📊 COI — CE vs PE",
    "📊 COI Difference",
    "📊 All-in-One",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1  —  Open Interest
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    if HAS_PLOTLY:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=strikes, y=df["CE_OI"].tolist(),
            mode="lines+markers", name="CE OI  (Call / Resistance)",
            line=dict(color=CE_COL, width=2.5), marker=dict(size=5),
            fill="tozeroy", fillcolor="rgba(239,83,80,0.10)",
            hovertemplate="Strike %{x:,.0f}<br>CE OI: %{y:,.0f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=strikes, y=df["PE_OI"].tolist(),
            mode="lines+markers", name="PE OI  (Put / Support)",
            line=dict(color=PE_COL, width=2.5), marker=dict(size=5),
            fill="tozeroy", fillcolor="rgba(38,166,154,0.10)",
            hovertemplate="Strike %{x:,.0f}<br>PE OI: %{y:,.0f}<extra></extra>",
        ))
        lay = base_layout("Open Interest — CE (Call) vs PE (Put)")
        lay["yaxis"]["title"] = "OI (contracts)"
        fig.update_layout(**lay)
        vlines(fig)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.line_chart(df.set_index("STRIKE")[["CE_OI", "PE_OI"]])

    mx_ce = df.loc[df["CE_OI"].idxmax()]
    mx_pe = df.loc[df["PE_OI"].idxmax()]
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Max CE OI Strike", f"{int(mx_ce['STRIKE']):,}", help="Key Resistance")
    m2.metric("CE OI",            f"{int(mx_ce['CE_OI']):,}")
    m3.metric("Max PE OI Strike", f"{int(mx_pe['STRIKE']):,}", help="Key Support")
    m4.metric("PE OI",            f"{int(mx_pe['PE_OI']):,}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2  —  Change in OI
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    if HAS_PLOTLY:
        fig = go.Figure()
        fig.add_hline(y=0, line_color="rgba(255,255,255,0.2)", line_width=1)
        fig.add_trace(go.Bar(
            x=strikes, y=df["CE_COI"].tolist(),
            name="CE COI bars", marker_color="rgba(239,83,80,0.22)",
            showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Bar(
            x=strikes, y=df["PE_COI"].tolist(),
            name="PE COI bars", marker_color="rgba(38,166,154,0.22)",
            showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=strikes, y=df["CE_COI"].tolist(),
            mode="lines+markers", name="CE COI  (Call Δ OI)",
            line=dict(color=CE_COL, width=2.5), marker=dict(size=5),
            hovertemplate="Strike %{x:,.0f}<br>CE ΔCOI: %{y:,.0f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=strikes, y=df["PE_COI"].tolist(),
            mode="lines+markers", name="PE COI  (Put Δ OI)",
            line=dict(color=PE_COL, width=2.5), marker=dict(size=5),
            hovertemplate="Strike %{x:,.0f}<br>PE ΔCOI: %{y:,.0f}<extra></extra>",
        ))
        lay = base_layout("Change in OI (COI) — CE vs PE")
        lay["yaxis"]["title"] = "Δ OI (contracts)"
        lay["barmode"] = "overlay"
        fig.update_layout(**lay)
        vlines(fig)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.line_chart(df.set_index("STRIKE")[["CE_COI", "PE_COI"]])

    mx_ce2 = df.loc[df["CE_COI"].abs().idxmax()]
    mx_pe2 = df.loc[df["PE_COI"].abs().idxmax()]
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("Max |CE COI| Strike", f"{int(mx_ce2['STRIKE']):,}")
    m2.metric("CE COI",              f"{int(mx_ce2['CE_COI']):,}")
    m3.metric("Max |PE COI| Strike", f"{int(mx_pe2['STRIKE']):,}")
    m4.metric("PE COI",              f"{int(mx_pe2['PE_COI']):,}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3  —  COI Difference (PE − CE)
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    if HAS_PLOTLY:
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            row_heights=[0.68, 0.32], vertical_spacing=0.07,
            subplot_titles=(
                "PE COI − CE COI  (Green = PE dominates = Bullish | Red = CE dominates = Bearish)",
                "OI context — CE vs PE"
            )
        )
        diff_vals  = df["COI_DIFF"].tolist()
        bar_colors = [PE_COL if v >= 0 else CE_COL for v in diff_vals]

        fig.add_trace(go.Bar(
            x=strikes, y=diff_vals, name="PE COI − CE COI",
            marker_color=bar_colors, opacity=0.85,
            hovertemplate="Strike %{x:,.0f}<br>Diff: %{y:,.0f}<extra></extra>",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=strikes, y=diff_vals, mode="lines",
            name="Diff trend", line=dict(color=DIFF_COL, width=2),
            hoverinfo="skip",
        ), row=1, col=1)
        fig.add_hline(y=0, line_color="rgba(255,255,255,0.25)",
                      line_width=1, row=1, col=1)

        fig.add_trace(go.Scatter(
            x=strikes, y=df["CE_OI"].tolist(), mode="lines",
            name="CE OI", line=dict(color=CE_COL, width=1.5, dash="dot"),
        ), row=2, col=1)
        fig.add_trace(go.Scatter(
            x=strikes, y=df["PE_OI"].tolist(), mode="lines",
            name="PE OI", line=dict(color=PE_COL, width=1.5, dash="dot"),
        ), row=2, col=1)

        fig.update_layout(
            template="plotly_dark", paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
            height=530, margin=dict(l=65, r=25, t=55, b=45),
            legend=dict(orientation="h", x=0, y=1.10,
                        font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
            hovermode="x unified", barmode="relative",
        )
        fig.update_xaxes(showgrid=True, gridcolor=GRID_COL,
                         tickfont=dict(size=10), title_text="Strike Price", row=2, col=1)
        fig.update_yaxes(showgrid=True, gridcolor=GRID_COL, tickfont=dict(size=10))
        fig.update_yaxes(title_text="PE−CE COI", row=1, col=1)
        fig.update_yaxes(title_text="OI", row=2, col=1)

        for r in [1, 2]:
            fig.add_vline(x=spot, line_dash="dash", line_color=SPOT_COL,
                          line_width=1.6, opacity=0.85, row=r, col=1)
            fig.add_vrect(x0=atm-25, x1=atm+25,
                          fillcolor=ATM_FILL, line_width=0, row=r, col=1)

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(df.set_index("STRIKE")[["COI_DIFF"]])

    total_diff  = int(df["COI_DIFF"].sum())
    pos_strikes = int((df["COI_DIFF"] > 0).sum())
    neg_strikes = int((df["COI_DIFF"] < 0).sum())
    bias = "🟢 PE Dominated — Bullish Bias" if total_diff > 0 else "🔴 CE Dominated — Bearish Bias"
    st.info(
        f"**Net COI Diff (PE−CE): {total_diff:,}** | {bias}  \n"
        f"Strikes PE > CE: **{pos_strikes}** &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Strikes CE > PE: **{neg_strikes}**"
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4  —  All-in-One 2×2
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    if HAS_PLOTLY:
        fig = make_subplots(
            rows=2, cols=2,
            vertical_spacing=0.16, horizontal_spacing=0.10,
            subplot_titles=(
                "OI — CE vs PE",
                "COI — CE vs PE",
                "COI Diff (PE−CE)",
                "IV — CE vs PE",
            )
        )

        def add(tr, r, c): fig.add_trace(tr, row=r, col=c)

        add(go.Scatter(x=strikes, y=df["CE_OI"].tolist(), mode="lines",
            name="CE OI", line=dict(color=CE_COL, width=2),
            fill="tozeroy", fillcolor="rgba(239,83,80,0.08)",
            hovertemplate="CE OI: %{y:,.0f}<extra></extra>"), 1, 1)
        add(go.Scatter(x=strikes, y=df["PE_OI"].tolist(), mode="lines",
            name="PE OI", line=dict(color=PE_COL, width=2),
            fill="tozeroy", fillcolor="rgba(38,166,154,0.08)",
            hovertemplate="PE OI: %{y:,.0f}<extra></extra>"), 1, 1)

        add(go.Scatter(x=strikes, y=df["CE_COI"].tolist(), mode="lines",
            name="CE COI", line=dict(color=CE_COL, width=2),
            hovertemplate="CE COI: %{y:,.0f}<extra></extra>"), 1, 2)
        add(go.Scatter(x=strikes, y=df["PE_COI"].tolist(), mode="lines",
            name="PE COI", line=dict(color=PE_COL, width=2),
            hovertemplate="PE COI: %{y:,.0f}<extra></extra>"), 1, 2)

        add(go.Bar(x=strikes, y=df["COI_DIFF"].tolist(), name="Diff",
            marker_color=[PE_COL if v >= 0 else CE_COL for v in df["COI_DIFF"].tolist()],
            opacity=0.85,
            hovertemplate="Diff: %{y:,.0f}<extra></extra>"), 2, 1)

        add(go.Scatter(x=strikes, y=df["CE_IV"].tolist(), mode="lines",
            name="CE IV", line=dict(color=CE_COL, width=2, dash="dot"),
            hovertemplate="CE IV: %{y:.1f}<extra></extra>"), 2, 2)
        add(go.Scatter(x=strikes, y=df["PE_IV"].tolist(), mode="lines",
            name="PE IV", line=dict(color=PE_COL, width=2, dash="dot"),
            hovertemplate="PE IV: %{y:.1f}<extra></extra>"), 2, 2)

        fig.update_layout(
            template="plotly_dark", paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
            height=650, margin=dict(l=55, r=15, t=60, b=40),
            showlegend=True,
            legend=dict(orientation="h", x=0, y=1.07,
                        font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
            hovermode="x unified", barmode="relative",
        )
        fig.update_xaxes(showgrid=True, gridcolor=GRID_COL,
                         tickfont=dict(size=9), title_text="Strike")
        fig.update_yaxes(showgrid=True, gridcolor=GRID_COL, tickfont=dict(size=9))

        for r, c in [(1,1),(1,2),(2,1),(2,2)]:
            fig.add_vline(x=spot, line_dash="dash", line_color=SPOT_COL,
                          line_width=1.2, opacity=0.75, row=r, col=c)
            fig.add_vrect(x0=atm-25, x1=atm+25,
                          fillcolor=ATM_FILL, line_width=0, row=r, col=c)

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.line_chart(df.set_index("STRIKE")[["CE_OI","PE_OI","CE_COI","PE_COI","CE_IV","PE_IV"]])

# ── Footer ─────────────────────────────────────────────────────────────────────
st.caption(
    f"Source: live raw_data snapshot (same fetch as main page) | "
    f"Spot: **{spot:,.0f}** | ATM: **{atm:,.0f}** | "
    f"Showing: **{atm-strike_range:,} – {atm+strike_range:,}** | "
    f"Strikes plotted: **{len(df)}**"
)
