from __future__ import annotations
import pandas as pd
import numpy as np

def _as_str_key(series):
    if series is None:
        return pd.Series(dtype='string')
    return pd.Series(series, copy=False).astype('string').fillna('').str.strip()

def american_to_decimal(o):
    try:
        o = int(o)
    except Exception:
        return np.nan
    return 1 + o / 100 if o > 0 else 1 - 100 / o

def _canon_team(x: str) -> str:
    if not isinstance(x, str):
        return ''
    return x.strip().upper().replace(' ', '_')

def _mk_game_id(row):
    d = str(row.get('_DateISO') or row.get('date') or '')[:10]
    h = _canon_team(row.get('_home_team') or row.get('home_team'))
    a = _canon_team(row.get('_away_team') or row.get('away_team'))
    return f'{d}_{a}_AT_{h}' if d and h and a else ''

def _norm_market(m: str) -> str:
    if not isinstance(m, str):
        return ''
    m = m.strip().lower()
    if m in ('h2h', 'ml', 'moneyline', 'money line'):
        return 'H2H'
    if m in ('spread', 'spreads', 'point spread'):
        return 'SPREADS'
    if m in ('total', 'totals', 'over/under', 'ou'):
        return 'TOTALS'
    return m.upper()

def _get(df, *names):
    if df is None:
        return None
    cols = {c.lower(): c for c in df.columns}
    for n in names:
        c = cols.get(n.lower())
        if c is not None:
            return df[c]
    return None

def _win_flags(scores: pd.DataFrame) -> pd.DataFrame:
    s = scores.copy()
    hs = pd.to_numeric(s.get('home_score'), errors='coerce')
    as_ = pd.to_numeric(s.get('away_score'), errors='coerce')
    s['home_score'] = hs
    s['away_score'] = as_
    s['home_win'] = (hs > as_).fillna(False).astype(int)
    s['away_win'] = (as_ > hs).fillna(False).astype(int)
    return s

def normalize_edges_for_settlement(edges: pd.DataFrame, lines_live: pd.DataFrame | None=None) -> pd.DataFrame:
    if edges is None or edges.empty:
        return pd.DataFrame(columns=['game_id', 'market', 'side', 'line', 'odds', '_home_team', '_away_team', '_DateISO'])
    df = edges.copy()
    if 'game_id' not in df.columns or df['game_id'].isna().all():
        df['game_id'] = df.apply(_mk_game_id, axis=1)
    df['game_id'] = _as_str_key(df['game_id'])
    if 'market' in df.columns:
        df['market'] = df['market'].map(_norm_market)
    if lines_live is not None and (not lines_live.empty):
        live = lines_live.copy()
        if 'market' in live.columns:
            live['market'] = live['market'].map(_norm_market)
        for col in ('game_id', 'market', 'side'):
            if col in live.columns:
                live[col] = _as_str_key(live[col])
        for col in ('game_id', 'market', 'side'):
            if col in df.columns:
                df[col] = _as_str_key(df[col])
        key_cols = [c for c in ['game_id', 'market', 'side'] if c in df.columns and c in live.columns]
        if key_cols:
            keep = key_cols + [c for c in ['line', 'odds', 'book'] if c in live.columns]
            live_small = live[keep].drop_duplicates()
            df = df.merge(live_small, on=key_cols, how='left', suffixes=('', '_live'))
            if 'line' not in df.columns and 'line_live' in df.columns:
                df['line'] = df['line_live']
            for c in list(df.columns):
                if c.endswith('_live'):
                    df.drop(columns=c, inplace=True, errors='ignore')
    return df

