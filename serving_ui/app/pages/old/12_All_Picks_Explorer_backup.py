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
import os
from pathlib import Path
import numpy as np
import pandas as pd
from lib.io_paths import autoload_edges, find_exports_dir
df, df_path, root_path = autoload_edges(with_caption=True)
if st.button('Refresh data', type='primary'):
    from lib.io_paths import _read_cached
    _read_cached.clear()
    st.rerun()
st.set_page_config(page_title='All Picks Explorer', page_icon='🧭', layout='wide')





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

def find_exports_dir() -> Path | None:
    env = os.environ.get('EDGE_FINDER_ROOT')
    if env:
        p = Path(env) / 'exports'
        if p.exists():
            return p
    try:
        here = Path(__file__).resolve()
    except Exception:
        here = Path.cwd()
    for up in [here] + list(here.parents):
        cand = up / 'exports'
        if cand.exists():
            return cand
    cwd = Path.cwd()
    for up in [cwd] + list(cwd.parents):
        cand = up / 'exports'
        if cand.exists():
            return cand
    return None
EXPORTS = find_exports_dir()

def _read_any(p: Path) -> pd.DataFrame:
    try:
        if p.suffix == '.feather':
            return pd.read_feather(p)
        if p.suffix == '.parquet':
            return pd.read_parquet(p)
        return pd.read_csv(p, low_memory=False, encoding='utf-8-sig')
    except Exception:
        try:
            return pd.read_csv(p, engine='python', low_memory=False)
        except Exception:
            return pd.DataFrame()

@st.cache_data(show_spinner=False)
def load_edges() -> pd.DataFrame:
    names = ['edges_graded_plus.csv', 'edges_graded_wlp.csv', 'edges_graded.csv', 'edges.csv']
    candidates = []
    if EXPORTS:
        for n in names:
            candidates.append(EXPORTS / n)
    for n in names:
        candidates.append(Path('exports') / n)
    seen = []
    for p in candidates:
        if p.exists() and p.stat().st_size > 512:
            df = _read_any(p)
            if not df.empty and len(df.columns) > 1:
                df.__loaded_from__ = str(p)
                seen.append((len(df), df))
    if seen:
        seen.sort(key=lambda t: t[0], reverse=True)
        return seen[0][1]
    return pd.DataFrame()

def american_to_decimal(odds):
    arr = pd.to_numeric(odds, errors='coerce')
    dec = pd.Series(np.nan, index=arr.index, dtype='float64')
    pos, neg = (arr > 0, arr < 0)
    dec.loc[pos] = 1.0 + arr.loc[pos] / 100.0
    dec.loc[neg] = 1.0 + 100.0 / arr.loc[neg].abs()
    return dec

def implied_prob_from_american(odds):
    arr = pd.to_numeric(odds, errors='coerce')
    p = pd.Series(np.nan, index=arr.index, dtype='float64')
    pos, neg = (arr > 0, arr < 0)
    p.loc[pos] = 100.0 / (arr.loc[pos] + 100.0)
    p.loc[neg] = -arr.loc[neg] / (-arr.loc[neg] + 100.0)
    return p

def ev_per_dollar_series(p, odds):
    p = pd.to_numeric(p, errors='coerce')
    dec = american_to_decimal(odds)
    ev = p * (dec - 1.0) - (1.0 - p)
    bad = p.isna() | dec.isna() | (dec <= 1.0)
    ev[bad] = np.nan
    return ev

def norm_lower(s):
    return s.astype(str).str.strip().str.lower()

def first_existing(df: pd.DataFrame, cols: list[str]):
    for c in cols:
        if c in df.columns:
            return c
    return None

def best_kickoff_series(df: pd.DataFrame) -> pd.Series:
    for c in ['sort_ts', 'kickoff_ts', 'game_time', 'datetime', 'date']:
        if c in df.columns:
            try:
                s = pd.to_datetime(df[c], errors='coerce', utc=True)
                if s.notna().any():
                    return s
            except Exception:
                pass
    for a, b in [('event_date', 'event_time'), ('game_date', 'game_time'), ('date', 'time')]:
        if a in df.columns and b in df.columns:
            try:
                s = pd.to_datetime(df[a].astype(str) + ' ' + df[b].astype(str), errors='coerce', utc=True)
                if s.notna().any():
                    return s
            except Exception:
                pass
    return pd.to_datetime(pd.Series([None] * len(df)), errors='coerce')
st.title('All Picks Explorer')
col_refresh, _ = st.columns([1, 5])
with col_refresh:
    if st.button('🔄 Refresh data'):
        st.cache_data.clear()
        st.rerun()
df, df_path, root_path = autoload_edges(with_caption=True)
st.caption(f"Loaded: {df_path or '—'} · exports root: {root_path or '(not found)'} · rows={len(df):,} · cols={len(df.columns)}")
if df.empty:
    st.stop()
df['sport_norm'] = norm_lower(df.get('sport', 'nfl'))
df['market_norm'] = norm_lower(df.get('market', df.get('market_norm', '')))
gid_col = first_existing(df, ['game_id', 'game_key', 'event_id', 'fixture_id', 'match_id', 'uuid', 'id', 'gid', 'game_uuid'])
if gid_col:
    df['game_id'] = df[gid_col].astype(str)
