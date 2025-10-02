# tools/compute_open_close.py
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import os
import pandas as pd
import numpy as np

EXP = Path(os.environ.get("EDGE_EXPORTS_DIR","") or Path(__file__).resolve().parents[1] / "exports")
EXP.mkdir(parents=True, exist_ok=True)

CANDIDATES = [
    EXP / "odds_lines_all.csv",
    EXP / "odds_all.csv",
    EXP / "odds.csv",
]

def _load_first(paths):
    for p in paths:
        if p.exists():
            return pd.read_csv(p, low_memory=False)
    raise FileNotFoundError("No odds CSV found in exports/ (looked for odds_lines_all.csv, odds_all.csv, odds.csv)")

def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    w = df.copy()
    # standardize column names if variants exist
    if "market_norm" in w and "market" not in w: w["market"] = w["market_norm"]
    if "side_norm"   in w and "side"   not in w: w["side"]   = w["side_norm"]
    if "price" in w and "odds" not in w:          w["odds"]   = w["price"]
    if "decimal" in w and "decimal_odds" not in w: w["decimal_odds"] = w["decimal"]

    # parse timestamps
    for c in ("captured_at", "_captured_at", "asof_ts"):
        if c in w.columns:
            w["captured_at"] = pd.to_datetime(w[c], errors="coerce", utc=True)
            break
    if "captured_at" not in w:
        # fallback: derive from file mtime (worse than ideal). Strongly recommend capturing a real timestamp in pulls.
        w["captured_at"] = pd.Timestamp.utcnow()

    if "commence_time" in w.columns:
        w["kickoff"] = pd.to_datetime(w["commence_time"], errors="coerce", utc=True)
    elif "_date_iso" in w.columns:
        w["kickoff"] = pd.to_datetime(w["_date_iso"], errors="coerce", utc=True)
    else:
        w["kickoff"] = pd.NaT

    # prefer explicit game_id; else synthesize
    if "game_id" not in w.columns:
        away = w.get("_away_nick", w.get("away","")).astype(str).str.upper().str.replace(r"\s+","_", regex=True)
        home = w.get("_home_nick", w.get("home","")).astype(str).str.upper().str.replace(r"\s+","_", regex=True)
        date = pd.to_datetime(w.get("_date_iso", w.get("kickoff")), errors="coerce", utc=True).dt.date.astype("string")
        w["game_id"] = date + "::" + away + "@" + home

    return w

def _choose_open_close(grp: pd.DataFrame, buffer_secs: int = 0) -> pd.Series:
    # Opening = earliest snapshot for this book/market/side/game with non-null line/odds
    g = grp.sort_values("captured_at")
    g = g[(~g["odds"].isna()) | (~g["line"].isna())]

    # Closing = latest snapshot BEFORE kickoff - buffer
    cutoff = None
    if pd.notna(g["kickoff"].iloc[0]):
        cutoff = g["kickoff"].iloc[0] - pd.Timedelta(seconds=buffer_secs)

    open_row = g.iloc[0] if len(g) else pd.Series(dtype=object)
    if cutoff is not None:
        gc = g[g["captured_at"] <= cutoff]
        close_row = gc.iloc[-1] if len(gc) else (g.iloc[-1] if len(g) else pd.Series(dtype=object))
    else:
        close_row = g.iloc[-1] if len(g) else pd.Series(dtype=object)

    def pick(row, col):
        return row[col] if (col in row and pd.notna(row[col])) else np.nan

    return pd.Series({
        "open_line": pick(open_row, "line"),
        "open_odds": pick(open_row, "odds"),
        "open_at":   pick(open_row, "captured_at"),
        "close_line":pick(close_row,"line"),
        "close_odds":pick(close_row,"odds"),
        "close_at":  pick(close_row,"captured_at"),
        "kickoff":   pick(open_row, "kickoff") or pick(close_row, "kickoff"),
    })

def main():
    odds = _norm_cols(_load_first(CANDIDATES))
    # focus on core fields
    use = odds[[
        "game_id","book","market","side","line","odds","captured_at","kickoff"
    ]].copy()

    # safe dtypes
    use["line"] = pd.to_numeric(use["line"], errors="coerce")
    use["odds"] = pd.to_numeric(use["odds"], errors="coerce")

    # group by game/book/market[/side]
    key_cols = ["game_id","book","market","side"]
    agg = use.groupby(key_cols, as_index=False).apply(_choose_open_close).reset_index(drop=True)

    # add flags
    agg["has_open"]  = agg["open_at" ].notna()
    agg["has_close"] = agg["close_at"].notna()
    agg["is_same_line"]  = np.isclose(agg["open_line"], agg["close_line"], equal_nan=True)
    agg["is_same_odds"]  = np.isclose(agg["open_odds"], agg["close_odds"], equal_nan=True)

    out = EXP / "lines_open_close.csv"
    agg.to_csv(out, index=False)
    print(f"[write] {out} rows={len(agg)}")

if __name__ == "__main__":
    main()
