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
st.set_page_config(page_title='Micro Calculations — Locks & Moonshots', page_icon='🧪', layout='wide')




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

st.title('Micro Calculations Locks & Moonshots')
st.caption('Locks: singles p_win ≥ threshold with EV ≥ 0 (stake capped). Moonshots: parlays with +odds ≥ threshold and positive EV.')
import json
import itertools
import math
from collections import Counter
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
from lib.io_paths import autoload_edges
edges_raw, df_path, root_path = autoload_edges(with_caption=True)
if edges_raw is None or edges_raw.empty:
    st.error('No edges found. Place your export in ./exports and reload.')
    st.stop()
exports_dir = Path(root_path) if root_path else Path.cwd() / 'exports'
exports_dir.mkdir(parents=True, exist_ok=True)
if st.button('Refresh data', type='primary'):
    try:
        from lib.io_paths import _read_cached
        _read_cached.clear()
    except Exception:
        pass
    st.rerun()

def american_to_decimal(odds: float | int) -> float:
    o = float(odds)
    if o >= 100:
        return 1.0 + o / 100.0
    if o <= -100:
        return 1.0 + 100.0 / abs(o)
    return float('nan')

def decimal_to_american(dec: float) -> int:
    if not np.isfinite(dec) or dec <= 1.0:
        return -100000
    profit = dec - 1.0
    if profit >= 1.0:
        return int(round(max(100, profit * 100), -1))
    return int(round(min(-100, -100 / profit), -1))

def implied_p_from_american(odds: float | int) -> float:
    o = float(odds)
    if o >= 100:
        return 100.0 / (o + 100.0)
    if o <= -100:
        return abs(o) / (abs(o) + 100.0)
    return float('nan')

def ev_per_dollar(odds_american: float | int, p_win: float) -> float:
    if not np.isfinite(odds_american) or not np.isfinite(p_win):
        return float('nan')
    o = float(odds_american)
    profit = o / 100.0 if o >= 100 else 100.0 / abs(o)
    return p_win * profit - (1.0 - p_win)

def kelly_fraction(odds_american: float | int, p: float, frac: float=0.25) -> float:
    if not np.isfinite(odds_american) or not np.isfinite(p):
        return 0.0
    o = float(odds_american)
    b = o / 100.0 if o >= 100 else 100.0 / abs(o)
    if b <= 0 or p <= 0 or p >= 1:
        return 0.0
    k = (b * p - (1 - p)) / b
    k = max(0.0, k)
    return round(min(frac * k, 0.5), 2)
ALT_ODDS = ['odds', 'american', 'price', 'price_american', 'american_odds']
ALT_PWIN = ['p_win', 'prob', 'model_p', 'win_prob', 'p', 'prob_win']
ALT_LINE = ['line', 'points', 'total', 'spread']
ALT_BOOK = ['book', 'sportsbook', 'bk']
ALT_GAME = ['game_id', 'ref', 'gid', 'game']

def _first_col(df: pd.DataFrame, cands: List[str]) -> Optional[str]:
    lower = {c.lower(): c for c in df.columns}
    for c in cands:
        if c in lower:
            return lower[c]
    return None