else:
    home = df.get('home_team', df.get('home', ''))
    away = df.get('away_team', df.get('away', ''))
    df['game_id'] = df.get('season', '').astype(str) + '-' + df.get('week', '').astype(str) + '-' + away.astype(str) + '@' + home.astype(str)
df['kickoff_utc'] = best_kickoff_series(df)
df['season'] = pd.to_numeric(df.get('season'), errors='coerce').astype('Int64')
wk_col = first_existing(df, ['week', 'wk', 'game_week', 'schedule_week', 'week_num'])
if wk_col:
    df['week'] = pd.to_numeric(df[wk_col], errors='coerce').astype('Int64')
else:
    df['week'] = pd.Series([pd.NA] * len(df), dtype='Int64')
if df['week'].isna().all() and 'kickoff_utc' in df.columns:
    try:
        df['week'] = pd.to_datetime(df['kickoff_utc'], errors='coerce', utc=True).dt.isocalendar().week.astype('Int64')
    except Exception:
        pass
home_col = first_existing(df, ['home_team', 'home', 'home_name', 'home_abbr'])
away_col = first_existing(df, ['away_team', 'away', 'away_name', 'away_abbr'])
if home_col and away_col:
    df['matchup'] = df[away_col].astype(str) + ' @ ' + df[home_col].astype(str)
else:
    df['matchup'] = df.get('team', '').astype(str)
with st.sidebar:
    st.subheader('Filters')
    sports = sorted(df['sport_norm'].dropna().unique().tolist()) or ['nfl']
    seasons = sorted(pd.to_numeric(df.get('season'), errors='coerce').dropna().astype(int).unique().tolist())
    markets = sorted(df['market_norm'].dropna().unique().tolist())
    sport_sel = st.selectbox('Sport', sports, index=sports.index('nfl') if 'nfl' in sports else 0)
    season_sel = st.selectbox('Season', seasons or ['—'], index=len(seasons) - 1 if seasons else 0)
    market_sel = st.multiselect('Markets', markets, default=[m for m in ['spread', 'total', 'moneyline'] if m in markets] or markets[:1])
    settled_only = st.toggle('Settled only', value=False)
    hide_empty_weeks = st.toggle('Hide empty weeks (None)', value=True)
    st.divider()
    st.subheader('Like rules (✅)')
    min_ev = st.slider('Min EV per $1', -1.0, 1.0, 0.0, 0.01)
    min_prob_edge = st.slider('Min prob edge (p_model - implied)', -0.5, 0.5, 0.0, 0.01)
    likes_only = st.toggle('Show only likes', value=False)
    search_txt = st.text_input('Search (game_id / matchup / team / selection / book)', '')

def apply_filters(df):
    notes = []
    work = df.copy()
    if sport_sel:
        work = work[work['sport_norm'] == sport_sel]
    if season_sel not in (None, '—'):
        w_season = work[pd.to_numeric(work.get('season'), errors='coerce').astype('Int64') == int(season_sel)]
        if w_season.empty:
            seasons_avail = pd.to_numeric(work.get('season'), errors='coerce').dropna().astype(int).sort_values().unique().tolist()
            if seasons_avail:
                fallback_season = seasons_avail[-1]
                notes.append(f'Season {season_sel} is empty; auto-switched to {fallback_season}.')
                work = work[pd.to_numeric(work.get('season'), errors='coerce').astype('Int64') == fallback_season]
            else:
                notes.append('No seasons have rows for this sport; showing all seasons.')
        else:
            work = w_season
    valid_markets = set(work['market_norm'].dropna().unique().tolist()) if 'market_norm' in work.columns else set()
    selected = [m for m in market_sel or [] if m in valid_markets]
    if selected:
        work = work[work['market_norm'].isin(selected)]
    elif market_sel:
        notes.append('Selected markets not present in filtered data; showing all markets.')
    if settled_only and 'settled_bool' in work.columns and work['settled_bool'].notna().any():
        w2 = work[work['settled_bool'].fillna(False)]
        if w2.empty:
            notes.append('‘Settled only’ removed all rows; showing unsettled too.')
        else:
            work = w2
    if hide_empty_weeks and 'week' in work.columns:
        w2 = work[pd.to_numeric(work['week'], errors='coerce').notna()]
        if w2.empty:
            notes.append('‘Hide empty weeks’ removed all rows; including empty/None weeks.')
        else:
            work = w2
    return (work, notes)
work, widen_notes = apply_filters(df)
with st.expander('Filtering diagnostics', expanded=False):
    diag = {'sport_sel': sport_sel, 'season_sel': season_sel, 'selected_markets': market_sel, 'settled_only': settled_only, 'hide_empty_weeks': hide_empty_weeks, 'likes_only': likes_only, 'min_ev': float(min_ev), 'min_prob_edge': float(min_prob_edge), 'rows_after_filters': int(len(work))}
    st.write(diag)
    if widen_notes:
        st.write({'auto_widening': widen_notes})
