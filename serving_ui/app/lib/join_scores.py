import pandas as pd

def attach_scores(edges: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    """
    Join scores to edges using a multi-pass strategy:
      Pass A: _date_iso + exact home/away nicks
      Pass B: Season+Week + exact home/away nicks
      Pass C: _date_iso + swapped nicks (cover book-team vs scores-team orientation)
      Pass D: Season+Week + swapped nicks
    Sets:
      HomeScore, AwayScore, _joined_with_scores (bool), _join_method (str)
    Leaves original rows intact and only fills missing scores.
    """
    e = edges.copy()
    s = scores.copy()
    for c in ('_date_iso', 'Season', 'Week', '_home_nick', '_away_nick'):
        if c not in e.columns:
            e[c] = ''
        if c not in s.columns:
            s[c] = ''
    s_keep = s[['_date_iso', 'Season', 'Week', '_home_nick', '_away_nick', 'HomeScore', 'AwayScore']].drop_duplicates()

    def _apply_pass(merged, how_cols, tag):
        tmp = merged.merge(s_keep.rename(columns={'_home_nick': '_home_nick_sc', '_away_nick': '_away_nick_sc'}), left_on=how_cols, right_on=[c.replace('_home_nick', '_home_nick_sc').replace('_away_nick', '_away_nick_sc') for c in how_cols], how='left', suffixes=('', '_sc'))
        need = tmp['HomeScore'].isna() & tmp['AwayScore'].isna()
        can = tmp['HomeScore_sc'].notna() | tmp['AwayScore_sc'].notna()
        fill_mask = need & can
        tmp.loc[fill_mask, 'HomeScore'] = tmp.loc[fill_mask, 'HomeScore_sc']
        tmp.loc[fill_mask, 'AwayScore'] = tmp.loc[fill_mask, 'AwayScore_sc']
        tmp.loc[fill_mask, '_join_method'] = tag
        tmp.drop(columns=[c for c in tmp.columns if c.endswith('_sc')], inplace=True)
        return tmp
    if 'HomeScore' not in e.columns:
        e['HomeScore'] = pd.NA
    if 'AwayScore' not in e.columns:
        e['AwayScore'] = pd.NA
    e['_join_method'] = e.get('_join_method', '')
    e = _apply_pass(e, ['_date_iso', '_home_nick', '_away_nick'], 'date+exact')
    e = _apply_pass(e, ['Season', 'Week', '_home_nick', '_away_nick'], 'sw+exact')
    e_sw = e.rename(columns={'_home_nick': '_away_nick', '_away_nick': '_home_nick'}).copy()
    e_sw['__orig_index__'] = e_sw.index
    e_sw = _apply_pass(e_sw, ['_date_iso', '_home_nick', '_away_nick'], 'date+swap')
    filled = e_sw['HomeScore'].notna() | e_sw['AwayScore'].notna()
    e.loc[e_sw.loc[filled, '__orig_index__'], ['HomeScore', 'AwayScore', '_join_method']] = e_sw.loc[filled, ['HomeScore', 'AwayScore', '_join_method']].values
    e_sw = e.rename(columns={'_home_nick': '_away_nick', '_away_nick': '_home_nick'}).copy()
    e_sw['__orig_index__'] = e_sw.index
    e_sw = _apply_pass(e_sw, ['Season', 'Week', '_home_nick', '_away_nick'], 'sw+swap')
    filled = e_sw['HomeScore'].notna() | e_sw['AwayScore'].notna()
    e.loc[e_sw.loc[filled, '__orig_index__'], ['HomeScore', 'AwayScore', '_join_method']] = e_sw.loc[filled, ['HomeScore', 'AwayScore', '_join_method']].values
    e['_joined_with_scores'] = e['HomeScore'].notna() & e['AwayScore'].notna()
    return e