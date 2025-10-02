from __future__ import annotations
# === UltraImportGuard (parlay_ui & parlay_cart) ===
try:
    from app.utils.parlay_ui import selectable_odds_table
    from app.utils.parlay_cart import read_cart, add_to_cart, clear_cart
except Exception:
    import sys, types, importlib.util
    from pathlib import Path
    here = Path(__file__).resolve()

    def _find(path_tail: str):
        for up in (here,) + tuple(here.parents):
            cand = up / "serving_ui" / "app" / "utils" / path_tail
            if cand.exists():
                return up / "serving_ui", cand
        return None, None

    base_ui, ui_path   = _find("parlay_ui.py")
    base_ca, cart_path = _find("parlay_cart.py")
    base = base_ui or base_ca
    if not base:
        raise

    if str(base) not in sys.path:
        sys.path.insert(0, str(base))

    # ensure packages
    if "app" not in sys.modules:
        pkg_app = types.ModuleType("app"); pkg_app.__path__ = [str(base / "app")]; sys.modules["app"] = pkg_app
    if "app.utils" not in sys.modules:
        pkg_utils = types.ModuleType("app.utils"); pkg_utils.__path__ = [str(base / "app" / "utils")]; sys.modules["app.utils"] = pkg_utils

    # load modules by file and register under canonical names
    if ui_path:
        spec = importlib.util.spec_from_file_location("app.utils.parlay_ui", str(ui_path))
        mod = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        sys.modules["app.utils.parlay_ui"] = mod
        selectable_odds_table = mod.selectable_odds_table
    if cart_path:
        spec2 = importlib.util.spec_from_file_location("app.utils.parlay_cart", str(cart_path))
        mod2 = importlib.util.module_from_spec(spec2); assert spec2 and spec2.loader; spec2.loader.exec_module(mod2)  # type: ignore[attr-defined]
        sys.modules["app.utils.parlay_cart"] = mod2
        read_cart      = getattr(mod2, "read_cart")
        add_to_cart    = getattr(mod2, "add_to_cart")
        clear_cart     = getattr(mod2, "clear_cart")
# === /UltraImportGuard ===

# === AccessImportGuard ===
try:
    from app.lib.access import require_allowed_page, beta_banner, live_enabled  # type: ignore
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    _here = Path(__file__).resolve()
    for up in (_here,) + tuple(_here.parents):
        cand = up / "serving_ui" / "app" / "lib" / "access.py"
        if cand.exists():
            base = str((up / "serving_ui").resolve())
            if base not in sys.path:
                sys.path.insert(0, base)
            break
    try:
        from app.lib.access import require_allowed_page, beta_banner, live_enabled  # type: ignore
    except Exception:
        def live_enabled() -> bool: return False
        def require_allowed_page(_page_path: str) -> None: return None
        def beta_banner() -> None:
            try:
                import streamlit as st
                st.caption("🧪 Beta mode — access module missing; using shim.")
            except Exception:
                pass
# === /AccessImportGuard ===

# === UltraImportGuard (parlay_ui) ===
try:
    from app.utils.parlay_ui import selectable_odds_table
except Exception:
    import sys, types, importlib.util
    from pathlib import Path
    here = Path(__file__).resolve()
    base = path = None
    for up in (here,) + tuple(here.parents):
        cand = up / "serving_ui" / "app" / "utils" / "parlay_ui.py"
        if cand.exists():
            base, path = up / "serving_ui", cand
            break
    if not base or not path:
        raise
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    if "app" not in sys.modules:
        pkg_app = types.ModuleType("app")
        pkg_app.__path__ = [str(base / "app")]
        sys.modules["app"] = pkg_app
    if "app.utils" not in sys.modules:
        pkg_utils = types.ModuleType("app.utils")
        pkg_utils.__path__ = [str(base / "app" / "utils")]
        sys.modules["app.utils"] = pkg_utils
    spec = importlib.util.spec_from_file_location("app.utils.parlay_ui", str(path))
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    sys.modules["app.utils.parlay_ui"] = mod
    selectable_odds_table = mod.selectable_odds_table
# === /UltraImportGuard ===

# === AppImportGuard (auth) ===
try:
    from app.lib.auth import login, show_logout
except ModuleNotFoundError:
    import sys, types, importlib.util
    from pathlib import Path
    here = Path(__file__).resolve()
    base = auth_path = None
    for p in (here,) + tuple(here.parents):
        c1 = p / "serving_ui" / "app" / "lib" / "auth.py"
        if c1.exists():
            base, auth_path = p / "serving_ui", c1
            break
        c2 = p / "app" / "lib" / "auth.py"
        if c2.exists():
            base, auth_path = p, c2
            break
    if not base or not auth_path:
        raise
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    try:
        from app.lib.auth import login, show_logout  # type: ignore
    except ModuleNotFoundError:
        if "app" not in sys.modules:
            pkg_app = types.ModuleType("app")
            pkg_app.__path__ = [str(base / "app")]
            sys.modules["app"] = pkg_app
        if "app.lib" not in sys.modules:
            pkg_lib = types.ModuleType("app.lib")
            pkg_lib.__path__ = [str(base / "app" / "lib")]
            sys.modules["app.lib"] = pkg_lib
        spec = importlib.util.spec_from_file_location("app.lib.auth", str(auth_path))
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        assert spec and spec.loader
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        sys.modules["app.lib.auth"] = mod
        login, show_logout = mod.login, mod.show_logout
