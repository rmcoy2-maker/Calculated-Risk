from pathlib import Path
import pandas as pd
import streamlit as st
from serving_ui.app._layout import header
from app.lib.betlog import read_log, log_path
header('Settle Results')
st.caption('Mark bets as win/loss/push/void and auto-compute payouts from stake + odds. Changes are saved to `exports/bets_log.csv`.')

def american_to_decimal(odds: int) -> float:
    o = int(odds)
    return 1 + (o / 100.0 if o > 0 else 100.0 / abs(o))

def auto_payout(result: str, stake: float, odds: int) -> float:
    """
    Returns net profit:
      win:  stake*(decimal-1)
      loss: -stake
      push/void: 0
    """
    if pd.isna(stake) or pd.isna(odds):
        return 0.0
    d = american_to_decimal(int(odds))
    res = (result or '').strip().lower()
    if res == 'win':
        return float(stake) * (d - 1.0)
    if res == 'loss':
        return -float(stake)
    return 0.0

def _safe_lower_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df
df = read_log()
if df.empty:
    st.warning('No bets found in `exports/bets_log.csv`. Add some via All Picks Explorer or Import Bets.')
    st.stop()
df = _safe_lower_cols(df)
for col in ['result', 'payout', 'stake', 'odds', 'ref']:
    if col not in df.columns:
        df[col] = None
left, right = st.columns([2, 1])
with left:
    only_open = st.checkbox('Show only open/unset bets', value=True)
    search_ref = st.text_input('Filter by Ref / Ticket ID (optional)', value='')
with right:
    n_show = st.number_input('Max rows to show', 10, 2000, 200)
f = df.copy()
if only_open:
    f = f[f['result'].isna() | f['result'].astype(str).str.lower().isin(['', 'open'])]
if search_ref:
    q = search_ref.strip().lower()
    if 'ref' in f.columns:
        f = f[f['ref'].astype(str).str.lower().str.contains(q, na=False)]
f = f.head(n_show)
if f.empty:
    st.info('No rows match the current filters.')
    st.stop()
st.subheader('Edit & Settle')
st.caption('Edit **result** (open/win/loss/push/void). Leave **payout** blank to auto-compute from stake and odds.')
editable_cols = []
for c in ['result', 'payout']:
    if c in f.columns:
        editable_cols.append(c)
key_cols = [c for c in ['ts', 'ref', 'game_id', 'market', 'side', 'selection', 'odds', 'stake'] if c in f.columns]
display_cols = key_cols + [c for c in editable_cols if c not in key_cols]
edit_df = f[key_cols + editable_cols].copy()
edit_df = st.data_editor(edit_df, hide_index=False, num_rows='fixed', width='stretch')
preview = edit_df.copy()
if 'result' in preview.columns:
    preview['result'] = preview['result'].astype(str).str.strip().str.lower()
if {'payout', 'result', 'stake', 'odds'}.issubset(preview.columns):
    for idx, row in preview.iterrows():
        if pd.isna(row.get('payout')) or str(row.get('payout')) == '':
            preview.at[idx, 'payout'] = auto_payout(result=row.get('result', ''), stake=pd.to_numeric(row.get('stake'), errors='coerce'), odds=pd.to_numeric(row.get('odds'), errors='coerce'))
with st.expander('Preview computed payouts (before save)'):
    st.dataframe(preview, hide_index=False, width='stretch')
if st.button('Ã°Å¸â€™Â¾ Save changes to bets_log.csv'):
    for idx, row in preview.iterrows():
        orig_idx = f.index[idx]
        if 'result' in preview.columns:
            df.at[orig_idx, 'result'] = row.get('result', '')
        if 'payout' in preview.columns:
            df.at[orig_idx, 'payout'] = pd.to_numeric(row.get('payout'), errors='coerce')
    out = log_path()
    df.to_csv(out, index=False)
    st.success(f'Saved {len(preview):,} updates Ã¢â€\xa0â€™ `{out}`')
    st.toast('Bets updated', icon='Ã¢Å“â€¦')