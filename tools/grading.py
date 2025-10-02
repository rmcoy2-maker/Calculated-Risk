# tools/grading.py
from __future__ import annotations
import numpy as np
import pandas as pd

def american_to_prob(odds: float) -> float:
    try:
        o = float(odds)
    except Exception:
        return np.nan
    if o > 0:  return 100.0 / (o + 100.0)
    if o < 0:  return (-o) / ((-o) + 100.0)
    return np.nan

def odds_profit(stake: float, odds: float, result: str) -> float:
    r = (result or "").strip().lower()
    if r in ("push","void"): return 0.0
    if r != "win": return -float(stake)
    o = float(odds)
    if o > 0:  return stake * (o / 100.0)
    if o < 0:  return stake * (100.0 / abs(o))
    return 0.0

def _winner_from_scores(s: pd.Series) -> str:
    # expects: home_team, away_team, home_score, away_score
    try:
        hs = float(s["home_score"]); as_ = float(s["away_score"])
    except Exception:
        return ""
    if hs == as_: return "PUSH"
    return s["home_team"] if hs > as_ else s["away_team"]

def _normalize_scores(scores: pd.DataFrame) -> pd.DataFrame:
    # expected columns: game_id, home_team, away_team, home_score, away_score
    keep = ["game_id","home_team","away_team","home_score","away_score"]
    for k in keep:
        if k not in scores.columns:
            scores[k] = np.nan
    out = scores[keep].copy()
    out["home_score"] = pd.to_numeric(out["home_score"], errors="coerce")
    out["away_score"] = pd.to_numeric(out["away_score"], errors="coerce")
    out["winner"] = out.apply(_winner_from_scores, axis=1)
    out["total_pts"] = out["home_score"] + out["away_score"]
    return out

def grade_shop_bets(bets: pd.DataFrame, scores: pd.DataFrame, default_stake: float = 1.0) -> pd.DataFrame:
    """
    bets columns (at minimum): game_id, market, ref, side, odds, line, quoted_ts, book
    scores columns: game_id, home_team, away_team, home_score, away_score
    """
    b = bets.copy()
    s = _normalize_scores(scores.copy())
    df = b.merge(s, on="game_id", how="left", suffixes=("","_s"))

    # resolve team orientation for spreads
    def team_margin(row) -> float:
        home, away = str(row["home_team"]), str(row["away_team"])
        hs, as_ = row["home_score"], row["away_score"]
        ref = str(row["ref"])
        if pd.isna(hs) or pd.isna(as_): return np.nan
        if ref == home: return hs - as_
        if ref == away: return as_ - hs
        # fall back: if side says 'home'/'away'
        side = str(row["side"]).lower()
        if side == "home": return hs - as_
        if side == "away": return as_ - hs
        return np.nan

    df["_margin"] = df.apply(team_margin, axis=1)

    def decide(row) -> str:
        mkt = str(row["market"])
        hs, as_, tot = row["home_score"], row["away_score"], row["total_pts"]
        line = row.get("line")
        side = str(row["side"]).strip().lower()
        ref  = str(row["ref"])
        win  = str(row["winner"])

        if pd.isna(hs) or pd.isna(as_): return "pending"

        if mkt == "H2H":
            if win == "PUSH": return "push"
            return "win" if ref == win or (side in ("home","away") and ((side=="home" and win==row["home_team"]) or (side=="away" and win==row["away_team"]))) else "loss"

        if mkt == "SPREADS":
            if pd.isna(row["_margin"]) or pd.isna(line): return "pending"
            diff = row["_margin"] - float(line)
            if diff > 0: return "win"
            if diff == 0: return "push"
            return "loss"

        if mkt == "TOTALS":
            if pd.isna(tot) or pd.isna(line): return "pending"
            if side in ("o","over","over ", "Over"):  # forgiving
                if tot > float(line): return "win"
                if tot == float(line): return "push"
                return "loss"
            # Under
            if tot < float(line): return "win"
            if tot == float(line): return "push"
            return "loss"

        # unknown market → leave pending
        return "pending"

    df["_result"] = df.apply(decide, axis=1)

    # profit in units
    stake = pd.to_numeric(b.get("stake", default_stake), errors="coerce").fillna(default_stake)
    df["_profit_units"] = [
        odds_profit(stk, odd, res) for stk, odd, res in zip(stake, df["odds"], df["_result"])
    ]

    # friendly outputs
    out_cols = list(bets.columns) + ["home_team","away_team","home_score","away_score","winner","total_pts","_margin","_result","_profit_units"]
    out = df[out_cols].copy()
    return out
from tools.lines_shop_io import read_latest_shop, snapshot_shop
df = read_latest_shop()
snapshot_path = snapshot_shop(df)  # writes exports/lines_snapshots/lines_shop_*.parquet


