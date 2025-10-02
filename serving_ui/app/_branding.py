from __future__ import annotations
from pathlib import Path
from PIL import Image
import streamlit as st

def setup_branding(current_file: str | None=None, app_title: str='Calculated Risk', subtitle: str | None=None):
    """
    Sets page icon, places the logo + title in the sidebar on every page.
    Call this at the very top of each page before other st.* calls.
    """
    app_dir = Path(current_file).resolve().parent if current_file else Path(__file__).resolve().parent
    root = app_dir.parent.parent
    candidates = [app_dir / 'assets' / 'logo.png', app_dir / 'assets' / 'calculated_risk_logo.png', root / 'logo.png', root / 'calculated_risk_logo.png']
    logo_path = next((p for p in candidates if p.exists()), None)
    page_icon = None
    if logo_path:
        try:
            page_icon = Image.open(logo_path)
        except Exception:
            page_icon = '📈'
    st.set_page_config(page_title=app_title, page_icon=page_icon or '📈', layout='wide', initial_sidebar_state='expanded')
    with st.sidebar:
        if logo_path:
            st.image(str(logo_path), width='stretch')
        st.markdown(f"<div style='margin-top:0.25rem;font-weight:700;font-size:1.05rem'>{app_title}</div>", unsafe_allow_html=True)
        if subtitle:
            st.markdown(f"<div style='opacity:0.7'>{subtitle}</div>", unsafe_allow_html=True)
        if hasattr(st, 'page_link'):
            st.page_link('Home.py', label='🏠 Home')