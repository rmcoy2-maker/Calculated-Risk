from pathlib import Path
import pandas as pd
import streamlit as st
from datetime import datetime
ROOT = Path(__file__).resolve().parents[2]
EXPORTS = ROOT / 'exports'
EDGES = EXPORTS / 'edges.csv'
st.set_page_config(page_title='ðŸ“Š Edge Viewer', layout='wide')
st.title('ðŸ“Š Edge Viewer')
try:
    if EDGES.exists():
        st.caption(f'Using: {EDGES} (mtime: {datetime.fromtimestamp(EDGES.stat().st_mtime)})')
    else:
        st.info(f'No edges.csv at {EDGES}. Create one from Edge Scanner or drop a file there.')
        st.stop()
except Exception as _e:
    st.caption(f'Using: (error reading mtime: {_e})')
try:
    df = pd.read_csv(EDGES)
except Exception as e:
    st.error(f'Failed to read edges.csv: {e}')
    st.stop()
if df.empty:
    st.warning('edges.csv has no rows.')
else:
    st.dataframe(df, width='stretch')
    st.download_button('â¬‡ï¸\x8f Download edges.csv', data=df.to_csv(index=False).encode('utf-8'), file_name='edges_filtered.csv', mime='text/csv')