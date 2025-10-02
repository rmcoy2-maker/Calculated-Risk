from __future__ import annotations
import sys
from pathlib import Path
APP_DIR = Path(__file__).resolve().parent
UI_DIR = APP_DIR.parent
REPO_DIR = UI_DIR.parent
PAGES_DIR = APP_DIR / 'pages'
ASSETS = REPO_DIR / 'assets'
LOGO = ASSETS / 'logo.png'
for p in (UI_DIR, REPO_DIR):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)
from app.bootstrap import bootstrap_paths
bootstrap_paths()
import streamlit as st
st.set_page_config(page_title='Calculated Risk Hub', page_icon='', layout='wide')
c1, c2 = st.columns([1, 3])
with c1:
    try:
        if LOGO.exists():
            st.image(str(LOGO), width=160)
        else:
            st.write('**Calculated Risk**')
    except Exception:
        st.write('**Calculated Risk**')
with c2:
    st.title('Calculated Risk')
    st.markdown('**Edge Finder · Betting Analytics · Parlay Builder**')
st.divider()

def page_exists(filename: str) -> bool:
    return (PAGES_DIR / filename).exists()

def link_or_note(filename: str, label: str):
    rel = f'pages/{filename}'
    if page_exists(filename):
        st.page_link(rel, label=label)
    else:
        st.caption(f': missing: {rel}')
cols = st.columns(4)
with cols[0]:
    link_or_note('09_Parlay_Builder.py', 'Parlay Builder')
with cols[1]:
    link_or_note('06_Bet_Log.py', 'Calculated Log')
with cols[2]:
    link_or_note('03_Backtest.py', 'Backtest')
with cols[3]:
    link_or_note('08_Ghost_Parlay_Calc.py', 'Ghost Parlay')
st.divider()
with st.expander('Diagnostics'):
    st.write('APP_DIR:', APP_DIR)
    st.write('UI_DIR:', UI_DIR)
    st.write('PAGES_DIR:', PAGES_DIR)
    st.write('Has logo:', LOGO.exists())
    st.write('Repo:', REPO_DIR)
