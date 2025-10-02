from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

def _read_csv_safe(p: Path) -> pd.DataFrame:
    try:
        if p.exists() and p.stat().st_size > 5:
            return pd.read_csv(p)
    except Exception:
        pass
    return pd.DataFrame()

def _normalize_bets(df: pd.DataFrame, source: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns={c: c.lower() for c in df.columns})
    for c in ['placed_at', 'settled_at', 'stake', 'payout', 'status', 'origin', 'sport', 'market', 'league', 'result']:
        if c not in df.columns:
            df[c] = None
    for c in ['placed_at', 'settled_at']:
        df[c] = pd.to_datetime(df[c], errors='coerce')
    for c in ['stake', 'payout', 'odds', 'line', 'p_win']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    if 'stake' in df.columns:
        df['stake'] = df['stake'].fillna(0.0)
    if 'profit' not in df.columns:
        profit = np.where(df['payout'].notna(), df['payout'] - df['stake'], np.nan)
        if 'result' in df.columns:
            res = df['result'].astype(str).str.lower()
            profit = np.where(profit.notna(), profit, np.where(res.eq('win'), df['stake'], np.where(res.eq('push'), 0.0, np.where(res.eq('loss'), -df['stake'], np.nan))))
        df['profit'] = pd.to_numeric(profit, errors='coerce')
    df['source'] = source
    return df

def load_bankroll_base(EXPORTS: Path) -> pd.DataFrame:
    """
    Reads bets/parlays/edges if present and returns a unified frame.
    Priority: bets_log.csv + parlays.csv; fallback to edges.csv as "suggested".
    """
    df_list = []
    bl = _read_csv_safe(EXPORTS / 'bets_log.csv')
    if not bl.empty:
        df_list.append(_normalize_bets(bl, 'bets_log'))
    pl = _read_csv_safe(EXPORTS / 'parlays.csv')
    if not pl.empty:
        df_list.append(_normalize_bets(pl, 'parlays'))
    if not df_list:
        eg = _read_csv_safe(EXPORTS / 'edges.csv')
        if not eg.empty:
            eg = eg.rename(columns={c: c.lower() for c in eg.columns})
            keep = ['ts', 'sport', 'league', 'game_id', 'market', 'ref', 'side', 'line', 'odds', 'p_win']
            for c in keep:
                if c not in eg.columns:
                    eg[c] = None
            eg['placed_at'] = pd.to_datetime(eg.get('ts'), errors='coerce')
            eg['stake'] = 0.0
            eg['payout'] = np.nan
            eg['status'] = 'open'
            eg['origin'] = 'suggested'
            eg['profit'] = np.nan
            df_list.append(eg[['placed_at', 'stake', 'payout', 'status', 'origin', 'sport', 'market', 'league', 'profit']])
    base = pd.concat([d for d in df_list if d is not None and (not d.empty)], ignore_index=True) if df_list else pd.DataFrame()
    if base.empty:
        return base
    base['date'] = pd.to_datetime(base['placed_at'], errors='coerce').dt.date
    base['year'] = pd.to_datetime(base['placed_at'], errors='coerce').dt.isocalendar().year if base['placed_at'].notna().any() else np.nan
    base['week'] = pd.to_datetime(base['placed_at'], errors='coerce').dt.isocalendar().week if base['placed_at'].notna().any() else np.nan
    return base

def weekly_roi_closed(df: pd.DataFrame) -> pd.DataFrame:
    """
    ROI on settled bets per ISO week = sum(profit)/sum(stake) for status in ['won','lost','push','settled'].
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=['year', 'week', 'stake', 'profit', 'roi'])
    status = df.get('status', pd.Series(dtype=object)).astype(str).str.lower()
    closed = df[status.isin(['won', 'lost', 'push', 'settled', 'closed', 'graded'])]
    if closed.empty:
        return pd.DataFrame(columns=['year', 'week', 'stake', 'profit', 'roi'])
    g = closed.groupby(['year', 'week'], dropna=True, as_index=False).agg(stake=('stake', 'sum'), profit=('profit', 'sum'))
    g['roi'] = np.where(g['stake'] > 0, g['profit'] / g['stake'], np.nan)
    return g.sort_values(['year', 'week'])

def weekly_roi_by_origin(df: pd.DataFrame) -> pd.DataFrame:
    """
    ROI per week per origin (e.g., manual vs suggested).
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=['origin', 'year', 'week', 'stake', 'profit', 'roi'])
    status = df.get('status', pd.Series(dtype=object)).astype(str).str.lower()
    closed = df[status.isin(['won', 'lost', 'push', 'settled', 'closed', 'graded'])]
    if closed.empty:
        return pd.DataFrame(columns=['origin', 'year', 'week', 'stake', 'profit', 'roi'])
    g = closed.groupby(['origin', 'year', 'week'], dropna=True, as_index=False).agg(stake=('stake', 'sum'), profit=('profit', 'sum'))
    g['roi'] = np.where(g['stake'] > 0, g['profit'] / g['stake'], np.nan)
    return g.sort_values(['origin', 'year', 'week'])

def cumulative_bankroll(df: pd.DataFrame, starting_bankroll: float=1000.0) -> pd.DataFrame:
    """
    Cumulative bankroll over time using settled bets in chronological order.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=['placed_at', 'bankroll'])
    status = df.get('status', pd.Series(dtype=object)).astype(str).str.lower()
    closed = df[status.isin(['won', 'lost', 'push', 'settled', 'closed', 'graded'])].copy()
    if closed.empty:
        return pd.DataFrame(columns=['placed_at', 'bankroll'])
    closed = closed.sort_values('placed_at')
    bk = [starting_bankroll]
    for prof in closed['profit'].fillna(0.0).tolist():
        bk.append(bk[-1] + prof)
    out = pd.DataFrame({'placed_at': pd.to_datetime(closed['placed_at'], errors='coerce'), 'bankroll': bk[1:]})
    return out

def roi_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Overall ROI by market and sport for quick tables.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=['market', 'sport', 'bets', 'stake', 'profit', 'roi'])
    status = df.get('status', pd.Series(dtype=object)).astype(str).str.lower()
    closed = df[status.isin(['won', 'lost', 'push', 'settled', 'closed', 'graded'])].copy()
    if closed.empty:
        return pd.DataFrame(columns=['market', 'sport', 'bets', 'stake', 'profit', 'roi'])
    grp = closed.groupby(['market', 'sport'], dropna=False).agg(bets=('stake', 'count'), stake=('stake', 'sum'), profit=('profit', 'sum')).reset_index()
    grp['roi'] = np.where(grp['stake'] > 0, grp['profit'] / grp['stake'], np.nan)
    return grp.sort_values(['roi', 'bets'], ascending=[False, False])