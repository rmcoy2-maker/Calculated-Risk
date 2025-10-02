from __future__ import annotations
from pathlib import Path
import pandas as pd
CANDIDATES = [Path('exports/lines_live_normalized.csv'), Path('exports/lines_live_fixed.csv'), Path('exports/lines_live.csv')]

def load_lines_live() -> pd.DataFrame:
    """
    Load live lines with a safe fallback order and light hygiene.
    Ensures key string cols are trimmed and numeric cols coerced.
    Adds implied_prob when decimal is present but implied_prob missing.
    """
    for p in CANDIDATES:
        if p.exists():
            df = pd.read_csv(p, low_memory=False)
            break
    else:
        return pd.DataFrame()
    str_cols = ['_date_iso', '_home_nick', '_away_nick', 'book', '_market_norm', 'side', 'side_norm']
    for c in str_cols:
        if c in df.columns:
            df[c] = df[c].astype('string').fillna('').str.strip()
    for c in ('decimal', 'line'):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    if 'decimal' in df.columns:
        if 'implied_prob' not in df.columns:
            df['implied_prob'] = 1.0 / df['decimal']
        else:
            df['implied_prob'] = pd.to_numeric(df['implied_prob'], errors='coerce')
            needs = df['implied_prob'].isna() & df['decimal'].gt(1)
            df.loc[needs, 'implied_prob'] = 1.0 / df.loc[needs, 'decimal']
    return df