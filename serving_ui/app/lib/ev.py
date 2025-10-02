from __future__ import annotations
import numpy as np
import pandas as pd

def _dec_to_american(x: float) -> float | np.nan:
    """
    Convert decimal odds to American odds for display.
    Returns NaN if invalid.
    """
    if pd.isna(x) or x <= 1:
        return np.nan
    return int(round((x - 1) * 100)) if x >= 2 else -int(round(100 / (x - 1)))

def add_ev_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds EV-friendly columns:
      - implied_prob : if missing, computed as 1/decimal
      - imp_prob     : alias of implied_prob (legacy convenience)
      - fair_dec     : 1 / imp_prob
      - fair_american: decimal -> American conversion of fair price
    """
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    d = df.copy()
    if 'decimal' in d.columns:
        d['decimal'] = pd.to_numeric(d['decimal'], errors='coerce')
    if 'implied_prob' not in d.columns and 'decimal' in d.columns:
        d['implied_prob'] = 1.0 / d['decimal']
    elif 'implied_prob' in d.columns:
        d['implied_prob'] = pd.to_numeric(d['implied_prob'], errors='coerce')
        if 'decimal' in d.columns:
            needs = d['implied_prob'].isna() & d['decimal'].gt(1)
            d.loc[needs, 'implied_prob'] = 1.0 / d.loc[needs, 'decimal']
    if 'implied_prob' in d.columns:
        d['imp_prob'] = d['implied_prob']
        with np.errstate(divide='ignore', invalid='ignore'):
            d['fair_dec'] = 1.0 / d['imp_prob']
        d['fair_american'] = d['fair_dec'].map(_dec_to_american)
    else:
        d['imp_prob'] = np.nan
        d['fair_dec'] = np.nan
        d['fair_american'] = np.nan
    return d