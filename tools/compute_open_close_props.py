# tools/compute_open_close_props.py
from __future__ import annotations
from pathlib import Path
import os
import pandas as pd
import numpy as np

EXP = Path(os.environ.get("EDGE_EXPORTS_DIR","") or Path(__file__).resolve().parents[1] / "exports")
EXP.mkdir(parents=True, exist_ok=True)

SRC = EXP / "props_odds_all.csv"  # your rolling props snapshots

def _load() -> pd.DataFrame:
    if not SRC.exists():
        raise FileNotFoundError(f"{SRC} not found. Write props snapshots there first.")
    return pd.read_csv(SRC, low_memory=False)

def _norm(df: pd.DataFrame) -> pd.DataFrame:
    w = df.copy()
    # required: captured_at, book, player_name, stat, side, line, odds
    # helpful: game_id, team, kickoff
    # Timestamps
    w["captured_at"] = pd.to_datetime(w.get("captured_at"), errors="coerce", utc=True)
    if "kickoff" in w.columns:
        w["kickoff"] = pd.to_datetime(w["kickoff"], errors="coerce", utc=True)
    else:
        w["kickoff"] = pd.NaT
    # Numerics
    w["line"] = pd.to_numeric(w.get("line"), errors="coerce")
    w["odds"] = pd.to_numeric(w.get("odds"), errors="coerce")
    # Strings
    for c in ("book","player_name","team","stat","side","market"):
        if c in w.columns:
            w[c] = w[c].astype("string").str.strip()
    return w

def _choose_open_close(grp: pd.DataFrame, buffer_secs: int = 0) -> pd.Series:
    g = grp.sort_values("captured_at")
    g = g[(~g["odds"].isna()) | (~g["line"].isna())]
    if g.empty:
        return pd.Series({k: np.nan for k in ["open_line","open_odds","open_at","close_line","close_odds","close_at","kickoff"]})
    open_row = g.iloc[0]
    if pd.notna(g["kickoff"].iloc[0]):
        cutoff = g["kickoff"].iloc[0] - pd.Timedelta(seconds=buffer_secs)
        gc = g[g["captured_at"] <= cutoff]
        close_row = gc.iloc[-1] if len(gc) else g.iloc[-1]
    else:
        close_row = g.iloc[-1]
    return pd.Series({
        "open_line": open_row.get("line"),
        "open_odds": open_row.get("odds"),
        "open_at":   open_row.get("captured_at"),
        "close_line":close_row.get("line"),
        "close_odds":close_row.get("odds"),
        "close_at":  close_row.get("captured_at"),
        "kickoff":   open_row.get("kickoff") if pd.notna(open_row.get("kickoff")) else close_row.get("kickoff"),
    })

def main():
    raw = _load()
    w = _norm(raw)

    # minimal key set: (player, stat, side, book)
    # optionally include game_id or team if your feed has multiple instances per day
    key_cols = ["player_name","stat","side","book"]
    if "game_id" in w.columns:
        key_cols = ["game_id"] + key_cols
    elif "team" in w.columns:
        key_cols = ["team"] + key_cols

    use_cols = list(dict.fromkeys(key_cols + ["line","odds","captured_at","kickoff","market"]))
    use = w[[c for c in use_cols if c in w.columns]].copy()

    agg = (
        use.groupby(key_cols, dropna=False, as_index=False)
           .apply(_choose_open_close)
           .reset_index()
           .drop(columns=["level_0"], errors="ignore")
    )

    agg["has_open"]  = agg["open_at"].notna()
    agg["has_close"] = agg["close_at"].notna()
    agg["is_same_line"] = np.isclose(agg["open_line"], agg["close_line"], equal_nan=True)
    agg["is_same_odds"] = np.isclose(agg["open_odds"], agg["close_odds"], equal_nan=True)

    out = EXP / "props_open_close.csv"
    agg.to_csv(out, index=False)
    print(f"[write] {out} rows={len(agg)}")

if __name__ == "__main__":
    main()
