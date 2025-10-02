import io, zipfile
import pandas as pd
import streamlit as st
from pathlib import Path
from serving_ui.app._layout import header
from app.lib.betlog import read_log
header('Reports & Exports')
df = read_log()
if df.empty:
    st.warning('No bets in log.')
    st.stop()
df.columns = [c.strip().lower() for c in df.columns]
settled = df[~df.get('result', '').astype(str).str.lower().isin(['', 'open'])].copy()

def _num(x):
    return pd.to_numeric(x, errors='coerce').fillna(0.0)
by_sport = settled.groupby('sport', dropna=True).agg(bets=('stake', 'count'), stake=('stake', _num), profit=('payout', _num)).reset_index()
by_sport['roi_%'] = by_sport['profit'] / by_sport['stake'] * 100.0
by_book = settled.groupby('book', dropna=True).agg(bets=('stake', 'count'), stake=('stake', _num), profit=('payout', _num)).reset_index()
by_book['roi_%'] = by_book['profit'] / by_book['stake'] * 100.0
st.subheader('Preview')
st.dataframe(by_sport, hide_index=True, width='stretch')
st.dataframe(by_book, hide_index=True, width='stretch')
if not by_modelver.empty:
    st.dataframe(by_modelver, hide_index=True, width='stretch')
mem = io.BytesIO()
with zipfile.ZipFile(mem, mode='w', compression=zipfile.ZIP_DEFLATED) as z:
    z.writestr('by_sport.csv', by_sport.to_csv(index=False))
    z.writestr('by_book.csv', by_book.to_csv(index=False))
    z.writestr('by_modelver.csv', by_modelver.to_csv(index=False))
    z.writestr('bets_log_full.csv', settled.to_csv(index=False))
mem.seek(0)
st.download_button('Download report bundle (zip)', data=mem.read(), file_name='portfolio_reports.zip', mime='application/zip')