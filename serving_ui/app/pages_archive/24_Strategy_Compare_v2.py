import numpy as np
import pandas as pd
import streamlit as st
from serving_ui.app._layout import header
from app.lib.betlog import read_log
header('Strategy Compare (Realized Results)')
df = read_log()
if df.empty:
    st.warning('No bets in log.')
    st.stop()
df.columns = [c.strip().lower() for c in df.columns]
d = df[~df.get('result', '').astype(str).str.lower().isin(['', 'open'])].copy()
if 'ts' in d.columns:
    d['ts'] = pd.to_datetime(d['ts'], errors='coerce', utc=True)
    d = d.sort_values('ts')
start_bankroll = st.number_input('Starting bankroll ($)', value=1000.0, min_value=0.0, step=50.0)
flat_amt = st.number_input('Flat stake ($)', value=10.0, min_value=0.0, step=1.0)
pct_bank = st.slider('% Bankroll stake', 0.5, 10.0, 2.0, 0.5) / 100.0
kelly_mult = st.slider('Fractional Kelly (x)', 0.0, 1.0, 0.5, 0.05)

def american_to_decimal(odds: int) -> float:
    return 1 + (odds / 100.0 if odds > 0 else 100.0 / abs(odds))

def replay(strategy: str):
    bank = start_bankroll
    curve = []
    for _, r in d.iterrows():
        odds = int(r.get('odds', -110))
        dec = american_to_decimal(odds)
        profit = float(pd.to_numeric(r.get('payout', 0.0), errors='coerce') or 0.0)
        if strategy == 'Flat-$':
            stake = flat_amt
        elif strategy == '% Bankroll':
            stake = bank * pct_bank
        else:
            stake0 = float(pd.to_numeric(r.get('stake', 0.0), errors='coerce') or 0.0)
            stake = bank * min(0.05, max(0.0, kelly_mult)) if stake0 == 0 else stake0
        bank += profit
        curve.append(bank)
    return curve
for s in ['Flat-$', '% Bankroll', 'Kelly-ish']:
    c = replay(s)
    st.line_chart(c, height=200)
    st.caption(f'{s}: end=${c[-1]:,.2f}')