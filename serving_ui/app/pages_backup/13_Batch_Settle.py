from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st
ROOT = Path(__file__).resolve().parents[2]
EXPORTS = ROOT / 'exports'
LOG = EXPORTS / 'bets_log.csv'
st.set_page_config(page_title='Batch Settle', layout='wide')
st.title('ðŸ§¾ Batch Settle Â· Open Bets')
BET_COLS = ['ts', 'market', 'ref', 'side', 'line', 'odds', 'p_win', 'ev', 'stake', 'status', 'result', 'pnl', 'tag', 'legs_json', 'bet_id']

def load_log() -> pd.DataFrame:
    if not LOG.exists() or LOG.stat().st_size <= 5:
        st.warning('bets_log.csv not found or empty. Create a few bets first.')
        return pd.DataFrame(columns=BET_COLS)
    df = pd.read_csv(LOG, dtype={'bet_id': str})
    for c in BET_COLS:
        if c not in df.columns:
            df[c] = None
    return df

def to_win_amount(stake: float, am_odds: int) -> float:
    try:
        am = int(am_odds)
    except Exception:
        return 0.0
    return stake * (am / 100.0) if am > 0 else stake * (100.0 / abs(am))

def settle_row(row: pd.Series, outcome: str) -> pd.Series:
    outcome = outcome.lower()
    row['status'] = 'closed'
    if outcome == 'win':
        row['result'] = 'win'
        row['pnl'] = round(to_win_amount(float(row['stake']), int(row['odds'])), 2)
    elif outcome == 'loss':
        row['result'] = 'loss'
        row['pnl'] = round(-float(row['stake']), 2)
    elif outcome in ('push', 'void'):
        row['result'] = 'push'
        row['pnl'] = 0.0
    else:
        st.warning(f'Unknown outcome: {outcome}')
    return row
df = load_log()
open_df = df[df['status'].fillna('open').str.lower().eq('open')].copy()
c1, c2, c3 = st.columns(3)
c1.metric('Open bets', f'{len(open_df):,}')
c2.metric('Singles', f"{(open_df['market'].astype(str).str.lower() != 'parlay').sum():,}")
c3.metric('Parlays', f"{(open_df['market'].astype(str).str.lower() == 'parlay').sum():,}")
st.divider()
if open_df.empty:
    st.info('No open bets to settle.')
    st.stop()
colf1, colf2, colf3 = st.columns([1.2, 1.2, 1.2])
with colf1:
    tags = sorted([t for t in open_df['tag'].dropna().unique()])
    pick_tags = st.multiselect('Filter by tag', tags, default=tags)
with colf2:
    mkts = sorted([m for m in open_df['market'].dropna().unique()])
    pick_mkts = st.multiselect('Filter by market', mkts, default=mkts)
with colf3:
    q = st.text_input('Search (ref / side containsâ€¦)')
f = open_df.copy()
if pick_tags:
    f = f[f['tag'].isin(pick_tags)]
if pick_mkts:
    f = f[f['market'].isin(pick_mkts)]
if q:
    ql = q.lower()
    mask = False
    for c in ['ref', 'side', 'legs_json', 'bet_id', 'tag']:
        if c in f.columns:
            mask = mask | f[c].astype(str).str.lower().str.contains(ql, na=False)
    f = f[mask]
st.caption(f'{len(f):,} open bets (after filters)')
show_cols = ['bet_id', 'ts', 'market', 'ref', 'side', 'line', 'odds', 'stake', 'tag']
show_cols = [c for c in show_cols if c in f.columns]
st.dataframe(f[show_cols], hide_index=True, width='stretch')
ids = st.multiselect('Select bet_id(s) to settle', f['bet_id'].astype(str).tolist())
cA, cB, cC, cD = st.columns(4)
do_win = cA.button('âœ… Mark WIN')
do_loss = cB.button('â\x9dŒ Mark LOSS')
do_push = cC.button('âž– Mark PUSH')
do_save = cD.button('ðŸ’¾ Save changes', type='primary')
if 'stage' not in st.session_state:
    st.session_state['stage'] = df.copy()
if ids:
    st.info(f'Selected {len(ids)} bet(s).')
    if do_win or do_loss or do_push:
        outcome = 'win' if do_win else 'loss' if do_loss else 'push'
        idx_map = st.session_state['stage']['bet_id'].astype(str).isin(ids)
        count = int(idx_map.sum())
        if count:
            st.session_state['stage'].loc[idx_map] = st.session_state['stage'].loc[idx_map].apply(settle_row, outcome=outcome, axis=1)
            st.success(f'Staged {count} bet(s) as {outcome.upper()}. Review below, then Save.')
        else:
            st.warning('No matching rows found in staging copy.')
st.divider()
st.subheader('Staged changes (will be written on Save)')
changed = st.session_state['stage'].merge(df.assign(_orig=True), on=BET_COLS, how='outer', indicator=True)
diff = st.session_state['stage'][~st.session_state['stage'][['bet_id', 'status', 'result', 'pnl']].astype(str).apply(tuple, axis=1).isin(df[['bet_id', 'status', 'result', 'pnl']].astype(str).apply(tuple, axis=1))]
if diff.empty:
    st.caption('No pending changes.')
else:
    view_cols = ['bet_id', 'status', 'result', 'pnl', 'stake', 'odds', 'market', 'ref', 'tag']
    view_cols = [c for c in view_cols if c in diff.columns]
    st.dataframe(diff[view_cols], hide_index=True, width='stretch')
if do_save:
    try:
        st.session_state['stage'].to_csv(LOG, index=False, encoding='utf-8')
        st.success(f'Saved updates to {LOG}')
        st.toast('Calculated Log updated', icon='âœ…')
        st.rerun()
    except Exception as e:
        st.error(f'Failed to save: {e}')
with st.expander('How PnL is computed'):
    st.markdown('\n- **WIN**: `stake * (odds/100)` for positive odds, or `stake * (100/|odds|)` for negative odds  \n- **LOSS**: `-stake`  \n- **PUSH/VOID**: `0`  \nWe only update **status/result/pnl**; other columns remain unchanged.\n        ')
