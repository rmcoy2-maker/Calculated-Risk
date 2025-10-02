from __future__ import annotations
# === AppImportGuard (nuclear) ===
try:
    from app.lib.auth import login, show_logout
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    here = Path(__file__).resolve()

    base = None
    auth_path = None
    for p in [here] + list(here.parents):
        cand1 = p / "app" / "lib" / "auth.py"
        cand2 = p / "serving_ui" / "app" / "lib" / "auth.py"
        if cand1.exists():
            base, auth_path = p, cand1
            break
        if cand2.exists():
            base, auth_path = (p / "serving_ui"), cand2
            break

    if base and auth_path:
        s = str(base)
        if s not in sys.path:
            sys.path.insert(0, s)
        try:
            from app.lib.auth import login, show_logout  # type: ignore
        except ModuleNotFoundError:
            import types, importlib.util
            if "app" not in sys.modules:
                pkg_app = types.ModuleType("app")
                pkg_app.__path__ = [str(Path(base) / "app")]
                sys.modules["app"] = pkg_app
            if "app.lib" not in sys.modules:
                pkg_lib = types.ModuleType("app.lib")
                pkg_lib.__path__ = [str(Path(base) / "app" / "lib")]
                sys.modules["app.lib"] = pkg_lib
            spec = importlib.util.spec_from_file_location("app.lib.auth", str(auth_path))
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            assert spec and spec.loader
            spec.loader.exec_module(mod)  # type: ignore[attr-defined]
            sys.modules["app.lib.auth"] = mod
            login = mod.login
            show_logout = mod.show_logout
    else:
        raise
# === /AppImportGuard ===


import sys
from pathlib import Path
import streamlit as st
_here = Path(__file__).resolve()
for up in [_here] + list(_here.parents):
    cand = up / 'serving_ui' / 'app' / '__init__.py'
    if cand.exists():
        base = str((up / 'serving_ui').resolve())
        if base not in sys.path:
            sys.path.insert(0, base)
        break
PAGE_PROTECTED = False
auth = login(required=PAGE_PROTECTED)
if not auth.ok:
    st.stop()
show_logout()
auth = login(required=False)
if not auth.authenticated:
    st.info('You are in read-only mode.')
show_logout()
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
st.set_page_config(page_title='95 Models Browser', page_icon='📈', layout='wide')




# === Nudge+Session (auto-injected) ===
try:
    from app.utils.nudge import begin_session, touch_session, session_duration_str, bump_usage, show_nudge  # type: ignore
except Exception:
    def begin_session(): pass
    def touch_session(): pass
    def session_duration_str(): return ""
    bump_usage = lambda *a, **k: None
    def show_nudge(*a, **k): pass

# Initialize/refresh session and show live duration
begin_session()
touch_session()
if hasattr(st, "sidebar"):
    st.sidebar.caption(f"🕒 Session: {session_duration_str()}")

# Count a lightweight interaction per page load
bump_usage("page_visit")

# Optional upsell banner after threshold interactions in last 24h
show_nudge(feature="analytics", metric="page_visit", threshold=10, period="1D", demo_unlock=True, location="inline")
# === /Nudge+Session (auto-injected) ===

# === Nudge (auto-injected) ===
try:
    from app.utils.nudge import bump_usage, show_nudge  # type: ignore
except Exception:
    bump_usage = lambda *a, **k: None
    def show_nudge(*a, **k): pass

# Count a lightweight interaction per page load
bump_usage("page_visit")

# Show a nudge once usage crosses threshold in the last 24h
show_nudge(feature="analytics", metric="page_visit", threshold=10, period="1D", demo_unlock=True, location="inline")
# === /Nudge (auto-injected) ===

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






