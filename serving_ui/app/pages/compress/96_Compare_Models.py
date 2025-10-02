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


import streamlit as st
auth = login(required=False)
if not auth.authenticated:
    st.info('You are in read-only mode.')
show_logout()
import re
from pathlib import Path
import numpy as np
import pandas as pd
try:
    from lib.io_paths import find_exports_dir
except Exception:

    def find_exports_dir() -> Path:
        for cand in [Path('exports'), Path.cwd() / 'exports', Path.stem and Path(__file__).parent.parent.parent / 'exports']:
            try:
                if cand and Path(cand).exists():
                    return Path(cand)
            except Exception:
                pass
        return Path.cwd()
try:
    from lib.enrich import add_probs_and_ev, attach_teams
except Exception:

    def attach_teams(df: pd.DataFrame) -> pd.DataFrame:
        return df

    def add_probs_and_ev(df: pd.DataFrame) -> pd.DataFrame:
        return df
st.set_page_config(page_title='Compare Models', page_icon='🧠', layout='wide')




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

st.title('Compare Models')
exp = find_exports_dir()
cands: list[Path] = []

def add_if_exists(p: Path):
    try:
        if p.exists() and p.stat().st_size > 0 and (p.suffix.lower() == '.csv'):
            cands.append(p)
    except Exception:
        pass
for name in ['edges_graded_full.csv', 'edges_graded_plus.csv', 'edges_graded.csv', 'edges.csv']:
    add_if_exists(exp / name)
for p in exp.glob('edges_graded*_*.csv'):
    add_if_exists(p)
models_dir = exp / 'models'
if models_dir.exists():
    for p in models_dir.rglob('*.csv'):
        add_if_exists(p)
if not cands:
    st.warning('No graded CSVs found in exports/. Drop per-model graded CSVs into exports/ or exports/models/<name>/.')
    st.stop()
labels = [f'{p.name} — {p.parent}' for p in cands]
sel = st.multiselect('Select 2–6 graded files to compare (one per model)', options=list(range(len(cands))), format_func=lambda i: labels[i], default=list(range(min(2, len(cands)))))
if not sel:
    st.info('Pick at least one file to compare.')
    st.stop()

@st.cache_data(ttl=60, show_spinner=False)
def load_and_enrich(path_str: str) -> pd.DataFrame:
    p = Path(path_str)
    df = pd.read_csv(p, low_memory=False, encoding='utf-8-sig')
    df = add_probs_and_ev(attach_teams(df))
    m = re.search('__(.+?)\\.csv$', p.name)
    model = m.group(1) if m else p.parent.name if p.parent.name not in ('exports', 'models') else p.stem
    df['__source'] = p.name
    df['__model'] = model
    return df
dfs = [load_and_enrich(str(cands[i])) for i in sel if cands[i].exists() and cands[i].stat().st_size > 0]
dfs = [d for d in dfs if not d.empty]
if not dfs:
    st.warning('Selected files are empty after load.')
    st.stop()

def ev_metrics(df: pd.DataFrame) -> dict:
    p = pd.to_numeric(df.get('p_model_use', np.nan), errors='coerce')
    ev = pd.to_numeric(df.get('ev_$1', np.nan), errors='coerce')
    return {'rows': len(df), 'with_p': int(p.notna().sum()), 'avg_p': float(np.nanmean(p)) if p.notna().any() else np.nan, 'with_ev': int(ev.notna().sum()), 'avg_ev_$1': float(np.nanmean(ev)) if ev.notna().any() else np.nan, 'pos_ev_rows': int((ev >= 0).sum())}
rows = []
for d in dfs:
    m = d['__model'].iloc[0]
    src = d['__source'].iloc[0]
    met = ev_metrics(d)
    met['model'] = m
    met['source'] = src
    rows.append(met)
tbl = pd.DataFrame(rows)[['model', 'source', 'rows', 'with_p', 'avg_p', 'with_ev', 'avg_ev_$1', 'pos_ev_rows']]
st.subheader('EV-based comparison')
st.dataframe(tbl, width='stretch')
st.subheader('Top 25 edges per model')
for d in dfs:
    m = d['__model'].iloc[0]
    st.markdown(f"**{m}** — {d['__source'].iloc[0]}")
    show_cols = [c for c in ['game_id', 'home_team', 'away_team', 'market', 'selection', 'book', 'odds', 'p_model_use', 'computer_fair_odds', 'ev_$1'] if c in d.columns]
    st.dataframe(d.sort_values('ev_$1', ascending=False)[show_cols].head(25), width='stretch')
with st.expander('Tips', expanded=False):
    st.markdown('\n- Compare **graded** CSVs (with model probabilities). To create per-model files, export one CSV per model (e.g., `edges_graded_plus__game_lr_v3.csv`).\n- Place them in `exports/` or `exports/models/<model_name>/`.\n- This page compares **expected value** across files. For realized ROI, run Backtest on each file.\n')






