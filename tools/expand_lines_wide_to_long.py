# tools/expand_lines_wide_to_long.py
from __future__ import annotations
from pathlib import Path
import os
import pandas as pd
import numpy as np

EXP = Path(os.environ.get("EDGE_EXPORTS_DIR", "") or Path(__file__).resolve().parents[1] / "exports")
EXP.mkdir(parents=True, exist_ok=True)

CANDIDATES = [
    EXP / "odds_lines_all.csv",
    EXP / "odds_all.csv",
    EXP / "odds.csv",
]

def _load_first(paths):
    for p in paths:
        if p.exists():
            return pd.read_csv(p, low_memory=False), p
    raise FileNotFoundError("No odds CSV found in exports/ (looked for odds_lines_all.csv, odds_all.csv, odds.csv)")

def _nickify(s: pd.Series) -> pd.Series:
    return (
        s.astype("string")
         .str.upper()
         .str.replace(r"[^A-Z0-9 ]+","", regex=True)
         .str.strip()
         .str.replace(r"\s+","_", regex=True)
    )

def _ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    w = df.copy()
    # normalize common variants
    if "market" not in w and "market_norm" in w: w["market"] = w["market_norm"]
    if "odds"   not in w and "price"       in w: w["odds"]   = w["price"]
    if "decimal_odds" not in w and "decimal" in w: w["decimal_odds"] = w["decimal"]
    # parse times if present
    if "captured_at" not in w.columns:
        for c in ("_captured_at","asof_ts","pulled_at","fetched_at"):
            if c in w.columns:
                w["captured_at"] = w[c]
                break
    if "kickoff" not in w.columns:
        if "commence_time" in w.columns:
            w["kickoff"] = w["commence_time"]
        elif "_date_iso" in w.columns:
            w["kickoff"] = w["_date_iso"]
    # synthesize game_id if needed
    if "game_id" not in w.columns:
        away_src = next((c for c in ["_away_nick","away_team","away"] if c in w.columns), None)
        home_src = next((c for c in ["_home_nick","home_team","home"] if c in w.columns), None)
        date_src = "kickoff" if "kickoff" in w.columns else None
        away = _nickify(w[away_src]) if away_src else ""
        home = _nickify(w[home_src]) if home_src else ""
        date = pd.to_datetime(w[date_src], errors="coerce", utc=True).dt.date.astype("string") if date_src else ""
        w["game_id"] = date + "::" + away + "@" + home
    # book fallback
    if "book" not in w.columns:
        alt = next((c for c in ["bookmaker","site","sportsbook"] if c in w.columns), None)
        w["book"] = w[alt] if alt else "(unknown)"
    return w

