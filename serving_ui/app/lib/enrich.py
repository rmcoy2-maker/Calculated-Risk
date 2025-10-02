from __future__ import annotations
import pandas as pd

def american_to_decimal(o: float | int | str) -> float:
    try:
        o = int(o)
    except Exception:
        return float('nan')
    if o > 0:
        return 1 + o / 100
    else:
        return 1 - 100 / o

def american_to_prob(o: float | int | str) -> float:
    try:
        o = int(o)
    except Exception:
        return float('nan')
    if o > 0:
        return 100 / (o + 100)
    else:
        return -o / (-o + 100)

def add_probs_and_ev(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if 'odds' in out.columns and 'p_win' not in out.columns:
        out['p_win'] = out['odds'].map(american_to_prob)
    if 'p_win' in out.columns:
        try:
            payout = out['odds'].map(american_to_decimal)
            p = pd.to_numeric(out['p_win'], errors='coerce').clip(0, 1)
            out['_ev_per_$1'] = p * payout - (1 - p)
        except Exception:
            out['_ev_per_$1'] = None
    return out

def attach_teams(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if '_home_team' in out.columns and '_away_team' in out.columns and ('_pick_team' not in out.columns):
        out['_pick_team'] = out['_home_team']
    return out

def norm_market(m: str) -> str:
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