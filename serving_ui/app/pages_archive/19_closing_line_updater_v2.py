import pandas as pd
import streamlit as st
from pathlib import Path
from serving_ui.app._layout import header
from app.lib.betlog import read_log, log_path
header('Closing Line Updater (CLV Automation)')
st.caption('Upload a CSV with closing odds; weÃ¢â‚¬â„¢ll match and update `close_odds` and recompute `clv_pct` in your Calculated Log.')

def american_to_decimal(odds: int) -> float:
    o = int(odds)
    return 1 + (o / 100.0 if o > 0 else 100.0 / abs(o))

def american_to_implied(odds: int) -> float:
    return 1.0 / american_to_decimal(int(odds))

def compute_clv(open_odds, close_odds):
    try:
        q0 = american_to_implied(int(open_odds))
        q1 = american_to_implied(int(close_odds))
        return (q1 - q0) / q0 if q0 > 0 else None
    except Exception:
        return None
st.subheader('1) Upload closing odds CSV')
st.caption('Accepted columns (any of): ref (best), game_id, market, side, selection, close_odds. WeÃ¢â‚¬â„¢ll match by `ref` first, then by the tuple.')
upload = st.file_uploader('Upload CSV', type=['csv'])
if not upload:
    st.stop()
try:
    closers = pd.read_csv(upload)
except Exception:
    closers = pd.read_csv(upload, encoding_errors='ignore')
orig_cols = closers.columns.tolist()
closers.columns = [c.strip().lower() for c in closers.columns]
need_any = {'ref'} | {'game_id', 'market', 'side', 'selection'}
if not ('ref' in closers.columns or {'game_id', 'market', 'side', 'selection'} <= set(closers.columns)):
    st.error('CSV must contain `ref` or the tuple (`game_id`,`market`,`side`,`selection`).')
    st.stop()
if 'close_odds' not in closers.columns:
    for guess in ['closing_odds', 'close', 'final_odds', 'closing_price']:
        if guess in closers.columns:
            closers['close_odds'] = closers[guess]
            break
if 'close_odds' not in closers.columns:
    st.error('Need a `close_odds` column.')
    st.stop()
st.write('Preview of closers:', closers.head())
st.subheader('2) Apply to Calculated Log')
log = read_log()
if log.empty:
    st.warning('No existing bets. Add to log first.')
    st.stop()
log.columns = [c.strip().lower() for c in log.columns]
for c in ['ref', 'game_id', 'market', 'side', 'selection', 'open_odds', 'close_odds']:
    if c not in log.columns:
        log[c] = None
updated = 0
log_idx_map = {str(v).strip().lower(): i for i, v in log['ref'].items() if pd.notna(v)}
tuple_idx_map = {}
if {'game_id', 'market', 'side', 'selection'} <= set(log.columns):
    for i, r in log.iterrows():
        key = (str(r.get('game_id', '')).strip().lower(), str(r.get('market', '')).strip().lower(), str(r.get('side', '')).strip().lower(), str(r.get('selection', '')).strip().lower())
        tuple_idx_map[key] = i
for _, r in closers.iterrows():
    ref = str(r.get('ref', '')).strip().lower()
    co = r.get('close_odds', None)
    idx = None
    if ref and ref in log_idx_map:
        idx = log_idx_map[ref]
    elif {'game_id', 'market', 'side', 'selection'} <= set(closers.columns):
        key = (str(r.get('game_id', '')).strip().lower(), str(r.get('market', '')).strip().lower(), str(r.get('side', '')).strip().lower(), str(r.get('selection', '')).strip().lower())
        idx = tuple_idx_map.get(key)
    if idx is not None and pd.notna(co):
        log.at[idx, 'close_odds'] = pd.to_numeric(co, errors='coerce')
        updated += 1
if {'open_odds', 'close_odds'} <= set(log.columns):
    clv_vals = []
    for o, c in zip(log['open_odds'], log['close_odds']):
        clv_vals.append(compute_clv(o, c) if pd.notna(o) and pd.notna(c) else None)
    log['clv_pct'] = clv_vals
st.info(f'Matched + updated rows: {updated:,}')
out = log_path()
log.to_csv(out, index=False)
st.success(f'Saved updates Ã¢â€\xa0â€™ `{out}`')
with st.expander('Tail of updated log'):
    st.dataframe(log.tail(30), hide_index=True, width='stretch')