if work.empty:
    st.warning('No rows after filters. Try turning off ‘Settled only’, unchecking ‘Hide empty weeks’, selecting a season that has rows, or clearing the Markets filter.')
    st.stop()
if 'odds' in work.columns:
    work['implied_p(odds)'] = implied_prob_from_american(work['odds'])
    work['dec_odds'] = american_to_decimal(work['odds'])
    p_model = next((c for c in ['p_model', 'p', 'prob', 'prob_model', 'win_prob'] if c in work.columns), None)
    if p_model is None:
        p_model = 'implied_p(odds)'
    work['p_model_use'] = pd.to_numeric(work[p_model], errors='coerce')
    work['ev/$1'] = ev_per_dollar_series(work['p_model_use'], work['odds'])
    work['p_edge'] = work['p_model_use'] - work['implied_p(odds)']
else:
    work['implied_p(odds)'] = np.nan
    work['dec_odds'] = np.nan
    work['ev/$1'] = np.nan
    work['p_edge'] = np.nan
    work['p_model_use'] = np.nan
like_mask = (pd.to_numeric(work['ev/$1'], errors='coerce').fillna(-9) >= float(min_ev)) & (pd.to_numeric(work['p_edge'], errors='coerce').fillna(-9) >= float(min_prob_edge))
work['✓'] = np.where(like_mask, '✅', '')
if likes_only:
    w2 = work[like_mask]
    if w2.empty:
        st.info('‘Show only likes’ removed all rows; showing all picks that pass the other filters.')
    else:
        work = w2
if search_txt.strip():
    s = search_txt.strip().lower()
    hay = pd.Series('', index=work.index)
    for c in ['game_id', 'matchup', 'team', 'selection', 'book', 'home_team', 'away_team']:
        if c in work.columns:
            hay = hay + ' ' + work[c].astype(str).str.lower()
    work = work[hay.str.contains(s, na=False)]
sort_cols = []
if '✓' in work.columns:
    sort_cols.append(('✓', False))
if 'kickoff_utc' in work.columns and work['kickoff_utc'].notna().any():
    sort_cols.append(('kickoff_utc', True))
if 'ev/$1' in work.columns:
    sort_cols.append(('ev/$1', False))
if sort_cols:
    by = [c for c, _ in sort_cols]
    asc = [a for _, a in sort_cols]
    work = work.sort_values(by=by, ascending=asc)
st.subheader('Picks')
show_cols_base = ['✓', 'kickoff_utc', 'game_id', 'matchup', 'season', 'week', 'sport', 'market_norm', 'team', 'selection', 'book', 'line', 'total', 'spread', 'odds', 'dec_odds', 'implied_p(odds)', 'p_model_use', 'p_edge', 'ev/$1', 'result_norm']
show_cols = [c for c in show_cols_base if c in work.columns]
colcfg = {'✓': st.column_config.TextColumn(width='small'), 'kickoff_utc': st.column_config.DatetimeColumn(format='YYYY-MM-DD HH:mm', timezone='UTC'), 'game_id': st.column_config.TextColumn('game_id'), 'matchup': st.column_config.TextColumn('matchup'), 'season': st.column_config.NumberColumn(format='%d'), 'week': st.column_config.NumberColumn(format='%d'), 'sport': st.column_config.TextColumn('sport'), 'market_norm': st.column_config.TextColumn('market'), 'team': st.column_config.TextColumn(), 'selection': st.column_config.TextColumn(), 'book': st.column_config.TextColumn(), 'line': st.column_config.NumberColumn(format='%.2f'), 'total': st.column_config.NumberColumn(format='%.2f'), 'spread': st.column_config.NumberColumn(format='%.2f'), 'odds': st.column_config.NumberColumn(format='%d'), 'dec_odds': st.column_config.NumberColumn(format='%.3f'), 'implied_p(odds)': st.column_config.NumberColumn(format='%.3f'), 'p_model_use': st.column_config.NumberColumn(format='%.3f', label='p_model'), 'p_edge': st.column_config.NumberColumn(format='+.3f', label='p_edge'), 'ev/$1': st.column_config.NumberColumn(format='%.3f'), 'result_norm': st.column_config.TextColumn('result')}
st.dataframe(work[show_cols].head(5000), hide_index=True, column_config=colcfg, height=580, width='stretch')
if 'ev/$1' in work.columns:
    evdesc = pd.to_numeric(work['ev/$1'], errors='coerce').describe()
    cA, cB, cC, cD, cE = st.columns(5)
    cA.metric('Rows', f'{len(work):,}')
    cB.metric('Likes', f"{int((work['✓'] == '✅').sum()):,}")
    cC.metric('Avg EV/$1', f"{evdesc.get('mean', 0):.3f}")
    cD.metric('75% EV/$1', f"{evdesc.get('75%', 0):.3f}")
    cE.metric('Max EV/$1', f"{evdesc.get('max', 0):.3f}")
csv = work[show_cols].to_csv(index=False).encode('utf-8')
st.download_button('⬇️ Download filtered CSV', data=csv, file_name='picks_filtered_fullclean.csv', mime='text/csv')






