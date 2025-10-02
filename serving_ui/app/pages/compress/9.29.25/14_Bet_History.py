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
st.set_page_config(page_title='14 Calculated History', page_icon='📈', layout='wide')




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
import sys, io
from pathlib import Path
import numpy as np
import pandas as pd
st.markdown('\n<style>\n  .block-container { max-width: none !important; padding-left: 1rem; padding-right: 1rem; }\n</style>\n', unsafe_allow_html=True)
HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
EXP = REPO / 'exports'
BETLOG = EXP / 'bets_log.csv'
SCORES_CANDIDATES = [EXP / 'scores_1966-2025.csv', EXP / 'scores_normalized_std_maxaligned.csv']
st.title('📜 Calculated History')
st.caption(f'Using log: {BETLOG}')

def _s(x):
    if isinstance(x, pd.Series):
        return x.astype('string').fillna('')
    return pd.Series([x], dtype='string')

def _nickify(s: pd.Series) -> pd.Series:
    _ALIAS = {'REDSKINS': 'COMMANDERS', 'WASHINGTON': 'COMMANDERS', 'FOOTBALL': 'COMMANDERS', 'OAKLAND': 'RAIDERS', 'LV': 'RAIDERS', 'LAS': 'RAIDERS', 'VEGAS': 'RAIDERS', 'SD': 'CHARGERS', 'LA': 'RAMS', 'STL': 'RAMS'}
    s = _s(s).str.upper().str.replace('[^A-Z0-9 ]+', '', regex=True).str.strip().replace(_ALIAS)
    return s.str.replace('\\s+', '_', regex=True)

def _int_str(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors='coerce').astype('Int64').astype('string').fillna('')

def _market_norm(s: pd.Series) -> pd.Series:
    s = _s(s).str.upper().str.replace('\\s+', '', regex=True)
    return s.replace({'MONEYLINE': 'H2H', 'ML': 'H2H', 'SPREAD': 'SPREADS', 'ATS': 'SPREADS', 'TOTAL': 'TOTALS', 'TOTALSPOINTS': 'TOTALS', 'OU': 'TOTALS', 'O/U': 'TOTALS'})

def _pick_team_series(df: pd.DataFrame) -> pd.Series:
    if '_pick_team' in df.columns and df['_pick_team'].astype(str).str.strip().ne('').any():
        return _nickify(df['_pick_team'])
    side = _s(df.get('side', '')).str.upper()
    return np.where(side == 'HOME', df.get('_home_nick', ''), np.where(side == 'AWAY', df.get('_away_nick', ''), '')).astype('string')

def _american_profit_per_dollar(odds: float, result: str) -> float:
    if pd.isna(odds) or result not in {'WIN', 'LOSE', 'PUSH', 'VOID'}:
        return np.nan
    if result in {'PUSH', 'VOID'}:
        return 0.0
    if odds >= 100:
        return odds / 100.0 if result == 'WIN' else -1.0
    else:
        return 100.0 / abs(odds) if result == 'WIN' else -1.0

def _normalize_scores(sc: pd.DataFrame) -> pd.DataFrame:
    s = sc.copy()
    date_raw = _s(s.get('Date', s.get('_Date', s.get('date', ''))))
    s['_DateISO'] = pd.to_datetime(date_raw, errors='coerce').dt.date.astype('string').fillna('')
    s['_season'] = _int_str(_s(s.get('season', s.get('Season', ''))))
    s['_week'] = _int_str(_s(s.get('week', s.get('Week', ''))))
    s['_home_nick'] = _nickify(_s(s.get('home_team', s.get('HomeTeam', s.get('_home_nick', '')))))
    s['_away_nick'] = _nickify(_s(s.get('away_team', s.get('AwayTeam', s.get('_away_nick', '')))))
    s['home_score'] = pd.to_numeric(s.get('HomeScore', s.get('home_score')), errors='coerce')
    s['away_score'] = pd.to_numeric(s.get('AwayScore', s.get('away_score')), errors='coerce')
    ymd = pd.to_datetime(s['_DateISO'], errors='coerce').dt.strftime('%Y%m%d').fillna('')
    s['_key_date'] = (ymd + '_' + s['_away_nick'] + '_AT_' + s['_home_nick']).str.strip('_')
    s['_key_home_sw'] = s['_home_nick'] + '|' + s['_season'] + '|' + s['_week']
    s['_key_away_sw'] = s['_away_nick'] + '|' + s['_season'] + '|' + s['_week']
    return s.astype({'_key_date': 'string', '_key_home_sw': 'string', '_key_away_sw': 'string'})

