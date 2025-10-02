# tools/_io.py
from __future__ import annotations
import pandas as pd, pathlib as P

TEAM_MAP = {
    "GNB":"GB","GBP":"GB","GB":"GB",
    "SFO":"SF","SF":"SF",
    "JAC":"JAX","JAX":"JAX",
    "SD":"LAC","LAC":"LAC","LAR":"LAR","LA":"LA",  # 'LA' is ambiguous, try to avoid
    "ARZ":"ARI","ARI":"ARI",
    # add as needed…
}

def norm_team(x: str) -> str | None:
    if pd.isna(x): return None
    s = str(x).strip().upper()
    return TEAM_MAP.get(s, s)

def read_csv(path, **kw):
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=["", "NA", "NaN"], **kw)
    # trim whitespace everywhere
    df = df.applymap(lambda v: v.strip() if isinstance(v, str) else v)
    return df

def to_int(s: pd.Series):
    return pd.to_numeric(s, errors="coerce").astype("Int64")

def to_float(s: pd.Series):
    return pd.to_numeric(s, errors="coerce")