def settle_bets(edges: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    if edges is None or edges.empty:
        return pd.DataFrame()
    if scores is None or scores.empty:
        out = edges.copy()
        out['_result'] = ''
        out['_payout_per_$1'] = np.nan
        return out
    e = edges.copy()
    s = _win_flags(scores.copy())
    if 'game_id' not in e.columns or e['game_id'].isna().all():
        e['game_id'] = e.apply(_mk_game_id, axis=1)
    e['game_id'] = _as_str_key(e['game_id'])
    if 'game_id' not in s.columns or s['game_id'].isna().all():
        s['game_id'] = s.apply(lambda r: _mk_game_id({'_DateISO': r.get('Date') or r.get('_DateISO'), '_home_team': r.get('home_team'), '_away_team': r.get('away_team')}), axis=1)
    s['game_id'] = _as_str_key(s['game_id'])
    use_cols = [c for c in ['game_id', 'home_team', 'away_team', 'home_score', 'away_score', 'home_win', 'away_win'] if c in s.columns]
    j = e.merge(s[use_cols], on='game_id', how='left')
    if 'home_score' not in j.columns or 'away_score' not in j.columns or (j['home_score'].isna() & j['away_score'].isna()).all():
        e_home = _get(e, '_home_team', 'home_team')
        e_away = _get(e, '_away_team', 'away_team')
        e_season = _get(e, 'Season', 'season')
        e_tmp = e.copy()
        e_tmp['_H'] = e_home.map(_canon_team) if e_home is not None else ''
        e_tmp['_A'] = e_away.map(_canon_team) if e_away is not None else ''
        e_tmp['_S'] = pd.to_numeric(e_season, errors='coerce') if e_season is not None else pd.Series(np.nan, index=e_tmp.index)
        s_home = _get(s, 'home_team', '_home_team', 'HomeTeam')
        s_away = _get(s, 'away_team', '_away_team', 'AwayTeam')
        s_season = _get(s, 'Season', 'season')
        s_tmp = s.copy()
        s_tmp['_H'] = s_home.map(_canon_team) if s_home is not None else ''
        s_tmp['_A'] = s_away.map(_canon_team) if s_away is not None else ''
        s_tmp['_S'] = pd.to_numeric(s_season, errors='coerce') if s_season is not None else pd.Series(np.nan, index=s_tmp.index)
        s_keep = [c for c in ['_S', '_H', '_A', 'home_team', 'away_team', 'home_score', 'away_score', 'home_win', 'away_win'] if c in s_tmp.columns]
        j2 = e_tmp.merge(s_tmp[s_keep], on=['_S', '_H', '_A'], how='left')
        for c in ['home_team', 'away_team', 'home_score', 'away_score', 'home_win', 'away_win']:
            if c in j2.columns:
                if c not in j.columns:
                    j[c] = pd.NA
                miss = j[c].isna()
                j.loc[miss, c] = j2.loc[miss, c]
    if 'market' in j.columns:
        j['market'] = j['market'].map(_norm_market)
    j['home_score'] = pd.to_numeric(j.get('home_score'), errors='coerce')
    j['away_score'] = pd.to_numeric(j.get('away_score'), errors='coerce')
    has_scores = j['home_score'].notna() & j['away_score'].notna()
    line = pd.to_numeric(j.get('line'), errors='coerce') if 'line' in j.columns else pd.Series(np.nan, index=j.index)
    odds = pd.to_numeric(j.get('odds'), errors='coerce') if 'odds' in j.columns else pd.Series(np.nan, index=j.index)
    dec = odds.map(american_to_decimal) if odds is not None else pd.Series(np.nan, index=j.index)
    home = j.get('_home_team') if '_home_team' in j.columns else j.get('home_team')
    away = j.get('_away_team') if '_away_team' in j.columns else j.get('away_team')
    side = j.get('side')
    pick = j.get('_pick_team')
    if side is not None:
        _su = side.astype(str).str.upper().str.strip()
        _hu = home.astype(str).str.upper().str.strip()
        _au = away.astype(str).str.upper().str.strip()
        pick_from_side = np.where(_su.eq(_hu), home, np.where(_su.eq(_au), away, None))
        if pick is None:
            j['_pick_team'] = pick_from_side
            pick = j['_pick_team']
        else:
            j['_pick_team'] = pick.fillna(pd.Series(pick_from_side, index=j.index))
            pick = j['_pick_team']
    j['_result'] = ''
    m = j['market'].eq('H2H') & has_scores & pick.notna()
    if m.any():
        is_home_pick = pick.loc[m].astype(str).str.upper().str.strip().eq(j.loc[m, 'home_team'].astype(str).str.upper().str.strip()).fillna(False)
        hw = j.loc[m, 'home_win'].fillna(0).astype(int).eq(1)
        aw = j.loc[m, 'away_win'].fillna(0).astype(int).eq(1)
        j.loc[m, '_result'] = np.where(is_home_pick & hw, 'win', np.where(~is_home_pick & aw, 'win', 'loss'))
    m = j['market'].eq('SPREADS') & has_scores & line.notna()
    if m.any():
        margin = j.loc[m, 'home_score'] - j.loc[m, 'away_score']
        home_spread = -line.loc[m]
        home_cover = (margin > home_spread).fillna(False)
        push_spread = (margin == home_spread).fillna(False)
        is_home_pick = pick.loc[m].astype(str).str.upper().str.strip().eq(home.loc[m].astype(str).str.upper().str.strip()).fillna(False)
        j.loc[m, '_result'] = np.where(push_spread, 'push', np.where(is_home_pick, np.where(home_cover, 'win', 'loss'), np.where(~home_cover, 'win', 'loss')))
    m = j['market'].eq('TOTALS') & has_scores & line.notna()
    if m.any():
        total = j.loc[m, 'home_score'] + j.loc[m, 'away_score']
        tot_line = line.loc[m]
        is_over = side.loc[m].astype(str).str.upper().eq('OVER').fillna(False) if side is not None else pd.Series(False, index=j.index)
        is_under = side.loc[m].astype(str).str.upper().eq('UNDER').fillna(False) if side is not None else pd.Series(False, index=j.index)
        push_tot = (total == tot_line).fillna(False)
        j.loc[m, '_result'] = np.where(push_tot, 'push', np.where(is_over, np.where(total > tot_line, 'win', 'loss'), np.where(is_under, np.where(total < tot_line, 'win', 'loss'), '')))
    j['_payout_per_$1'] = np.where(j['_result'].eq('win'), dec, np.where(j['_result'].eq('push'), 1.0, 0.0))
    return j