def _attach_scores_generic(df: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    e = df.copy()
    sc = scores[['_key_date', '_key_home_sw', '_key_away_sw', 'home_score', 'away_score']].copy()
    merged = e.merge(sc[['_key_date', 'home_score', 'away_score']], on='_key_date', how='left')
    miss = merged['home_score'].isna() | merged['away_score'].isna()
    if miss.any():
        fb = e.loc[miss, ['_key_home_sw', '_key_away_sw']].merge(sc, on=['_key_home_sw', '_key_away_sw'], how='left').set_index(e.loc[miss].index)
        for c in ('home_score', 'away_score'):
            merged.loc[miss, c] = fb[c]
    merged['_joined_with_scores'] = ~merged['home_score'].isna() & ~merged['away_score'].isna()
    return merged

def _settle_minimal(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d['market_norm'] = _market_norm(d.get('market', ''))
    d['_pick_nick'] = _pick_team_series(d)
    hs = pd.to_numeric(d.get('home_score'), errors='coerce')
    as_ = pd.to_numeric(d.get('away_score'), errors='coerce')
    line = pd.to_numeric(d.get('line', d.get('spread', d.get('total'))), errors='coerce')
    price = pd.to_numeric(d.get('price', d.get('odds')), errors='coerce')
    winner = np.where(hs > as_, d.get('_home_nick', ''), np.where(as_ > hs, d.get('_away_nick', ''), ''))
    result = np.full(len(d), 'VOID', dtype=object)
    is_ml = d['market_norm'].eq('H2H')
    result[is_ml] = np.where(pd.Series(winner, index=d.index)[is_ml].eq(''), 'PUSH', np.where(d.loc[is_ml, '_pick_nick'].eq(pd.Series(winner, index=d.index)[is_ml]), 'WIN', np.where(d.loc[is_ml, '_pick_nick'].eq(''), 'VOID', 'LOSE')))
    is_spread = d['market_norm'].eq('SPREADS')
    if is_spread.any():
        margin = hs - as_
        picked = np.where(d.loc[is_spread, '_pick_nick'].eq(d.loc[is_spread, '_home_nick']), line[is_spread], -line[is_spread])
        result[is_spread] = np.where(margin[is_spread] > picked, 'WIN', np.where(margin[is_spread] < picked, 'LOSE', 'PUSH'))
    is_totals = d['market_norm'].eq('TOTALS')
    if is_totals.any():
        side = _s(d.get('side', '')).str.upper()
        total_pts = hs + as_
        result[is_totals] = np.where(total_pts[is_totals] == line[is_totals], 'PUSH', np.where(side[is_totals].eq('OVER') & (total_pts[is_totals] > line[is_totals]) | side[is_totals].eq('UNDER') & (total_pts[is_totals] < line[is_totals]), 'WIN', 'LOSE'))
    d['_result'] = pd.Series(result, index=d.index, dtype='string')
    d['_profit_per_$1'] = [_american_profit_per_dollar(o, r) for o, r in zip(price, d['_result'])]
    return d
if not BETLOG.exists():
    st.info('No Calculated Log found yet.')
    with st.expander('Diagnostics'):
        st.write('Expected path:', str(BETLOG))
    st.stop()
bets = pd.read_csv(BETLOG, encoding='utf-8-sig', low_memory=False)
st.caption(f'Rows: {len(bets):,}')
need_cols = {'_key_date', '_key_home_sw', '_key_away_sw'}
if need_cols.issubset(set(bets.columns)):
    spath = next((p for p in SCORES_CANDIDATES if p.exists()), None)
    if spath:
        scores = pd.read_csv(spath, low_memory=False)
        if not {'_key_date', '_key_home_sw', '_key_away_sw', 'home_score', 'away_score'} <= set(scores.columns):
            scores = _normalize_scores(scores)
        bets = _attach_scores_generic(bets, scores)
        st.caption(f"With scores joined: {int(bets['_joined_with_scores'].sum()):,} matched")
        bets = _settle_minimal(bets)
st.dataframe(bets, width='stretch')
if '_result' in bets.columns:
    st.subheader('Metrics')
    bets['market_norm'] = _market_norm(bets.get('market', ''))
    if '_pick_nick' not in bets.columns or bets['_pick_nick'].eq('').all():
        bets['_pick_nick'] = _pick_team_series(bets)
    team_tbl = bets.assign(is_win=bets['_result'].eq('WIN'), is_loss=bets['_result'].eq('LOSE'), is_push=bets['_result'].eq('PUSH')).groupby('_pick_nick', dropna=False).agg(bets=('market_norm', 'size'), wins=('is_win', 'sum'), losses=('is_loss', 'sum'), pushes=('is_push', 'sum'), profit=('_profit_per_$1', 'sum'), roi_per_bet=('_profit_per_$1', 'mean')).reset_index().rename(columns={'_pick_nick': 'team'}).sort_values('profit', ascending=False)
    kind_tbl = bets.groupby('market_norm', dropna=False).agg(bets=('market_norm', 'size'), wins=lambda x: (bets.loc[x.index, '_result'] == 'WIN').sum(), losses=lambda x: (bets.loc[x.index, '_result'] == 'LOSE').sum(), pushes=lambda x: (bets.loc[x.index, '_result'] == 'PUSH').sum(), profit=('_profit_per_$1', 'sum'), roi_per_bet=('_profit_per_$1', 'mean')).reset_index().rename(columns={'market_norm': 'market'}).sort_values('profit', ascending=False)
    c1, c2 = st.columns(2)
    with c1:
        st.caption('Team performance (your bets)')
        st.dataframe(team_tbl, hide_index=True, width='stretch')
        b1 = io.StringIO()
        team_tbl.to_csv(b1, index=False, encoding='utf-8-sig')
        st.download_button('Download team performance CSV', b1.getvalue(), 'bet_history_team_performance.csv', 'text/csv')
    with c2:
        st.caption('Bet performance by market')
        st.dataframe(kind_tbl, hide_index=True, width='stretch')
        b2 = io.StringIO()
        kind_tbl.to_csv(b2, index=False, encoding='utf-8-sig')
        st.download_button('Download bet-type breakdown CSV', b2.getvalue(), 'bet_history_bet_types.csv', 'text/csv')
if '_result' in bets.columns:
    st.subheader('More breakdowns')
    if 'book' in bets.columns:
        rc = bets.groupby('book')['_result'].value_counts().unstack(fill_value=0)
        for col in ['WIN', 'LOSE', 'PUSH']:
            if col not in rc.columns:
                rc[col] = 0
        bk = bets.groupby('book')['_profit_per_$1'].agg(['sum', 'mean'])
        book_tbl = pd.concat([bets.groupby('book').size().rename('bets'), rc['WIN'].rename('wins'), rc['LOSE'].rename('losses'), rc['PUSH'].rename('pushes'), bk['sum'].rename('profit'), bk['mean'].rename('roi_per_bet')], axis=1).reset_index().sort_values('profit', ascending=False)
        st.caption('By sportsbook')
        st.dataframe(book_tbl, hide_index=True, width='stretch')

    def _bucket_series(df):
        df = df.copy()
        df['market_norm'] = _market_norm(df.get('market', ''))
        ln = pd.to_numeric(df.get('line', df.get('spread', df.get('total'))), errors='coerce')
        out = pd.Series(['other'] * len(df), index=df.index)
        is_sp = df['market_norm'].eq('SPREADS')
        is_to = df['market_norm'].eq('TOTALS')
        out[is_sp] = pd.cut(ln[is_sp], bins=[-40, -14.5, -7.5, -3.5, -0.5, 0.5, 3.5, 7.5, 14.5, 40], labels=['≤-15', '-15..-8', '-7.5..-4', '-3.5..-1', 'PK', '1..3.5', '4..7.5', '8..14.5', '≥15'], include_lowest=True).astype('string')
        out[is_to] = pd.cut(ln[is_to], bins=[0, 35, 41, 45, 49, 53, 57, 65, 100], labels=['<35', '35-41', '41-45', '45-49', '49-53', '53-57', '57-65', '>65'], include_lowest=True).astype('string')
        return out.astype('string')
    bets['_line_bucket'] = _bucket_series(bets)
    lb = bets.groupby('_line_bucket')['_profit_per_$1'].agg(['size', 'sum', 'mean']).reset_index().rename(columns={'size': 'bets', 'sum': 'profit', 'mean': 'roi_per_bet'}).sort_values('profit', ascending=False)
    st.caption('By line bucket')
    st.dataframe(lb, hide_index=True, width='stretch')
    st.subheader('Cumulative P&L (units)')
    cand_dt = bets.get('_DateISO', bets.get('_date_iso', bets.get('date', bets.get('commence_time', ''))))
    dt = pd.to_datetime(cand_dt, errors='coerce')
    pnl = bets.assign(_dt=dt, _p=bets['_profit_per_$1'].fillna(0)).sort_values('_dt')['_p'].cumsum()
    st.line_chart(pnl, width='stretch')
buf = io.StringIO()
bets.to_csv(buf, index=False, encoding='utf-8-sig')
st.download_button('Download full Calculated Log CSV', buf.getvalue(), 'bets_log_full.csv', 'text/csv')







