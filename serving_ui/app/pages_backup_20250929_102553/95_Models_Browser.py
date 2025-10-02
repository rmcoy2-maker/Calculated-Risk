from __future__ import annotations
import streamlit as st
from app.lib.auth import login, show_logout
import streamlit as st
from app.lib.auth import login, show_logout
auth = login(required=False)
if not auth.authenticated:
    st.info('You are in read-only mode.')
show_logout()
from __future__ import annotations
import streamlit as st
import sys
from pathlib import Path
_HERE = Path(__file__).resolve()
_SERVING_UI = _HERE.parents[2]
if str(_SERVING_UI) not in sys.path:
    sys.path.insert(0, str(_SERVING_UI))
from app.lib.access import live_enabled
if live_enabled():
    do_expensive_refresh()
else:
    pass
import streamlit as st
st.set_page_config(page_title='95 Models Browser', page_icon='📈', layout='wide')
import streamlit as st
import streamlit as st
import streamlit as st
import streamlit as st
try:
    from app.utils.diagnostics import mount_in_sidebar
except ModuleNotFoundError:
    try:
        import sys
        from pathlib import Path as _efP
        sys.path.append(str(_efP(__file__).resolve().parents[3]))
        from app.utils.diagnostics import mount_in_sidebar
    except Exception:
        try:
            from utils.diagnostics import mount_in_sidebar
        except Exception:

            def mount_in_sidebar(page_name: str):
                return None
try:
    pass
except Exception:
    pass
st.markdown('\n<style>\n  .block-container { max-width: none !important; padding-left: 1rem; padding-right: 1rem; }\n  [data-testid="stHeader"] { z-index: 9990; }\n</style>\n', unsafe_allow_html=True)
try:
    from app.utils.newest_first_patch import apply_newest_first_patch as __nfp_apply
except Exception:
    try:
        from utils.newest_first_patch import apply_newest_first_patch as __nfp_apply
    except Exception:

        def __nfp_apply(_):
            return
import streamlit as st
__nfp_apply(st)
from pathlib import Path
import sys
HERE = Path(__file__).resolve()
APP_DIR = HERE.parents[1]
PKG_PARENT = APP_DIR.parent
REPO = PKG_PARENT.parent
for p in (str(PKG_PARENT), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)
try:
    from app.bootstrap import bootstrap_paths
    bootstrap_paths()
except Exception:
    pass
import streamlit as st
from pathlib import Path as _P_OVERRIDE
REPO = _P_OVERRIDE('C:\\Projects\\edge-finder')
import pandas as pd
try:
    from app.lib.registry import current_model_version
except Exception:

    def current_model_version(default: str='0.0.0-dev') -> str:
        marker = REPO / 'exports' / 'models' / 'ACTIVE.txt'
        if marker.exists():
            try:
                return marker.read_text(encoding='utf-8').strip() or default
            except Exception:
                return default
        return default
try:
    from app.lib.models import find_models, set_active_model
except Exception:

    def _scan_model_dirs():
        bases = [REPO / 'models', REPO / 'exports' / 'models', REPO / 'artifacts' / 'models']
        for base in bases:
            if base.exists():
                yield base

    def find_models():
        out = []
        for base in _scan_model_dirs():
            for p in base.glob('*'):
                if p.is_dir():
                    name = p.name
                    version = name
                    updated = pd.to_datetime(p.stat().st_mtime, unit='s').isoformat()
                    notes = ''
                    for meta_name in ('model.json', 'metadata.json', 'meta.json'):
                        m = p / meta_name
                        if m.exists():
                            try:
                                js = pd.read_json(m)
                                name = str(js.get('name', name))
                                version = str(js.get('version', version))
                                notes = str(js.get('notes', notes))
                                break
                            except Exception:
                                pass
                    out.append({'name': name, 'version': version, 'updated': updated, 'notes': notes, 'path': str(p)})
        return sorted(out, key=lambda d: (d['name'].lower(), d['updated']), reverse=False)

    def set_active_model(version: str):
        marker = REPO / 'exports' / 'models'
        marker.mkdir(parents=True, exist_ok=True)
        (marker / 'ACTIVE.txt').write_text(version, encoding='utf-8')
st.title('🧠 Models Browser')
cur = current_model_version()
st.caption(f'Current model version: **{cur}**')
models = find_models()
if not models:
    st.warning('No models found. Add models under `models/`, `exports/models/`, or `artifacts/models/`.\nOptional metadata: `model.json`, `metadata.json`, or `meta.json` with `name`, `version`, `updated`, `notes`.')
    st.stop()
df = pd.DataFrame(models, columns=['name', 'version', 'updated', 'notes', 'path'])
st.dataframe(df, hide_index=True, width='stretch')
st.subheader('Activate')
col1, col2 = st.columns([2, 1])
with col1:
    choices = [f"{m['name']}  —  {m['version']}" for m in models]
    try:
        default_idx = next((i for i, m in enumerate(models) if m['version'] == cur))
    except StopIteration:
        default_idx = 0
    picked = st.selectbox('Select a model to activate', choices, index=default_idx)
with col2:
    if st.button('Set Active', type='primary'):
        sel_idx = choices.index(picked)
        ver = models[sel_idx]['version']
        set_active_model(ver)
        st.success(f'Set active model to: {ver}')
with st.expander('🔎 Inspect selected model files'):
    sel_idx = choices.index(picked)
    p = Path(models[sel_idx]['path'])
    files = [f for f in p.rglob('*') if f.is_file()]
    if not files:
        st.info('No files under this model fnewer.')
    else:
        table = pd.DataFrame({'relpath': [str(f.relative_to(p)) for f in files], 'size_kb': [round(f.stat().st_size / 1024, 2) for f in files]}).sort_values('relpath')
        st.dataframe(table, hide_index=True, width='stretch')