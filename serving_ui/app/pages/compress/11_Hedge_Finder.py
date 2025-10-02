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
import pandas as pd
import numpy as np
try:
    from lib.io_paths import autoload_edges
    df, df_path, root_path = autoload_edges(with_caption=True)
    if df is None:
        df = pd.DataFrame()
except Exception:
    df = pd.DataFrame()
key = ['Season', 'Week', 'market', '_pick_team', 'odds', 'p_win', 'p_model', 'stake', 'parlay_id']
have = [k for k in key if k in df.columns]
try:
    from lib.io_paths import autoload_edges
    _df_loaded, _df_path, _root_path = autoload_edges(with_caption=True)
    df = _df_loaded if _df_loaded is not None else pd.DataFrame()
except Exception:
    df = pd.DataFrame()
from itertools import combinations
from lib.io_paths import autoload_edges, clear_loader_cache
from lib.enrich import add_probs_and_ev, attach_teams
key = ['game_id', 'market', 'side']
have = [k for k in key if k in df.columns]
if len(have) == 3:
    grp = df.dropna(subset=have + ['odds']).groupby(have, dropna=False)
    best_buy = grp['odds'].max().rename('odds_max')
    best_lay = grp['odds'].min().rename('odds_min')
    spread = pd.concat([best_buy, best_lay], axis=1)
    spread['window'] = spread['odds_max'].abs() + spread['odds_min'].abs()
    candidates = spread.query('odds_max > 0 and odds_min < 0')
else:
    candidates = pd.DataFrame()
df, df_path, root = autoload_edges(with_caption=True)
df = add_probs_and_ev(attach_teams(df))
st.set_page_config(page_title='Hedge Finder', page_icon='🪙', layout='wide')




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

st.subheader('Hedge Finder')
if st.button('Refresh data', type='primary', width='content'):
    clear_loader_cache()
    st.rerun()
df, df_path, root_path = autoload_edges(with_caption=True)
if df.empty:
    st.stop()
for need in ['game_id', 'market', 'side', 'book', 'odds']:
    if need not in df.columns:
        df[need] = pd.NA
df['odds'] = pd.to_numeric(df['odds'], errors='coerce')
if 'sort_ts' in df.columns:
    try:
        df['sort_ts'] = pd.to_datetime(df['sort_ts'], errors='coerce')
    except Exception:
        pass
top = st.columns([1, 1.2, 2, 1])
with top[0]:
    newest_first = st.toggle('Newest first', value=True)
with top[1]:
    mode = st.selectbox('Side match', ['Strict (OU/Home-Away)', 'Loose (any different)'], index=1)
with top[2]:
    odds_min, odds_max = st.slider('Odds window (American, abs)', 100, 300, (100, 200))
with top[3]:
    run = st.button('Find hedges', type='primary', width='stretch')
if newest_first and 'sort_ts' in df.columns and df['sort_ts'].notna().any():
    df = df.sort_values('sort_ts', ascending=False, na_position='last')
games = df['game_id'].dropna().astype(str).unique().tolist()
game = st.selectbox('Game', ['All'] + games)
subset = df if game == 'All' else df[df['game_id'].astype(str) == game]
subset = subset[subset['odds'].abs().between(odds_min, odds_max, inclusive='both')]

def is_opposite(a: str, b: str, mode: str) -> bool:
    if not a or not b:
        return False
    A, B = (str(a).strip().lower(), str(b).strip().lower())
    if mode == 'Strict (OU/Home-Away)':
        return (A, B) in {('over', 'under'), ('home', 'away'), ('away', 'home')} or (B, A) in {('over', 'under'), ('home', 'away'), ('away', 'home')}
    return A != B
if not run:
    st.info('Adjust filters and click **Find hedges**.')
    st.stop()
rows = []
for (gid, mkt), g in subset.groupby(['game_id', 'market'], dropna=False):
    g = g.reset_index(drop=True)
    for i, j in combinations(range(len(g)), 2):
        a, b = (g.loc[i], g.loc[j])
        if is_opposite(a.get('side', ''), b.get('side', ''), mode):
            rows.append({'game_id': str(gid), 'market': str(mkt), 'a_side': str(a.get('side', '')), 'a_odds': a.get('odds'), 'a_book': str(a.get('book', '')), 'b_side': str(b.get('side', '')), 'b_odds': b.get('odds'), 'b_book': str(b.get('book', ''))})
if not rows:
    st.info('No hedges found at current filters.')
else:
    out = pd.DataFrame(rows)
    st.dataframe(out, width='stretch')
    st.download_button('Download hedges.csv', data=out.to_csv(index=False).encode('utf-8'), file_name='hedges.csv', mime='text/csv')






