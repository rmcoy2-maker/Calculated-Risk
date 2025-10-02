import os, sys, platform
from pathlib import Path
import pandas as pd
import streamlit as st
from serving_ui.app._layout import header
header('Diagnostics')
ROOT = Path(__file__).resolve().parents[2]
st.write('**Project root:**', f'`{ROOT}`')
CHECKS = {'exports/edges.csv': ROOT / 'exports' / 'edges.csv', 'data_scaffnew/exports/edges.csv': ROOT / 'data_scaffnew' / 'exports' / 'edges.csv', 'exports/bets_log.csv': ROOT / 'exports' / 'bets_log.csv'}
rows = []
for name, p in CHECKS.items():
    rows.append({'path': name, 'exists': p.exists(), 'size_bytes': p.stat().st_size if p.exists() else 0, 'modified': pd.to_datetime(p.stat().st_mtime, unit='s') if p.exists() else None})
st.subheader('Key files')
st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
with st.expander('Preview: edges.csv (first 10)'):
    edges = None
    for p in [CHECKS['exports/edges.csv'], CHECKS['data_scaffnew/exports/edges.csv']]:
        if p.exists() and p.stat().st_size > 0:
            try:
                edges = pd.read_csv(p)
                break
            except Exception as e:
                st.warning(f'Could not read {p}: {e}')
    if edges is not None and (not edges.empty):
        st.write(f'Rows: {len(edges):,}  |  Columns: {list(edges.columns)}')
        st.dataframe(edges.head(10), hide_index=True, width='stretch')
    else:
        st.info('No edges file found or file is empty.')
with st.expander('Preview: bets_log.csv (first 10)'):
    bets = None
    p = CHECKS['exports/bets_log.csv']
    if p.exists() and p.stat().st_size > 0:
        try:
            bets = pd.read_csv(p)
        except Exception as e:
            st.warning(f'Could not read {p}: {e}')
    if bets is not None and (not bets.empty):
        st.write(f'Rows: {len(bets):,}  |  Columns: {list(bets.columns)}')
        st.dataframe(bets.head(10), hide_index=True, width='stretch')
    else:
        st.info('No Calculated Log found or file is empty.')
with st.expander('Data hygiene checks'):
    problems = []

    def _num(s):
        return pd.to_numeric(s, errors='coerce')
    if edges is not None and (not edges.empty):
        cols = [c.strip().lower() for c in edges.columns]
        e = edges.copy()
        e.columns = cols
        if 'odds' in e.columns:
            bad_odds = e[_num(e['odds']).abs() > 10000]
            if not bad_odds.empty:
                problems.append(f'Edges: {len(bad_odds)} rows with absurd odds (>|10000|).')
        if 'model_p' in e.columns:
            bad_p = e[(e['model_p'] < 0) | (e['model_p'] > 1)]
            if not bad_p.empty:
                problems.append(f'Edges: {len(bad_p)} rows with model_p outside [0,1].')
        required = {'odds', 'market'}
        missing = [c for c in required if c not in e.columns]
        if missing:
            problems.append(f'Edges: missing expected columns: {missing}')
    if bets is not None and (not bets.empty):
        b = bets.copy()
        b.columns = [c.strip().lower() for c in b.columns]
        if 'stake' in b.columns:
            bad_stake = b[_num(b['stake']) < 0]
            if not bad_stake.empty:
                problems.append(f'Calculated Log: {len(bad_stake)} rows with negative stake.')
        if 'payout' in b.columns:
            bad_pay = b[_num(b['payout']).abs() > 1000000.0]
            if not bad_pay.empty:
                problems.append(f'Calculated Log: {len(bad_pay)} rows with extreme payout (>|$1M|).')
        if 'result' in b.columns:
            allowed = {'open', 'win', 'loss', 'push', 'void', ''}
            bad_res = b[~b['result'].astype(str).str.lower().isin(allowed)]
            if not bad_res.empty:
                problems.append(f'Calculated Log: {len(bad_res)} rows with unknown result labels.')
    if problems:
        for msg in problems:
            st.error(msg)
    else:
        st.success('No obvious data issues found.')
st.subheader('Environment')
st.code('Python: ' + sys.version.splitlines()[0] + '\n' + f'Platform: {platform.platform()}\n' + f'CWD: {os.getcwd()}\n' + 'sys.path (first 10):\n' + '\n'.join(sys.path[:10]))
with st.expander('Env variables (filtered)'):
    safe_keys = ['PATH', 'PYTHONPATH']
    env = {k: v for k, v in os.environ.items() if k in safe_keys}
    st.json(env)
with st.expander('Quick tips'):
    st.markdown('- If **edges.csv** is missing, run your edge scanner (e.g., `scan_edges.py`).\n- If **bets_log.csv** is missing, add a pick from **All Picks Explorer** or use **Import Bets**.\n- Odds should be within Â±10,000 and `model_p` in [0,1].\n- Use **Settle Results** to compute realized payouts; the Portfolio Dashboard uses those.')
