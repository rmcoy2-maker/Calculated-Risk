from __future__ import annotations
import pandas as pd

def missing_cols_report(df: pd.DataFrame, required: list[str]) -> list[str]:
    if df is None or df.empty:
        return required
    return [c for c in required if c not in df.columns]

def summarize_counts(edges: pd.DataFrame, live: pd.DataFrame, scores: pd.DataFrame) -> dict:
    return {'edges_rows': 0 if edges is None else len(edges), 'live_rows': 0 if live is None else len(live), 'scores_rows': 0 if scores is None else len(scores), 'edges_cols': 0 if edges is None or edges.empty else len(edges.columns), 'live_cols': 0 if live is None or live.empty else len(live.columns), 'scores_cols': 0 if scores is None or scores.empty else len(scores.columns)}

def key_overlap_report(edges: pd.DataFrame, live: pd.DataFrame) -> pd.DataFrame:
    e = edges if edges is not None else pd.DataFrame()
    l = live if live is not None else pd.DataFrame()
    if 'game_id' not in getattr(e, 'columns', []) or 'game_id' not in getattr(l, 'columns', []):
        return pd.DataFrame(columns=['in_edges_only', 'in_live_only', 'in_both'])
    e_ids = set(e['game_id'].dropna().astype(str))
    l_ids = set(l['game_id'].dropna().astype(str))
    return pd.DataFrame([{'in_edges_only': len(e_ids - l_ids), 'in_live_only': len(l_ids - e_ids), 'in_both': len(e_ids & l_ids)}])

def quick_healthcheck(edges: pd.DataFrame, live: pd.DataFrame, scores: pd.DataFrame) -> dict:
    out = summarize_counts(edges, live, scores)
    out['edges_has_probs'] = bool(edges is not None and 'p_win' in edges.columns and edges['p_win'].notna().any())
    out['edges_has_odds'] = bool(edges is not None and 'odds' in edges.columns and edges['odds'].notna().any())
    out['live_has_odds'] = bool(live is not None and 'odds' in live.columns and live['odds'].notna().any())
    out['scores_has_scores'] = bool(scores is not None and {'home_score', 'away_score'} <= set(scores.columns))
    return out