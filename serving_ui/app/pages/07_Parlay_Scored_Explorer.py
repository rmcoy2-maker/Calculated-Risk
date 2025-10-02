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
st.set_page_config(page_title='Parlay Scored Explorer', page_icon='📊', layout='wide')
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
require_allowed_page('pages/07_Parlay_Scored_Explorer.py')
beta_banner()

try:
    from app.utils.diagnostics import mount_in_sidebar
except Exception:
    def mount_in_sidebar(page_name: str): return None

from pathlib import Path
import numpy as np
import pandas as pd
from app.utils.parlay_cart import read_cart, clear_cart

PAGE_PROTECTED = False
auth = login(required=PAGE_PROTECTED)
if not auth.ok: st.stop()
show_logout()
auth = login(required=False)
if not auth.authenticated: st.info('You are in read-only mode.')
show_logout()

st.title('Parlay Scored Explorer')

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]

def load_edges_or_scores():
    repo = _repo_root()
    scores = repo / 'exports' / 'parlay_scores.csv'
    edges  = repo / 'exports' / 'edges.csv'
    if scores.exists() and scores.stat().st_size > 0:
        return (pd.read_csv(scores), str(scores))
    if edges.exists() and edges.stat().st_size > 0:
        return (pd.read_csv(edges), str(edges))
    return (pd.DataFrame(), str(edges))

df, src_path = load_edges_or_scores()
st.write(f'**Source:** `{src_path}` • **Rows:** {len(df):,}')
has_score = 'parlay_proba' in df.columns
if not has_score:
    st.warning('No `parlay_proba` found. Did you run `predict_parlay_score.py`? Showing base edges instead.', icon='⚠️')

def _num_unique(df, col):
    if col not in df.columns: return []
    s = pd.to_numeric(df[col], errors='coerce').dropna().astype(int)
    return sorted(s.unique().tolist())

seasons_all = _num_unique(df, 'season')
weeks_all   = _num_unique(df, 'week')

left, right = st.columns(2)
with left:
    season_options = ['All'] + [str(y) for y in seasons_all]
    season_sel = st.multiselect('Season', season_options, default=['All'])
with right:
    week_options = ['All'] + [str(w) for w in weeks_all or list(range(1, 23))]
    week_sel = st.multiselect('Week', week_options, default=['All'])

work = df.copy()
if 'All' not in season_sel and seasons_all:
    keep = {int(x) for x in season_sel if str(x).isdigit()}
    work = work[work['season'].astype('Int64').isin(keep)]
if 'All' not in week_sel:
    keep = {int(x) for x in week_sel if str(x).isdigit()}
    if 'week' in work.columns:
        work = work[work['week'].astype('Int64').isin(keep)]

if has_score:
    thr = st.slider('Min parlay probability', 0.0, 1.0, 0.7, 0.01)
    work = work[work['parlay_proba'].fillna(0) >= thr]
    st.caption(f'{len(work):,} rows ≥ {thr:.2f}')

pref_cols = [c for c in ['ts', 'season', 'week', 'sport', 'league', 'market', 'side', 'line', 'odds', 'p_win', 'ev', 'parlay_proba', 'dec_comb', 'legs', 'parlay_stake', 'team_name', 'home', 'away', 'game_id'] if c in work.columns]
with st.expander('Preview (top 2,500 rows)', expanded=True):
    st.dataframe((work[pref_cols] if pref_cols else work).head(2500), width='stretch')

st.download_button('Download filtered as CSV', data=work.to_csv(index=False).encode('utf-8'), file_name='parlay_scored_filtered.csv', mime='text/csv')

if has_score:
    arr = pd.to_numeric(work.get('parlay_proba'), errors='coerce').dropna().to_numpy()
    if arr.size:
        qs = np.quantile(arr, [0, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0])
        st.write('**Parlay probability quantiles:**', {k: round(float(v), 3) for k, v in zip(['min','25%','50%','75%','90%','95%','99%','max'], qs)})

try:
    if 'work' in globals() and isinstance(work, pd.DataFrame):
        selectable_odds_table(work, page_key='parlay_scored', page_name='07_Parlay_Scored_Explorer')
except Exception:
    pass