def expand(df: pd.DataFrame) -> pd.DataFrame:
    w = _ensure_cols(df)

    rows = []

    # Heuristics: your files may have any subset of these sets. We create rows only when fields exist.
    # --- MONEYLINE ---
    for home_col, away_col in [("home_odds","away_odds"), ("home_price","away_price"), ("price_home","price_away")]:
        if home_col in w.columns or away_col in w.columns:
            base_cols = ["game_id","book","kickoff","captured_at"]
            keep = [c for c in base_cols + ["market"] if c in w.columns]
            sub = w[keep].copy()
            sub["market"] = sub.get("market","H2H")
            # HOME row
            if home_col in w.columns:
                rH = sub.copy()
                rH["side"] = "HOME"
                rH["line"] = np.nan
                rH["odds"] = pd.to_numeric(w[home_col], errors="coerce")
                rows.append(rH)
            # AWAY row
            if away_col in w.columns:
                rA = sub.copy()
                rA["side"] = "AWAY"
                rA["line"] = np.nan
                rA["odds"] = pd.to_numeric(w[away_col], errors="coerce")
                rows.append(rA)
            break  # don’t double-add if multiple pairs exist

    # --- SPREADS ---
    # Patterns:
    # 1) one spread line column (home favored negative, away is the negation): spread / spread_line / handicap
    for spread_col in ("spread","spread_line","handicap","handicap_home"):
        if spread_col in w.columns:
            base_cols = ["game_id","book","kickoff","captured_at"]
            keep = [c for c in base_cols + ["market"] if c in w.columns]
            sub = w[keep].copy()
            sub["market"] = "SPREADS"
            line_home = pd.to_numeric(w[spread_col], errors="coerce")
            line_away = -line_home
            # odds columns if split by side
            home_odds = None
            away_odds = None
            for hc, ac in [("home_spread_odds","away_spread_odds"), ("price_home","price_away")]:
                if hc in w.columns and ac in w.columns:
                    home_odds = pd.to_numeric(w[hc], errors="coerce")
                    away_odds = pd.to_numeric(w[ac], errors="coerce")
                    break
            # HOME
            rH = sub.copy()
            rH["side"] = "HOME"
            rH["line"] = line_home
            rH["odds"] = home_odds if home_odds is not None else pd.to_numeric(w.get("odds"), errors="coerce")
            rows.append(rH)
            # AWAY
            rA = sub.copy()
            rA["side"] = "AWAY"
            rA["line"] = line_away
            rA["odds"] = away_odds if away_odds is not None else pd.to_numeric(w.get("odds"), errors="coerce")
            rows.append(rA)
            break

    # 2) explicit home/away handicap columns
    if "handicap_home" in w.columns and "handicap_away" in w.columns:
        base_cols = ["game_id","book","kickoff","captured_at"]
        keep = [c for c in base_cols + ["market"] if c in w.columns]
        sub = w[keep].copy()
        sub["market"] = "SPREADS"
        # HOME
        rH = sub.copy()
        rH["side"] = "HOME"
        rH["line"] = pd.to_numeric(w["handicap_home"], errors="coerce")
        rH["odds"] = pd.to_numeric(w.get("home_spread_odds", w.get("price_home")), errors="coerce")
        rows.append(rH)
        # AWAY
        rA = sub.copy()
        rA["side"] = "AWAY"
        rA["line"] = pd.to_numeric(w["handicap_away"], errors="coerce")
        rA["odds"] = pd.to_numeric(w.get("away_spread_odds", w.get("price_away")), errors="coerce")
        rows.append(rA)

    # --- TOTALS ---
    # Common pattern: one total line + separate over/under odds
    if "total" in w.columns or "total_line" in w.columns or "points_total" in w.columns:
        tot_col = next(c for c in ("total","total_line","points_total") if c in w.columns)
        base_cols = ["game_id","book","kickoff","captured_at"]
        keep = [c for c in base_cols + ["market"] if c in w.columns]
        sub = w[keep].copy()
        sub["market"] = "TOTALS"
        line_total = pd.to_numeric(w[tot_col], errors="coerce")
        # odds columns for OU
        over_odds  = None
        under_odds = None
        for oc, uc in [("over_odds","under_odds"), ("price_over","price_under"), ("ou_price_over","ou_price_under")]:
            if oc in w.columns and uc in w.columns:
                over_odds  = pd.to_numeric(w[oc], errors="coerce")
                under_odds = pd.to_numeric(w[uc], errors="coerce")
                break
        # OVER
        rO = sub.copy()
        rO["side"] = "OVER"
        rO["line"] = line_total
        rO["odds"] = over_odds if over_odds is not None else pd.to_numeric(w.get("odds"), errors="coerce")
        rows.append(rO)
        # UNDER
        rU = sub.copy()
        rU["side"] = "UNDER"
        rU["line"] = line_total
        rU["odds"] = under_odds if under_odds is not None else pd.to_numeric(w.get("odds"), errors="coerce")
        rows.append(rU)

    # If we didn’t create any rows (no wide cols found), just pass through any existing tidy rows.
    if not rows:
        tidy = w.copy()
        if "side" not in tidy.columns:
            tidy["side"] = np.nan
        if "market" not in tidy.columns:
            tidy["market"] = "H2H"
        tidy["line"] = pd.to_numeric(tidy.get("line"), errors="coerce")
        tidy["odds"] = pd.to_numeric(tidy.get("odds"), errors="coerce")
        return tidy

    out = pd.concat(rows, ignore_index=True)
    # ensure dtypes
    out["line"] = pd.to_numeric(out["line"], errors="coerce")
    out["odds"] = pd.to_numeric(out["odds"], errors="coerce")
    return out

def main():
    df, src = _load_first(CANDIDATES)
    long = expand(df)
    dest = EXP / "odds_lines_all_long.csv"
    long.to_csv(dest, index=False)
    print(f"[expand] {src.name} -> {dest} rows={len(long)}")

if __name__ == "__main__":
    main()
