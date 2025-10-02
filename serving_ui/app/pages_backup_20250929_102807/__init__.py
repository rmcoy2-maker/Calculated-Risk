from __future__ import annotations
import streamlit as st
from app.lib.auth import login, show_logout
# === Auth (auto-injected) ===
import streamlit as st  # ensured
from app.lib.auth import login, show_logout

auth = login(required=False)   # or required=True for protected pages
if not auth.authenticated:
    st.info("You are in read-only mode.")
show_logout()  # sidebar logout
# === /Auth (auto-injected) ===
from __future__ import annotations
import streamlit as st
# --- import bootstrap so 'app' package is importable when run from anywhere ---
import sys
from pathlib import Path
_HERE = Path(__file__).resolve()
# file: .../serving_ui/app/pages/<page>.py  -> parents[2] = .../serving_ui
_SERVING_UI = _HERE.parents[2]
if str(_SERVING_UI) not in sys.path:
    sys.path.insert(0, str(_SERVING_UI))
# -----------------------------------------------------------------------------import streamlit as st
st.set_page_config(page_title='  init  ', page_icon='📈', layout='wide')

import streamlit as st

import streamlit as st


import streamlit as st

import streamlit as st

import streamlit as st
# --- diagnostics import (robust) ---
try:
    from app.utils.diagnostics import mount_in_sidebar
except ModuleNotFoundError:
    try:
        import sys
        from pathlib import Path as _efP
        # add repo/serving_ui to sys.path so 'app' is importable
        sys.path.append(str(_efP(__file__).resolve().parents[3]))
        from app.utils.diagnostics import mount_in_sidebar
    except Exception:
        try:
            # fallback if pages run with CWD=app
            from utils.diagnostics import mount_in_sidebar
        except Exception:
            def mount_in_sidebar(page_name: str):
                return None
# --- /diagnostics import (robust) ---
try:
except Exception:
    pass
st.markdown("""
<style>
  .block-container { max-width: none !important; padding-left: 1rem; padding-right: 1rem; }
  [data-testid="stHeader"] { z-index: 9990; }
</style>
""", unsafe_allow_html=True)
st.markdown("""
<style>
  .block-container {max-width: 1600px; padding-top: 0.5rem; padding-left: 1.0rem; padding-right: 1.0rem;}
</style>
""", unsafe_allow_html=True)
# --- auto-added: newest-first patch ---
try:
    # Preferred absolute import (when 'app' is a proper package)
    from app.utils.newest_first_patch import apply_newest_first_patch as __nfp_apply
except Exception:
    try:
        # Fallback if pages are executed such that relative path works
        from utils.newest_first_patch import apply_newest_first_patch as __nfp_apply
    except Exception:
        # Final no-op guard
        def __nfp_apply(_): 
            return
import streamlit as st  # ensure alias available
__nfp_apply(st)
# --- end auto-added ---
from app.bootstrap import bootstrap_paths
bootstrap_paths()
















