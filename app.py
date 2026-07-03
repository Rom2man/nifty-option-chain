import streamlit as st
import requests
import pandas as pd
import time
import math
from datetime import datetime
import plotly.graph_objects as go

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
    .oc-table { width:100%; border-collapse:collapse; font-size:13px; font-weight:600; }
    .oc-table th { background:#1565C0; color:white; padding:6px 4px; text-align:center; font-size:12px; font-weight:700; border:1px solid #1976D2; }
    .oc-table td { padding:4px 5px; text-align:center; border:1px solid #E0E0E0; font-size:13px; font-weight:600; white-space:nowrap; }
    .oc-table tr:hover td