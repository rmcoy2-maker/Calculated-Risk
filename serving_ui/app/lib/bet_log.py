from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
EXPORTS = ROOT / 'exports'

def _read_csv_safe(p):
    try:
        return pd.read_csv(p)
    except Exception:
        return pd.DataFrame()

def _normalize_bets(df: pd.DataFrame, src: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.rename(columns={c: c.lower() for c in df.columns}, inplace=True)
    keep = ['ts', 'sport', 'league', 'game_id', 'market', 'ref', 'side', 'line', 'odds', 'p_win', 'ev', 'stake', 'status', 'result', 'pnl', 'tag']
    for c in keep:
        if c not in df.columns:
            df[c] = None
    df['odds'] = pd.to_numeric(df['odds'], errors='coerce')
    df['p_win'] = pd.to_numeric(df['p_win'], errors='coerce')
    df['ev'] = pd.to_numeric(df['ev'], errors='coerce')
    df['stake'] = pd.to_numeric(df['stake'], errors='coerce')
    df['source'] = src
    return df[keep + ['source']]

def read_log(use_logs: bool=True) -> pd.DataFrame:
    """
    Load a unified Calculated Log DataFrame for the Dashboard page.

    If use_logs=True, read bets/parlays; otherwise fall back to edges.csv as a pseudo-log.
    """
    bl = _read_csv_safe(EXPORTS / 'bets_log.csv')
    pl = _read_csv_safe(EXPORTS / 'parlays.csv')
    if use_logs and (not bl.empty or not pl.empty):
        parts = []
        if not bl.empty:
            parts.append(_normalize_bets(bl, 'bets_log'))
        if not pl.empty:
            parts.append(_normalize_bets(pl, 'parlays'))
        base = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    else:
        eg = _read_csv_safe(EXPORTS / 'edges.csv')
        if eg.empty:
            return pd.DataFrame(columns=['ts', 'market', 'ref', 'side', 'line', 'odds', 'p_win', 'ev', 'stake', 'status', 'result', 'pnl', 'tag', 'source'])
        eg = eg.copy()
        eg.rename(columns={c: c.lower() for c in eg.columns}, inplace=True)
        keep = ['ts', 'sport', 'league', 'game_id', 'market', 'ref', 'side', 'line', 'odds', 'p_win', 'ev']
        for c in keep:
            if c not in eg.columns:
                eg[c] = None
        eg['stake'] = 0.0
        eg['status'] = 'model-suggested'
        eg['result'] = None
        eg['pnl'] = None
        eg['tag'] = 'edges_preview'
        base = _normalize_bets(eg, 'edges')
    if not base.empty:
        if 'ts' in base.columns:
            base['ts'] = pd.to_datetime(base['ts'], errors='coerce')
            base = base.sort_values(['ts'], ascending=[False])
        base.reset_index(drop=True, inplace=True)
    return base
