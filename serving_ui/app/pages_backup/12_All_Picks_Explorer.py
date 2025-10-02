from app.bootstrap import bootstrap_paths
bootstrap_paths()
import sys
from pathlib import Path
HERE = Path(__file__).resolve()
APP = HERE.parents[1]
SU = HERE.parents[2]
REPO = HERE.parents[3]
for p in {str(REPO), str(SU)}:
    if p not in sys.path:
        sys.path.insert(0, p)
try:
    from app.utils.logger import log_error
except Exception:

    def log_error(e, context=None):
        print(f"[All Picks Explorer] {context or ''}: {e}")
import streamlit as st
import pandas as pd
st.set_page_config(page_title='All Picks Explorer', layout='wide')
st.title('ðŸ”Ž All Picks Explorer')
EXPORTS_CANDIDATES = [REPO / 'exports', SU / 'exports', APP / 'exports']
EXPORTS = next((d for d in EXPORTS_CANDIDATES if d.exists()), REPO / 'exports')
PICKS = EXPORTS / 'edges.csv'
try:
    if PICKS.exists():
        df = pd.read_csv(PICKS)
        q = st.text_input('Filter (substring match across columns):')
        if q:
            mask = df.astype(str).apply(lambda s: s.str.contains(q, case=False, na=False)).any(axis=1)
            st.dataframe(df[mask], width='stretch')
        else:
            st.dataframe(df, width='stretch')
    else:
        st.info(f'No edges.csv found. Looked in: {[str(p) for p in EXPORTS_CANDIDATES]}')
except Exception as e:
    log_error(e, context=__file__)
    st.error(f'Page error: {e}')
with st.expander('âš™ï¸\x8f Diagnostics', expanded=False):
    st.write('PICKS path:', str(PICKS))
    st.write('Exists?', PICKS.exists())
    if PICKS.exists():
        st.write('Size (bytes):', PICKS.stat().st_size)
        try:
            st.dataframe(pd.read_csv(PICKS, nrows=8), width='stretch')
        except Exception as e:
            st.error(f'Preview read error: {e}')