import streamlit as st
import pandas as pd

st.set_page_config(page_title='Scorecard', page_icon='📊', layout='wide')
st.title('📊 Scorecard')

st.markdown('''
### Score Formula
Score = ΔOI × 50% + OI Strength × 30% + ATM Proximity × 20%
''')

def calculate_score(oi, coi, strike, atm, max_oi, max_coi, max_dist=250):
    doi_score = abs(coi) / max_coi if max_coi else 0
    oi_score = oi / max_oi if max_oi else 0
    prox_score = max(0, 1 - abs(strike - atm) / max_dist)
    return round(doi_score * 50 + oi_score * 30 + prox_score * 20, 2)

st.info('Template page. Replace sample dataframe with your df_f from app.py')
