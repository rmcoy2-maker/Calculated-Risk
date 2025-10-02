import math
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
from serving_ui.app._layout import header
from app.lib.betlog import read_log
header('Portfolio Dashboard')
st.caption('Performance based on **settled results** in `bets_log.csv`. (Tip: use the *Settle Results* page to update results/payouts.)')
df = read_log()
if df.empty:
    st.warning('No bets found yet. Add/settle bets to see portfolio analytics.')
    st.stop()
df.columns = [c.strip().lower() for c in df.columns]
for c in ['stake', 'payout']:
    if c not in df.columns:
        df[c] = np.nan
if 'ts' in df.columns:
    try:
        df['ts'] = pd.to_datetime(df['ts'], errors='coerce', utc=True)
    except Exception:
        df['ts'] = pd.to_datetime(df['ts'], errors='coerce')
else:
    df['ts'] = pd.NaT
df['profit'] = pd.to_numeric(df['payout'], errors='coerce').fillna(0.0)
settled_mask = ~df.get('result', '').astype(str).str.lower().isin(['', 'open'])
df_set = df[settled_mask].copy()
if df_set.empty:
    st.info('No settled bets yet. Settle some results to see realized performance.')
    st.stop()
left, right = st.columns([2, 1])
with left:
    granularity = st.radio('Time Granularity', ['Monthly', 'Weekly', 'Daily'], index=0, horizontal=True)
with right:
    filt_cols = []
    if 'sport' in df_set.columns:
        filt_cols.append('sport')
    if 'league' in df_set.columns:
        filt_cols.append('league')
    if 'market' in df_set.columns:
        filt_cols.append('market')
    if 'book' in df_set.columns:
        filt_cols.append('book')
filters = {}
if filt_cols:
    with st.expander('Filters'):
        for c in filt_cols:
            vals = sorted((v for v in df_set[c].dropna().unique().tolist()))
            pick = st.multiselect(c.capitalize(), vals, default=vals)
            filters[c] = pick
f = df_set
for c, vals in filters.items():
    if vals:
        f = f[f[c].isin(vals)]
st.write(f'**Rows (settled after filters):** {len(f):,}')

def add_period(g: str) -> pd.Series:
    if g == 'Monthly':
        return f['ts'].dt.to_period('M').dt.to_timestamp()
    if g == 'Weekly':
        return f['ts'].dt.to_period('W-MON').dt.start_time
    return f['ts'].dt.floor('D')

def _safe_sum(x):
    return pd.to_numeric(x, errors='coerce').fillna(0.0).sum()
st.subheader('Bankroll Curve (Realized)')
start_bankroll = st.number_input('Starting bankroll ($)', value=1000.0, min_value=0.0, step=50.0, key='pb_start_bk')
f_sorted = f.sort_values('ts').copy()
f_sorted['cum_profit'] = _safe_sum([])
f_sorted['profit'] = pd.to_numeric(f_sorted['profit'], errors='coerce').fillna(0.0)
f_sorted['cum_profit'] = f_sorted['profit'].cumsum()
f_sorted['bankroll'] = start_bankroll + f_sorted['cum_profit']
st.line_chart(f_sorted.set_index('ts')['bankroll'], height=240)
with st.expander('Bankroll curve data (tail)'):
    st.dataframe(f_sorted[['ts', 'profit', 'cum_profit', 'bankroll']].tail(25), hide_index=True, width='stretch')

def roi_tbl(by_col: str) -> pd.DataFrame:
    if by_col not in f.columns:
        return pd.DataFrame()
    grp = f.groupby(by_col, dropna=True).agg(bets=('stake', 'count'), stake=('stake', _safe_sum), profit=('profit', _safe_sum), wins=('result', lambda s: (s.astype(str).str.lower() == 'win').sum()), losses=('result', lambda s: (s.astype(str).str.lower() == 'loss').sum()), pushes=('result', lambda s: s.astype(str).str.lower().isin(['push', 'void']).sum())).reset_index()
    grp['roi_%'] = np.where(grp['stake'] > 0, grp['profit'] / grp['stake'] * 100.0, np.nan)
    grp = grp.sort_values(['roi_%', 'profit'], ascending=[False, False])
    return grp
st.subheader('Breakdowns')
cols = [c for c in ['sport', 'league', 'market', 'book'] if c in f.columns]
if not cols:
    st.info('No categorical columns to break down (sport/league/market/book).')
else:
    for c in cols:
        st.markdown(f'**By {c.capitalize()}**')
        t = roi_tbl(c)
        if not t.empty:
            st.dataframe(t, hide_index=True, width='stretch')
            st.download_button(f'Download by_{c}.csv', data=t.to_csv(index=False).encode(), file_name=f'by_{c}.csv', mime='text/csv')
        else:
            st.caption(f'No data for {c}.')
st.subheader(f'{granularity} Performance')
f_time = f.copy()
f_time['period'] = add_period(granularity)
ts_tbl = f_time.groupby('period').agg(bets=('stake', 'count'), stake=('stake', _safe_sum), profit=('profit', _safe_sum)).reset_index().sort_values('period')
ts_tbl['roi_%'] = np.where(ts_tbl['stake'] > 0, ts_tbl['profit'] / ts_tbl['stake'] * 100.0, np.nan)
c1, c2 = st.columns([2, 1])
with c1:
    st.dataframe(ts_tbl, hide_index=True, width='stretch')
with c2:
    st.bar_chart(ts_tbl.set_index('period')['profit'], height=220)
st.download_button(f'Download {granularity.lower()}_performance.csv', data=ts_tbl.to_csv(index=False).encode(), file_name=f'{granularity.lower()}_performance.csv', mime='text/csv')
have_clv = 'clv_pct' in f.columns
have_ev = 'ev_pp' in f.columns or ('model_p' in f.columns and 'odds' in f.columns)
with st.expander('CLV / EV Diagnostics'):
    if have_clv:
        st.subheader('CLV% distribution')
        clv = pd.to_numeric(f['clv_pct'], errors='coerce').dropna() * 100.0
        if not clv.empty:
            hist = pd.cut(clv, bins=[-50, -25, -10, -5, 0, 5, 10, 25, 50], right=False).value_counts().sort_index()
            st.bar_chart(hist)
            st.metric('Median CLV%', f'{clv.median():.2f}%')
            st.metric('Mean CLV%', f'{clv.mean():.2f}%')
        else:
            st.caption('No CLV data yet.')
    else:
        st.caption('No CLV column found (set in Calculated Log or compute at ingestion).')
    if have_ev:
        st.subheader('+EV (pp) distribution')
        if 'ev_pp' not in f.columns and {'model_p', 'odds'}.issubset(f.columns):

            def american_to_implied(odds: int) -> float:
                o = int(odds)
                dec = 1 + (o / 100.0 if o > 0 else 100.0 / abs(o))
                return 1.0 / dec
            f['ev_pp'] = (pd.to_numeric(f['model_p'], errors='coerce') - f['odds'].astype(int).map(american_to_implied)) * 100.0
        ev = pd.to_numeric(f['ev_pp'], errors='coerce').dropna()
        if not ev.empty:
            hist = pd.cut(ev, bins=[-10, -5, -2, 0, 2, 5, 10, 20], right=False).value_counts().sort_index()
            st.bar_chart(hist)
            st.metric('Median +EV (pp)', f'{ev.median():.2f}')
            st.metric('Mean +EV (pp)', f'{ev.mean():.2f}')
        else:
            st.caption('No EV data yet.')