# === /AppImportGuard ===

# === Path bootstrap & refresh shim ===
import sys
from pathlib import Path
_HERE = Path(__file__).resolve()
_SERVING_UI = _HERE.parents[2]
if str(_SERVING_UI) not in sys.path:
    sys.path.insert(0, str(_SERVING_UI))
try:
    if live_enabled():
        try:
            from app.lib.access import do_expensive_refresh
        except Exception:
            def do_expensive_refresh(): return None
        do_expensive_refresh()
except Exception:
    pass
# === /Path bootstrap & refresh shim ===

import streamlit as st
st.set_page_config(page_title='09 All Picks Explorer', page_icon='📈', layout='wide')
from app.lib.compliance_gate import require_eligibility  # compliance gate
require_eligibility(min_age=18, restricted_states={"WA","ID","NV"})





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

# -------------- PAGE BODY --------------
require_allowed_page('pages/09_All_Picks_Explorer.py')
beta_banner()

import os, time
from pathlib import Path
from typing import List, Optional
import numpy as np
import pandas as pd
from app.utils.parlay_cart import read_cart, clear_cart
try:
    from app.utils.diagnostics import mount_in_sidebar
except Exception:
    def mount_in_sidebar(page_name: str): return None

TZ = 'America/New_York'

def _exports_dir() -> Path:
    env = os.environ.get('EDGE_EXPORTS_DIR', '').strip()
    if env:
        p = Path(env); p.mkdir(parents=True, exist_ok=True); return p
    here = Path(__file__).resolve()
    for up in [here.parent] + list(here.parents):
        if up.name.lower() == 'edge-finder':
            p = up / 'exports'; p.mkdir(parents=True, exist_ok=True); return p
    p = Path.cwd() / 'exports'; p.mkdir(parents=True, exist_ok=True); return p

def _age_str(p: Path) -> str:
    try:
        secs = int(time.time() - p.stat().st_mtime)
        return f'{secs}s' if secs < 60 else f'{secs // 60}m'
    except Exception:
        return 'n/a'

_ALIAS = {'REDSKINS': 'COMMANDERS', 'WASHINGTON': 'COMMANDERS', 'FOOTBALL': 'COMMANDERS', 'OAKLAND': 'RAIDERS', 'LV': 'RAIDERS', 'LAS': 'RAIDERS', 'VEGAS': 'RAIDERS', 'SD': 'CHARGERS', 'STL': 'RAMS'}

def _nickify(series: pd.Series) -> pd.Series:
    s = series.astype('string').fillna('').str.upper()
    s = s.str.replace('[^A-Z0-9 ]+', '', regex=True).str.strip().replace(_ALIAS)
    return s.str.replace('\\s+', '_', regex=True)

def _best_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    low = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in low:
            return low[c.lower()]
    return None

