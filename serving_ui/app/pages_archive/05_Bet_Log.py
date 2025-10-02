import pandas as pd
import streamlit as st
from pathlib import Path
from serving_ui.app._layout import header
header('Calculated Log')
st.page_link('serving_ui/app/pages/12_Settle_Results.py', label='Ã¢â€\xa0â€™ Settle Results', icon='Ã¢Å¡â€“Ã¯Â¸Â\x8f')
st.caption('Upload or view your Calculated Log. Supports CLV, EV, and summary metrics.')

def _find_log_csv() -> Path | None:
    here = Path(__file__).resolve()
    root = here.parents[2]
    candidates = [root / 'exports' / 'bets_log.csv', root / 'serving_ui' / 'exports' / 'bets_log.csv']
    for p in candidates:
        if p.exists() and p.stat().st_size > 0:
            return p
    return None
uploaded = st.file_uploader('Upload Calculated Log CSV', type=['csv'], key='betlog_up')
if uploaded:
    df = pd.read_csv(uploaded)
else:
    p = _find_log_csv()
    if p:
        df = pd.read_csv(p)
    else:
        st.warning('No Calculated Log found. Upload a CSV or create one.')
        st.stop()
df.columns = [c.strip().lower() for c in df.columns]

def american_to_decimal(odds: int) -> float:
    o = int(odds)
    return 1 + (o / 100.0 if o > 0 else 100.0 / abs(o))

def american_to_implied(odds: int) -> float:
    return 1.0 / american_to_decimal(odds)

def clv_pct(initial_odds: int, closing_odds: int) -> float:
    q0 = american_to_implied(initial_odds)
    q1 = american_to_implied(closing_odds)
    return (q1 - q0) / q0 if q0 > 0 else 0.0
if {'open_odds', 'close_odds'}.issubset(df.columns):
    df['clv_pct'] = [clv_pct(int(o), int(c)) if pd.notna(o) and pd.notna(c) else None for o, c in zip(df['open_odds'], df['close_odds'])]
if {'model_p', 'odds'}.issubset(df.columns):
    df['implied_q'] = df['odds'].map(lambda x: american_to_implied(int(x)))
    df['ev_pp'] = (df['model_p'] - df['implied_q']) * 100.0
if 'market' in df.columns:
    mkts = sorted(df['market'].dropna().unique())
    sel_mkts = st.multiselect('Markets', mkts, default=mkts)
    df = df[df['market'].isin(sel_mkts)]
if 'book' in df.columns:
    books = sorted(df['book'].dropna().unique())
    sel_books = st.multiselect('Books', books, default=books)
    df = df[df['book'].isin(sel_books)]
st.write(f'**Rows:** {len(df):,}')
st.dataframe(df, hide_index=True, width='stretch')
with st.expander('Summary'):
    if 'clv_pct' in df.columns:
        st.metric('Median CLV', f"{df['clv_pct'].median() * 100:.2f}%")
        st.metric('Mean CLV', f"{df['clv_pct'].mean() * 100:.2f}%")
    if 'ev_pp' in df.columns:
        st.metric('Median +EV (pp)', f"{df['ev_pp'].median():.2f}")
        st.metric('Mean +EV (pp)', f"{df['ev_pp'].mean():.2f}")
csv = df.to_csv(index=False).encode()
st.download_button('Download Calculated Log', data=csv, file_name='bets_log_out.csv', mime='text/csv')
