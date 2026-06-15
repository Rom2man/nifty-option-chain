import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Chart", page_icon="📈", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 0.6rem !important; padding-bottom: 0.6rem !important; }
    h1 { font-size: 1.2rem !important; margin-bottom: 0.2rem !important; }
    .stTabs [data-baseweb="tab"] { font-size: 0.82rem; padding: 4px 14px; }
    .chart-title {
        font-size: 0.72rem; font-weight: 700; color: #aaa;
        text-transform: uppercase; letter-spacing: 0.06em;
        margin: 8px 0 2px 0;
    }
</style>
""", unsafe_allow_html=True)

# ── Helpers ──────────────────────────────────────────────────────────────────
def mround(val, multiple):
    return math.floor(val / multiple + 0.5) * multiple

CHART_THEME = "plotly_dark"
GRID_COLOR  = "rgba(255,255,255,0.07)"
PAPER_BG    = "rgba(14,17,23,1)"
PLOT_BG     = "rgba(20,24,33,1)"
CE_COLOR    = "#ef5350"   # red  — call (resist