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
import os, time
from pathlib import Path
import numpy as np
import pandas as pd
try:
    from lib.io_paths import autoload_edges, clear_loader_cache, find_exports_dir, _file_mtime, LIVE_FILENAME
except Exception:
    LIVE_FILENAME = 'lines_live.csv'

    @st.cache_data(ttl=30, show_spinner=False)
    def _read_csv_safe(p: Path) -> pd.DataFrame:
        try:
            return pd.read_csv(p, low_memory=False, encoding='utf-8-sig')
        except Exception:
            return pd.DataFrame()

    def find_exports_dir() -> Path:
        for cand in [Path(os.environ.get('EDGE_EXPORTS_DIR', '')), Path('exports'), Path.cwd() / 'exports']:
            if cand and Path(cand).exists():
                return Path(cand)
        return Path.cwd()

    def _file_mtime(p: Path | str | None) -> float | None:
        if not p:
            return None
        p = Path(p)
        try:
            return p.stat().st_mtime
        except Exception:
            return None
    _CACHE = {'df': None, 'path': None, 'root': None}

    def clear_loader_cache():
        _CACHE.update({'df': None, 'path': None, 'root': None})

    def autoload_edges(with_caption: bool=True):
        root = find_exports_dir()
        env_path = os.environ.get('EDGE_SOURCE_FILE')
        candidates = []
        if env_path:
            p = Path(env_path)
            candidates.append(p if p.is_absolute() else Path.cwd() / env_path)
        candidates += [root / 'edges_graded_full.csv', root / 'edges_graded_plus.csv', root / 'edges_graded.csv', root / 'edges.csv', root / LIVE_FILENAME]
        for p in candidates:
            if p.exists() and p.stat().st_size > 0:
                df = _read_csv_safe(p)
                if not df.empty:
                    if with_caption:
                        st.caption(f'Loaded: {p} · exports root: {root} · rows={len(df):,} · cols={len(df.columns)}')
                    return (df, str(p), str(root))
        if with_caption:
            st.caption('Loaded: — · exports root: {root} · rows=0 · cols=0')
        return (pd.DataFrame(), None, str(root))
try:
    from lib.enrich import add_probs_and_ev, attach_teams
except Exception:

    def attach_teams(df: pd.DataFrame) -> pd.DataFrame:
        return df

    def add_probs_and_ev(df: pd.DataFrame) -> pd.DataFrame:
        return df
st.set_page_config(page_title='Data Diagnostics', page_icon='🧪', layout='wide')




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

st.title('Data Diagnostics')
lc1, lc2 = st.columns([1, 4])
with lc1:
    if st.button('Refresh data', type='primary'):
        clear_loader_cache()
        st.rerun()
df, df_path, root_path = autoload_edges(with_caption=True)
enriched = add_probs_and_ev(attach_teams(df.copy()))

def _first(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    low = {c.lower(): c for c in df.columns}
    for n in names:
        if n in low:
            return low[n]
    return None
ALT_ODDS = ('odds', 'american', 'price', 'price_american', 'american_odds')
ALT_PWIN = ('p_win', 'p_model', 'prob', 'model_p', 'win_prob', 'p', 'prob_win')
ALT_BOOK = ('book', 'sportsbook', 'bk')
ALT_MKT = ('market', 'bet_type', 'wager_type')
ALT_SIDE = ('side', 'selection')
ALT_GID = ('game_id', 'ref', 'gid', 'game')
odds_col = _first(enriched, ALT_ODDS)
p_col = _first(enriched, ALT_PWIN)
p_series = pd.to_numeric(enriched[p_col], errors='coerce') if p_col else pd.to_numeric(enriched.get('p_model_use', np.nan), errors='coerce')
rows_total = len(enriched)
rows_with_odds = int(pd.to_numeric(enriched.get(odds_col, np.nan), errors='coerce').notna().sum()) if odds_col else 0
rows_with_p = int(p_series.notna().sum())

def _payout_from_american(o):
    try:
        o = float(o)
    except Exception:
        return np.nan
    if o > 0:
        return o / 100.0
    if o < 0:
        return 100.0 / abs(o)
    return np.nan
if 'ev_$1' not in enriched.columns and odds_col and rows_with_p:
    enriched['ev_$1'] = p_series * enriched[odds_col].map(_payout_from_american) - (1 - p_series)
rows_pos_ev = int(pd.to_numeric(enriched.get('ev_$1', np.nan), errors='coerce').ge(0).sum())
m1, m2, m3, m4 = st.columns(4)
m1.metric('Rows', f'{rows_total:,}')
m2.metric('With odds', f'{rows_with_odds:,}')
m3.metric('With probability', f'{rows_with_p:,}')
m4.metric('EV ≥ 0', f'{rows_pos_ev:,}')
st.subheader('Exports directory & source resolution')
exp = find_exports_dir()
candidates = ['edges_graded_full.csv', 'edges_graded_plus.csv', 'edges_graded.csv', 'edges.csv', LIVE_FILENAME]
info = []
for name in candidates:
    path = exp / name
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    mtime = _file_mtime(path) if exists else None
    mt = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime)) if mtime else ''
    info.append({'file': name, 'exists': 'yes' if exists else 'no', 'size_bytes': size, 'last_write': mt, 'full_path': str(path if exists else '')})
st.dataframe(pd.DataFrame(info), height=220, width='stretch')
st.caption(f"Repo root: `{root_path or '—'}` · exports dir: `{exp}` · EDGE_SOURCE_FILE: `{os.environ.get('EDGE_SOURCE_FILE', '(not set)')}` · Loaded file: `{df_path or '—'}`")
st.subheader('Detected columns')
det = {'game_id': _first(enriched, ALT_GID), 'market': _first(enriched, ALT_MKT), 'side': _first(enriched, ALT_SIDE), 'book': _first(enriched, ALT_BOOK), 'odds': odds_col, 'p_win': p_col}
st.json(det)
st.subheader('Sample rows (raw)')
st.dataframe(df.head(50), width='stretch')
st.subheader('Sample rows (enriched: teams, p_model_use, EV, fair odds)')
show_cols = [det['game_id'] or 'game_id', 'home_team', 'away_team', det['market'] or 'market', det['side'] or 'side', det['book'] or 'book', det['odds'] or 'odds', det['p_win'] or 'p_win', 'p_model_use', 'computer_fair_odds', 'ev_$1']
exists = [c for c in show_cols if c in enriched.columns]
st.dataframe(enriched[exists].head(200), width='stretch')
with st.expander('How loading works', expanded=False):
    st.markdown('\n**Priority order** for the file loaded on every page:\n1) `$EDGE_SOURCE_FILE` if set (absolute or relative to repo root)  \n2) `edges_graded_full.csv` → `edges_graded_plus.csv` → `edges_graded.csv` → `edges.csv`  \n3) `lines_live.csv` (fallback)\n\n- If the chosen file lacks a model probability, pages derive a fallback probability from *implied odds*.\n- Use a graded file with a real `p_win` column for meaningful **EV** and **edges**.\n- Click **Refresh data** to clear cache after dropping in new exports.\n')