def normalize_edges(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    work = df.copy()
    work.rename(columns={c: c.lower() for c in work.columns}, inplace=True)
    odds_col = _first_col(work, ALT_ODDS)
    p_col = _first_col(work, ALT_PWIN)
    line_col = _first_col(work, ALT_LINE)
    book_col = _first_col(work, ALT_BOOK)
    game_col = _first_col(work, ALT_GAME)
    if odds_col:
        work[odds_col] = pd.to_numeric(work[odds_col], errors='coerce')
    if p_col:
        work[p_col] = pd.to_numeric(work[p_col], errors='coerce')
    if line_col:
        work[line_col] = pd.to_numeric(work[line_col], errors='coerce')
    work['odds_std'] = work[odds_col] if odds_col else np.nan
    work['p_win_std'] = work[p_col] if p_col else np.nan
    work['line_std'] = work[line_col] if line_col else None
    work['book_std'] = work[book_col] if book_col else ''
    work['game_id_std'] = work[game_col] if game_col else ''
    need = ~pd.to_numeric(work['p_win_std'], errors='coerce').notna()
    if odds_col:
        work.loc[need, 'p_win_std'] = work.loc[need, 'odds_std'].apply(implied_p_from_american)
    work['ev_std'] = work.apply(lambda r: ev_per_dollar(r.get('odds_std', np.nan), r.get('p_win_std', np.nan)), axis=1)
    diag = {'rows_total': int(len(work)), 'rows_with_odds': int(work['odds_std'].notna().sum()), 'rows_with_p': int(pd.to_numeric(work['p_win_std'], errors='coerce').notna().sum()), 'rows_pos_ev': int((work['ev_std'] >= 0).sum())}
    return (work, diag)
edges_norm, diag = normalize_edges(edges_raw)
CAND_PWIN_MIN = 0.35

def get_moonshot_candidates(norm: pd.DataFrame) -> pd.DataFrame:
    w = norm.copy()
    cand = w[(w['p_win_std'] > CAND_PWIN_MIN) & (w['ev_std'] > 0)].copy()
    cand['dec_odds'] = cand['odds_std'].apply(american_to_decimal)
    cand = cand[np.isfinite(cand['dec_odds'])]
    return cand.sort_values(['ev_std', 'dec_odds'], ascending=[False, False]).head(40).reset_index(drop=True)

def nCk(n: int, k: int) -> int:
    if k < 0 or k > n:
        return 0
    return math.comb(n, k)

def greedy_best_dec_odds(cand: pd.DataFrame, legs: int) -> float:
    if cand.empty or legs <= 0:
        return float('nan')
    top = cand['dec_odds'].sort_values(ascending=False).head(legs).tolist()
    if len(top) < legs:
        return float('nan')
    dec = 1.0
    for d in top:
        dec *= float(d)
    return dec

def build_locks(norm: pd.DataFrame, min_p_win: float, max_rows: int=200) -> pd.DataFrame:
    w = norm.copy()
    df = w[(w['p_win_std'] >= float(min_p_win)) & (w['ev_std'] >= 0)].copy()
    if df.empty:
        return pd.DataFrame(columns=['market', 'ref', 'side', 'line', 'odds', 'p_win', 'ev', 'stake', 'legs_json'])
    df['stake'] = df.apply(lambda r: kelly_fraction(r['odds_std'], r['p_win_std']), axis=1)
    df.loc[df['stake'] == 0, 'stake'] = 0.02
    if 'line_std' not in df:
        df['line_std'] = None
    df['ref'] = df.get('game_id_std', '')
    df['line'] = df.get('line_std', None)
    df['odds'] = df.get('odds_std', np.nan)
    df['p_win'] = df.get('p_win_std', np.nan)
    df['ev'] = df.get('ev_std', np.nan)
    df['market'] = df.get('market', df.get('bet_type', ''))
    df['side'] = df.get('side', df.get('selection', ''))
    df['legs_json'] = [[] for _ in range(len(df))]
    keep = ['market', 'ref', 'side', 'line', 'odds', 'p_win', 'ev', 'stake', 'legs_json']
    return df[keep].sort_values('ev', ascending=False).head(max_rows).reset_index(drop=True)

def _combo_respects_per_game(legs_json: List[Dict], per_game_cap: int) -> bool:
    gids = [l.get('game_id') for l in legs_json]
    counts = Counter(gids)
    return max(counts.values() or [0]) <= per_game_cap

def build_moonshots(norm: pd.DataFrame, min_plus: int, legs: int, max_per: int, per_game_cap: int) -> pd.DataFrame:
    """
    Build micro-parlays subject to:
      - positive EV
      - american odds ≥ min_plus
      - per-game cap: no more than `per_game_cap` legs from the same game (1 preferred; 2 allowed)
    """
    cand = get_moonshot_candidates(norm)
    if cand.empty:
        return pd.DataFrame(columns=['legs', 'american', 'p_combo', 'ev_est', 'stake', 'legs_json'])

    def _enumerate_with_cap(cap: int) -> List[Dict]:
        rows: List[Dict] = []
        L = max(1, int(legs))
        for combo in itertools.combinations(cand.to_dict('records'), r=L):
            p_combo, dec_combo = (1.0, 1.0)
            legs_json: List[Dict] = []
            valid = True
            for leg in combo:
                p = float(leg.get('p_win_std', np.nan))
                o = float(leg.get('odds_std', np.nan))
                if not np.isfinite(p) or not np.isfinite(o):
                    valid = False
                    break
                p_combo *= p
                dec_combo *= american_to_decimal(o)
                legs_json.append({'game_id': leg.get('game_id_std'), 'market': leg.get('market'), 'side': leg.get('side'), 'line': leg.get('line_std'), 'book': leg.get('book_std'), 'odds': leg.get('odds_std'), 'p_win': p, 'ev': leg.get('ev_std')})
            if not valid:
                continue
            if not _combo_respects_per_game(legs_json, cap):
                continue
            am = decimal_to_american(dec_combo)
            ev_est = p_combo * (dec_combo - 1.0) - (1.0 - p_combo)
            if am < int(min_plus) or ev_est <= 0:
                continue
            rows.append({'legs': L, 'american': am, 'p_combo': round(p_combo, 4), 'ev_est': round(ev_est, 4), 'stake': 0.1, 'legs_json': legs_json})
            if len(rows) >= int(max_per):
                break
        return rows
    rows = _enumerate_with_cap(per_game_cap)
    if not rows and per_game_cap == 1:
        rows = _enumerate_with_cap(2)
    if not rows:
        return pd.DataFrame(columns=['legs', 'american', 'p_combo', 'ev_est', 'stake', 'legs_json'])
    return pd.DataFrame(rows).sort_values(['ev_est', 'american'], ascending=[False, False]).reset_index(drop=True)

def write_micro_bets_csv(exports: Path, locks: pd.DataFrame, moons: pd.DataFrame) -> Path:
    out = exports / 'micro_bets.csv'

    def _prep(df: pd.DataFrame, section: str) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        d = df.copy()
        d['section'] = section
        d['legs_json'] = d.get('legs_json', pd.Series([[]] * len(d))).apply(lambda x: json.dumps(x, ensure_ascii=False))
        return d
    merged = pd.concat([_prep(locks, 'lock'), _prep(moons, 'moonshot')], ignore_index=True, sort=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out, index=False)
    return out

def make_combined(locks_df: pd.DataFrame, moons_df: pd.DataFrame) -> pd.DataFrame:
    parts = []
    if isinstance(locks_df, pd.DataFrame) and (not locks_df.empty):
        a = locks_df.copy()
        a['type'] = 'single'
        a['legs'] = 1
        a['american'] = pd.to_numeric(a['odds'], errors='coerce')
        a['p_combo'] = pd.to_numeric(a['p_win'], errors='coerce')
        a['ev_est'] = pd.to_numeric(a['ev'], errors='coerce')
        a['name'] = a.get('ref', '')
        parts.append(a[['type', 'legs', 'american', 'p_combo', 'ev_est', 'stake', 'name', 'legs_json']])
    if isinstance(moons_df, pd.DataFrame) and (not moons_df.empty):
        b = moons_df.copy()
        b['type'] = 'parlay'
        b['name'] = b['legs'].astype(str) + '-leg parlay'
        parts.append(b[['type', 'legs', 'american', 'p_combo', 'ev_est', 'stake', 'name', 'legs_json']])
    if not parts:
        return pd.DataFrame(columns=['type', 'legs', 'american', 'p_combo', 'ev_est', 'stake', 'name', 'legs_json'])
    out = pd.concat(parts, ignore_index=True, sort=False)
    return out.sort_values(['type', 'ev_est', 'american'], ascending=[True, False, False]).reset_index(drop=True)
c1, c2, c3, c4, c5 = st.columns([1.1, 1.1, 1.0, 1.0, 1.0])
with c1:
    min_p_win = st.slider('Locks min p_win', 0.55, 0.89, 0.6, 0.01)
with c2:
    moon_min_plus = st.number_input('Moonshots min odds (+)', min_value=100, max_value=10000, value=600, step=50)
with c3:
    moon_legs = st.number_input('Moonshot legs', min_value=3, max_value=10, value=3, step=1)
with c4:
    per_game_cap = st.selectbox('Max legs per game (micro)', options=[1, 2], index=0, help='Prefer 1. Will relax to 2 automatically if nothing passes.')
with c5:
    max_per = st.number_input('Max per section', min_value=1, max_value=50, value=5, step=1)
run = st.button('Generate Micro Calculations')
status = st.empty()
locks_df = pd.DataFrame()
moons_df = pd.DataFrame()
if run:
    locks_df = build_locks(edges_norm, min_p_win=min_p_win)
    moons_df = build_moonshots(edges_norm, min_plus=int(moon_min_plus), legs=int(moon_legs), max_per=int(max_per), per_game_cap=int(per_game_cap))
    outpath = write_micro_bets_csv(exports_dir, locks_df, moons_df)
    status.success(f'Wrote {outpath}')
st.subheader('Locks')
if locks_df.empty:
    st.info('No locks found for the current thresholds.')
else:
    st.dataframe(locks_df.style.format({'odds': '{:.0f}', 'p_win': '{:.2f}', 'ev': '{:.2f}', 'stake': '{:.2f}'}), height=min(420, 60 + 35 * len(locks_df)), width='stretch')
st.subheader('Moonshots')
if moons_df.empty:
    st.info('No moonshots met the criteria yet. Try lowering the odds threshold or legs.')
else:
    st.dataframe(moons_df[['legs', 'american', 'p_combo', 'ev_est', 'stake']].style.format({'american': '{:.0f}', 'p_combo': '{:.2f}', 'ev_est': '{:.2f}', 'stake': '{:.2f}'}), height=min(360, 60 + 35 * len(moons_df)), width='stretch')
    for i, row in moons_df.iterrows():
        with st.expander(f"Moonshot {i + 1}: +{int(row['american'])} — {int(row['legs'])} legs (EV≈{row['ev_est']:.2f})"):
            legs_json = row['legs_json']
            if isinstance(legs_json, str):
                try:
                    legs_json = json.loads(legs_json)
                except Exception:
                    legs_json = []
            if not legs_json:
                st.write('No legs recorded.')
            else:
                legs_df = pd.DataFrame(legs_json)
                cols = [c for c in ['game_id', 'market', 'side', 'line', 'book', 'odds', 'p_win', 'ev'] if c in legs_df.columns]
                st.dataframe(legs_df[cols].style.format({'odds': '{:.0f}', 'p_win': '{:.2f}', 'ev': '{:.2f}'}), width='stretch')
    with st.expander('Exploded legs (all moonshots)'):
        ex = moons_df.copy()
        ex['legs_json'] = ex['legs_json'].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
        ex = ex.explode('legs_json', ignore_index=True)
        if not ex.empty:
            for c in ['game_id', 'market', 'side', 'line', 'book', 'odds', 'p_win', 'ev']:
                ex[c] = ex['legs_json'].apply(lambda d: d.get(c) if isinstance(d, dict) else None)
            st.dataframe(ex[['american', 'p_combo', 'ev_est', 'stake', 'game_id', 'market', 'side', 'line', 'book', 'odds', 'p_win', 'ev']].style.format({'american': '{:.0f}', 'p_combo': '{:.2f}', 'ev_est': '{:.2f}', 'odds': '{:.0f}', 'p_win': '{:.2f}', 'ev': '{:.2f}'}), width='stretch')
combined_df = make_combined(locks_df, moons_df)
st.subheader('Combined (singles + parlays)')
if combined_df.empty:
    st.info('Nothing to show yet. Click **Generate Micro Calculations**.')
else:
    st.dataframe(combined_df[['type', 'legs', 'american', 'p_combo', 'ev_est', 'stake', 'name']].style.format({'american': '{:.0f}', 'p_combo': '{:.2f}', 'ev_est': '{:.2f}', 'stake': '{:.2f}'}), height=min(420, 60 + 35 * len(combined_df)), width='stretch')
    st.download_button('Download combined_micro_bets.csv', data=combined_df.to_csv(index=False).encode('utf-8'), file_name='combined_micro_bets.csv', mime='text/csv')
st.divider()
left, right = st.columns([1, 3])
with left:
    out = exports_dir / 'micro_bets.csv'
    if out.exists():
        st.download_button('Download micro_bets.csv', data=out.read_bytes(), file_name='micro_bets.csv', mime='text/csv')
with right:
    with st.expander('Diagnostics'):
        st.write(f'exports dir: `{exports_dir}`')
        st.write(f'edges file: `{df_path}`')
        st.write(f'edges rows: {len(edges_raw):,}')
        st.table(pd.DataFrame([{'total': diag['rows_total'], 'with_odds': diag['rows_with_odds'], 'with_p': diag['rows_with_p'], 'positive_ev': diag['rows_pos_ev']}]))