def _ensure_nicks(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    home_c = _best_col(df, ['_home_nick', 'home_nick', 'home', 'home_team', 'Home', 'HOME', 'team_home'])
    away_c = _best_col(df, ['_away_nick', 'away_nick', 'away', 'away_team', 'Away', 'AWAY', 'team_away'])
    if home_c is None:
        df['_home_nick'] = pd.Series([''] * len(df), dtype='string')
    else:
        df['_home_nick'] = _nickify(df[home_c].astype('string'))
    if away_c is None:
        df['_away_nick'] = pd.Series([''] * len(df), dtype='string')
    else:
        df['_away_nick'] = _nickify(df[away_c].astype('string'))
    return df

def _norm_market(m) -> str:
    m = (str(m) or '').strip().lower()
    if m in {'h2h', 'ml', 'moneyline', 'money line'}: return 'H2H'
    if m.startswith('spread') or m in {'spread', 'spreads'}: return 'SPREADS'
    if m.startswith('total') or m in {'total', 'totals'}: return 'TOTALS'
    return m.upper()

def _odds_to_decimal(o: pd.Series) -> pd.Series:
    o = pd.to_numeric(o, errors='coerce')
    return np.where(o > 0, 1 + o / 100.0, np.where(o < 0, 1 + 100.0 / np.abs(o), np.nan))

def _ensure_date_iso(df: pd.DataFrame, candidates: List[str]) -> pd.DataFrame:
    if len(df) == 0: return df
    for c in candidates:
        if c in df.columns:
            s = pd.to_datetime(df[c], errors='coerce', utc=True)
            df['_date_iso'] = s.dt.tz_convert(TZ).dt.strftime('%Y-%m-%d')
            break
    if '_date_iso' not in df.columns:
        df['_date_iso'] = pd.Series(pd.NA, index=df.index, dtype='string')
    return df

def latest_batch(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty: return df
    for col in ['_snapshot_ts_utc', 'snapshot_ts_utc', 'snapshot_ts', '_ts', 'ts']:
        if col in df.columns:
            ts = pd.to_datetime(df[col], errors='coerce', utc=True)
            last = ts.max()
            return df[ts == last].copy()
    return df

def within_next_week(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty: return df
    if '_date_iso' not in df.columns: return df
    d = pd.to_datetime(df['_date_iso'], errors='coerce', utc=True).dt.tz_convert(TZ)
    today = pd.Timestamp.now(tz=TZ).normalize()
    end = today + pd.Timedelta(days=7)
    return df[(d >= today) & (d <= end)].copy()

def refresh_button(key: Optional[str]=None):
    if st.button('🔄 Refresh data', key=key or f'refresh_{__name__}'):
        try: st.cache_data.clear()
        except Exception: pass
        st.rerun()

def _latest_csv(paths: list[Path]) -> Optional[Path]:
    paths = [p for p in paths if p and p.exists()]
    if not paths: return None
    return max(paths, key=lambda p: p.stat().st_mtime)

@st.cache_data(ttl=60)
def load_live() -> tuple[pd.DataFrame, Path]:
    exp = _exports_dir()
    cand = [exp / 'lines_live.csv', exp / 'lines_live_latest.csv']
    p = _latest_csv(cand) or cand[0]
    df = pd.read_csv(p, low_memory=False, encoding='utf-8-sig') if p.exists() else pd.DataFrame()
    return (df, p)

@st.cache_data(ttl=60)
def load_edges() -> tuple[pd.DataFrame, Path]:
    exp = _exports_dir()
    names = ['edges_standardized.csv', 'edges_graded_full_normalized_std.csv', 'edges_graded_full.csv', 'edges_normalized.csv', 'edges_master.csv']
    paths = [exp / n for n in names]
    p = _latest_csv(paths) or paths[0]
    df = pd.read_csv(p, low_memory=False, encoding='utf-8-sig') if p.exists() else pd.DataFrame()
    return (df, p)

diag = mount_in_sidebar('09_All_Picks_Explorer')
st.title('All Picks — Explorer')
refresh_button(key='refresh_09_all_picks')

live,  live_path  = load_live()
edges, edges_path = load_edges()
st.caption(f'Live lines: `{live_path}` · rows={len(live):,} · age={_age_str(live_path)}')
st.caption(f'Edges: `{edges_path}` · rows={len(edges):,}')

edges = _ensure_date_iso(edges, ['_date_iso', 'date', 'game_date', '_key_date', 'Date'])
live  = _ensure_date_iso(live,  ['_date_iso', 'event_date', 'commence_time', 'date', 'game_date', 'Date'])
edges = _ensure_nicks(edges)
live  = _ensure_nicks(live)
edges['_market_norm'] = edges.get('_market_norm', edges.get('market', pd.Series(index=edges.index))).map(_norm_market)
live ['_market_norm'] = live .get('_market_norm', live .get('market',  pd.Series(index=live .index))).map(_norm_market)

snap_live = within_next_week(latest_batch(live))

st.sidebar.header('Filters')
books = st.sidebar.multiselect('Books', sorted(snap_live.get('book', pd.Series(dtype='string')).dropna().unique()))
mkts  = st.sidebar.multiselect('Markets', sorted(snap_live.get('_market_norm', pd.Series(dtype='string')).dropna().unique()), default=['H2H', 'SPREADS', 'TOTALS'])
teams = st.sidebar.text_input('Team contains (nick)', '').strip().upper()

q = snap_live.copy()
if books: q = q[q.get('book', pd.Series(index=q.index)).isin(books)]
if mkts:  q = q[q.get('_market_norm', pd.Series(index=q.index)).isin(mkts)]
if teams: q = q[q['_home_nick'].str.contains(teams, na=False) | q['_away_nick'].str.contains(teams, na=False)]

cols    = [c for c in ['_date_iso','_home_nick','_away_nick','_market_norm','side','line','price','decimal','book'] if c in q.columns]
sort_by = [c for c in ['_date_iso','_home_nick','book','_market_norm','side'] if c in q.columns]

st.write(f'Showing {len(q):,} rows')
st.dataframe(q[cols].sort_values(sort_by), hide_index=True, width='stretch')

# Allow adding rows to cart from either edges or live
try:
    if 'edges' in globals() and isinstance(edges, pd.DataFrame):
        selectable_odds_table(edges, page_key='all_picks_edges', page_name='09_All_Picks_Explorer')
    if 'live' in globals() and isinstance(live, pd.DataFrame):
        selectable_odds_table(live,  page_key='all_picks_live',  page_name='09_All_Picks_Explorer')
except Exception:
    pass



