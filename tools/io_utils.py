from __future__ import annotations
import pandas as pd

# Map of messy codes => normalized codes
TEAM_MAP = {
    "GNB":"GB","GBP":"GB","GB":"GB",
    "SFO":"SF","SF":"SF",
    "JAC":"JAX","JAX":"JAX",
    "SD":"LAC","LAC":"LAC","LAR":"LAR","LA":"LA",  # "LA" is ambiguous; avoid if possible
    "ARZ":"ARI","ARI":"ARI",
    "WSH":"WAS","WAS":"WAS",
    # add more as needed…
}

def norm_team(x: str) -> str | None:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip().upper()
    return TEAM_MAP.get(s, s)

def read_csv(path, **kw):
    # Read everything as string; we'll coerce explicitly later
    df = pd.read_csv(
        path, dtype=str, keep_default_na=False,
        na_values=["", "NA", "NaN", "None", "null"],
        low_memory=False, **kw
    )
    # Trim whitespace
    df = df.applymap(lambda v: v.strip() if isinstance(v, str) else v)
    return df

def to_int(s: pd.Series):
    # Portable: no pandas nullable Int64 dtype
    return pd.to_numeric(s, errors="coerce")

def to_float(s: pd.Series):
    return pd.to_numeric(s, errors="coerce")

