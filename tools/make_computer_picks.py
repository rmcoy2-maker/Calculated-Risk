# tools/make_computer_picks.py
# Build computer-made picks from odds_history (+ edges if present), normalized to settle cleanly.

from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EDGES_PATH = ROOT / "exports" / "edges_graded_full_normalized_std.csv"
ODDS_PATH  = ROOT / "exports" / "odds_history.csv"
OUT_PATH   = ROOT / "exports" / "computer_picks.csv"

# Team alias normalizer (extend as needed to match your scores file)
ALIAS = {
    "REDSKINS":"COMMANDERS","WASHINGTON":"COMMANDERS","FOOTBALL":"COMMANDERS",
    "OAKLAND":"RAIDERS","LV":"RAIDERS","LAS":"RAIDERS","VEGAS":"RAIDERS",
    "SAN DIEGO":"CHARGERS","SD":"CHARGERS",
    "ST LOUIS":"RAMS","ST. LOUIS":"RAMS",
}

def _s(s: pd.Series) -> pd.Series:
    return s.astype("string").fillna("")

def _nick(s: pd.Series) -> pd.Series:
    s = _s(s).str.upper()
    s = s.replace(ALIAS)
    s = s.str.replace(r"[^A-Z0-9 ]+","", regex=True).str.strip()
    return s.str.replace(r"\s+","_", regex=True)

def load_edges(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    e = pd.read_csv(path)
    for h in ("_home_nick","home","home_team","home_name"):
        if h in e.columns: e["_home_nick"] = _nick(e[h]); break
    for a in ("_away_nick","away","away_team","away_name"):
        if a in e.columns: e["_away_nick"] = _nick(e[a]); break
    if "p_win" not in e.columns:
        for c in ("prob","p_model","prob_win","win_prob"):
            if c in e.columns:
                e["p_win"] = pd.to_numeric(e[c], errors="coerce")
                break
    e["_date_iso"] = _s(e.get("_date_iso", e.get("date","")))
    # If market/side aren’t in edges, leave them NaN; we’ll rely on odds rows.
    return e

def load_odds(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing odds file: {path}")
    o = pd.read_csv(path)
    o["_date_iso"]   = _s(o.get("_date_iso",""))
    o["market_norm"] = _s(o.get("market_norm","")).str.upper()
    o["side_norm"]   = _s(o.get("side_norm","")).str.upper()
    o["book"]        = _s(o.get("book",""))
    o["line"]        = pd.to_numeric(o.get("line", np.nan), errors="coerce")
    o["odds"]        = pd.to_numeric(o.get("odds", np.nan), errors="coerce")
    # Nicks from home/away
    for h in ("_home_nick","home","home_team","home_name"):
        if h in o.columns: o["_home_nick"] = _nick(o[h]); break
    for a in ("_away_nick","away","away_team","away_name"):
        if a in o.columns: o["_away_nick"] = _nick(o[a]); break
    # Keep only the 3 featured markets Backtest settles
    o = o[o["market_norm"].isin(["H2H","SPREADS","TOTALS"])].copy()
    # Require minimum fields
    req = ["_date_iso","_home_nick","_away_nick","market_norm","side_norm","odds"]
    o = o.dropna(subset=[c for c in req if c != "line"])  # line may be NaN for H2H
    return o

def join_edges(best: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    if edges.empty:
        best["p_win"] = np.nan
        return best
    ekey = ["_date_iso","_home_nick","_away_nick","market_norm","side_norm"]
    missing = [c for c in ekey if c not in edges.columns]
    if missing:
        # fallback: if edges lacks market/side, don’t block—just don’t join p_win
        best["p_win"] = np.nan
        return best
    out = best.merge(edges[ekey + (["p_win"] if "p_win" in edges.columns else [])],
                     how="left", on=ekey, suffixes=("", "_edge"))
    if "p_win" not in out.columns: out["p_win"] = np.nan
    return out

def make_picks(edges: pd.DataFrame, odds: pd.DataFrame) -> pd.DataFrame:
    # Best price per (date,home,away,market,side)
    key = ["_date_iso","_home_nick","_away_nick","market_norm","side_norm"]
    best = (odds
        .dropna(subset=["odds"])
        .sort_values(key + ["odds"], ascending=[True,True,True,True,True,False])
        .drop_duplicates(subset=key, keep="first")
        .copy()
    )
    # Attach p_win if we can match
    best = join_edges(best, edges)

    # EV per $1 (if p_win present)
    if "p_win" in best.columns and best["p_win"].notna().any():
        o = best["odds"]
        dec = np.where(o > 0, 1 + o/100.0, 1 + 100.0/np.maximum(1, -o))
        best["_ev_per_$1"] = best["p_win"] * (dec - 1) - (1 - best["p_win"])
    else:
        best["_ev_per_$1"] = np.nan

    # Enforce one pick per (date,game,market): prefer highest EV then best price
    best["_sort_ev"] = best["_ev_per_$1"].fillna(-9e9)
    picks = (best
        .sort_values(["_date_iso","_home_nick","_away_nick","market_norm","_sort_ev","odds"],
                     ascending=[True,True,True,True,False,False])
        .drop_duplicates(subset=["_date_iso","_home_nick","_away_nick","market_norm"], keep="first")
        .copy()
    )

    # Final schema for Backtest
    out_cols = [
        "_date_iso","_home_nick","_away_nick","market_norm","side_norm",
        "line","odds","book","_ev_per_$1","p_win","game_id","source"
    ]
    for c in ("game_id","source"):
        if c not in picks.columns: picks[c] = ""
    picks["source"] = "bot_from_odds"
    return picks[out_cols]

def main():
    edges = load_edges(EDGES_PATH)
    odds  = load_odds(ODDS_PATH)
    picks = make_picks(edges, odds)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    picks.to_csv(OUT_PATH, index=False)
    # quick sanity print
    nonnull = {c: int(picks[c].notna().sum()) for c in ["_date_iso","_home_nick","_away_nick","market_norm","side_norm","odds"]}
    print(f"[ok] wrote {len(picks):,} picks → {OUT_PATH}  | non-null keys: {nonnull}")

if __name__ == "__main__":
    main()
