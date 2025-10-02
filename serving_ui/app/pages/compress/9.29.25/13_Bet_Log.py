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
st.set_page_config(page_title='13 Calculated Log', page_icon='📈', layout='wide')




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
st.markdown('\n<style>\n  .block-container {max-width: 1600px; padding-top: 0.5rem; padding-left: 1.0rem; padding-right: 1.0rem;}\n</style>\n', unsafe_allow_html=True)
from app.bootstrap import bootstrap_paths
bootstrap_paths()
from pathlib import Path
import pandas as pd
BETS_CSV = Path('exports/bets_log.csv')
PARLAYS_CSV = Path('exports/parlays.csv')

def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        if getattr(path, 'stat', None) and path.stat().st_size == 0:
            return pd.DataFrame()
    except Exception:
        pass
    try:
        return pd.read_csv(path, encoding='utf-8-sig')
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    except pd.errors.ParserError:
        try:
            return pd.read_csv(path, engine='python')
        except Exception:
            return pd.DataFrame()
    except Exception:
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()

def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    out['sort_ts'] = pd.to_datetime(out.get('ts'), errors='coerce')
    for c in ('stake', 'profit', 'result'):
        if c not in out.columns:
            out[c] = 0 if c != 'result' else ''
    return out

def build_betlog() -> pd.DataFrame:
    bets = _normalize(_read_csv(BETS_CSV))
    parlays = _normalize(_read_csv(PARLAYS_CSV))
    if bets.empty and parlays.empty:
        cols = ['ts', 'stake', 'profit', 'result', 'sort_ts', 'origin']
        return pd.DataFrame(columns=cols)
    if not bets.empty:
        bets['origin'] = 'bet'
    if not parlays.empty:
        parlays['origin'] = 'parlay'
    cols = sorted(set(bets.columns) | set(parlays.columns))
    combined = pd.concat([bets.reindex(columns=cols), parlays.reindex(columns=cols)], ignore_index=True)
    return combined.sort_values('sort_ts').reset_index(drop=True)

def summarize(bets: pd.DataFrame) -> dict:
    if bets.empty:
        return dict(bets=0, wins=0, losses=0, pushes=0, roi=None)
    res = bets['result'].astype(str).str.lower()
    wins = (res == 'win').sum()
    losses = (res == 'loss').sum()
    pushes = (res == 'push').sum()
    stake_sum = pd.to_numeric(bets['stake'], errors='coerce').fillna(0).sum()
    profit_sum = pd.to_numeric(bets['profit'], errors='coerce').fillna(0).sum()
    roi = profit_sum / stake_sum if stake_sum > 0 else None
    return dict(bets=len(bets), wins=wins, losses=losses, pushes=pushes, roi=roi)

def equity_series(bets: pd.DataFrame, starting_bankroll: float=100.0) -> pd.DataFrame:
    p = pd.to_numeric(bets.get('profit', 0), errors='coerce').fillna(0)
    equity = starting_bankroll + p.cumsum()
    out = pd.DataFrame({'ts': bets['sort_ts'], 'equity': equity})
    out.set_index('ts', inplace=True)
    return out
bets_df = build_betlog()
st.subheader('Calculated Log — Summary')
S = summarize(bets_df)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric('Bets', S['bets'])
c2.metric('Wins', S['wins'])
c3.metric('Losses', S['losses'])
c4.metric('Pushes', S['pushes'])
c5.metric('ROI', '-' if S['roi'] is None else f"{S['roi'] * 100:.1f}%")
st.subheader('Bankroll equity')
start_bankroll = st.number_input('Starting bankroll (units)', 0.0, 1000000000.0, 100.0, 1.0)
if bets_df.empty:
    st.info('No bets/parlays found (empty or missing CSVs).')
else:
    st.line_chart(equity_series(bets_df, starting_bankroll=start_bankroll), y='equity')
st.subheader('Rows')
st.dataframe(bets_df, hide_index=True, width='stretch')







