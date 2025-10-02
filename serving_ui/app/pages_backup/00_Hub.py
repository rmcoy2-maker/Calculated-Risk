from app.bootstrap import bootstrap_paths
ROOT = bootstrap_paths()
import streamlit as st
from pathlib import Path
LOGO = Path(ROOT) / 'assets' / 'logo.png'
st.set_page_config(page_title='Calculated Risk â€¢ Hub', page_icon=str(LOGO) if LOGO.exists() else 'ðŸ\x8fˆ', layout='wide')
st.markdown('\n<style>\n.main > div { padding-top: 2rem; }\n.cr-hero { display:flex; flex-direction:column; align-items:center; gap:.5rem; }\n.cr-sub { opacity:.8; font-size:.95rem; }\n.grid { display:grid; grid-template-columns: repeat(2, minmax(240px, 1fr)); gap: 12px; margin-top: 1rem; }\n.tile { padding: 14px 16px; border: 1px solid rgba(255,255,255,.1); border-radius: 10px; }\n</style>\n', unsafe_allow_html=True)
st.markdown('<div class="cr-hero">', unsafe_allow_html=True)
if LOGO.exists():
    st.image(str(LOGO), width=260)
st.markdown('<h1>Calculated Risk</h1>', unsafe_allow_html=True)
st.markdown('<div class="cr-sub">Edge Finder â€¢ Betting Analytics â€¢ Parlay Builder</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('---')
st.markdown('<div class="grid">', unsafe_allow_html=True)
with st.container(border=False):
    st.markdown('<div class="tile">', unsafe_allow_html=True)
    st.page_link('pages/09_Parlay_Builder.py', label='Parlay Builder')
    st.page_link('pages/06_Bet_Log.py', label='ðŸ“\x9d Calculated Log')
    st.page_link('pages/03_Backtest.py', label='ðŸ§ª Backtest')
    st.page_link('pages/98_Diagnostics.py', label='ðŸ›\xa0ï¸\x8f Diagnostics')
    st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
