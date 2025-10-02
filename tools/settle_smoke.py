# tools/settle_smoke.py
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

# --- imports from your other helper modules ---
# Expect these files to exist as we discussed:
#   tools/odds_core.py  -> normalize_odds_lines, attach_odds
#   tools/settle_core.py-> settle_bets, filter_by_season_week, metrics_by_market, metrics_by_team
from odds_core import normalize_odds_lines, attach_odds
from settle_core import settle_bets, filter_by_season_week, metrics_by_market, metrics_by_team

# ---------------- helpers (lightweight, local) ----------------

def _s(x) -> pd.Series:
    return x.astype("string").fillna("") if isinstance(x, pd.Series) else pd.Series([x], dtype="string")

def _nickify(series: pd.Series) -> pd.Series:
    alias = {
        "REDSKINS": "COMMANDERS", "WASHINGTON": "COMMANDERS", "FOOTBALL": "COMMANDERS",
        "OAKLAND": "RAIDERS", "LV": "RAIDERS", "LAS": "RAIDERS", "VEGAS": "RAIDERS",
        "SD": "CHARGERS", "LA": "RAMS", "STL": "RAMS",
    }
    s = _s(series).str.upper().str.replace(r"[^A-Z0-9 ]+", "", regex=True).str.strip().replace(alias)
    return s.str.replace(r"\s+", "_", regex=True)

def _nick_core(s: pd.Series) -> pd.Series:
    return _s(s).str.split("_").str[-1]

def _pick_col(df: pd.DataFrame, candidates: list[str], regex: str | None = None) -> str | None:
    if regex:
        for c in df.columns:
            if pd.Series([c]).str.contains(regex, case=False, regex=True).any():
                return c
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _num(df: pd.DataFrame, candidates: list[str], regex: str | None = None) -> pd.Series:
    col = _pick_col(df, candidates, regex)
    if not col:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce")

def _str(df: pd.DataFrame, candidates: list[str], regex: str | None = None) -> pd.Series:
    col = _pick_col(df, candidates, regex)
    if not col:
        return pd.Series([""] * len(df), index=df.index, dtype="string")
    return _s(df[col])

# ---------------- scores attachment (tolerant) ----------------

def attach_scores(edges: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    e = edges.copy()
    s = scores.copy()

    # Normalize edges identifiers
    if "_home_nick" not in e.columns or e["_home_nick"].isna().all():
        e["_home_nick"] = _nickify(_str(e, ["_home_nick","home_team","HomeTeam"]))
    if "_away_nick" not in e.columns or e["_away_nick"].isna().all():
        e["_away_nick"] = _nickify(_str(e, ["_away_nick","away_team","AwayTeam"]))
    e["_home_core"] = _nick_core(e["_home_nick"])
    e["_away_core"] = _nick_core(e["_away_nick"])

    e["_season"] = _s(e.get("_season", e.get("season","")))
    e["_week"]   = _s(e.get("_week",   e.get("week","")))
    e["_DateISO"]  = _s(e.get("_DateISO", e.get("Date","")))
    e["_key_date"] = _s(e.get("_key_date", e["_DateISO"]))

    # Normalize scores
    s["_home_nick"] = _nickify(_str(s, ["_home_nick","home","Home","home_team","HomeTeam"]))
    s["_away_nick"] = _nickify(_str(s, ["_away_nick","away","Away","away_team","AwayTeam"]))
    s["_home_core"] = _nick_core(s["_home_nick"])
    s["_away_core"] = _nick_core(s["_away_nick"])

    s["_season"] = _s(s.get("_season", s.get("season","")))
    s["_week"]   = _s(s.get("_week",   s.get("week","")))
    s["_DateISO"]  = _s(s.get("_DateISO", s.get("Date","")))
    s["_key_date"] = _s(s.get("_key_date", s["_DateISO"]))

    s["home_score"] = pd.to_numeric(_str(s, ["home_score","HomeScore","home_pts","HomePts"]), errors="coerce")
    s["away_score"] = pd.to_numeric(_str(s, ["away_score","AwayScore","away_pts","AwayPts"]), errors="coerce")

    # Strict: date + teams (also carry scores date fields for repair)
    m1 = e.merge(
        s[["_key_date","_DateISO","_home_nick","_away_nick","home_score","away_score"]],
        on=["_key_date","_home_nick","_away_nick"], how="left", suffixes=("","_sc1")
    ).rename(columns={"_DateISO_sc1":"_DateISO_sc1"})

    # Fallback: season/week + core teams (carry scores date too)
    m2 = m1.merge(
        s[["_season","_week","_home_core","_away_core","_DateISO","home_score","away_score"]],
        left_on=["_season","_week","_home_core","_away_core"],
        right_on=["_season","_week","_home_core","_away_core"],
        how="left", suffixes=("","_sc2")
    ).rename(columns={"_DateISO_sc2":"_DateISO_sc2"})

    merged = m2

    # Fill scores from sc2 then sc1
    for col in ("home_score","away_score"):
        c2, c1 = f"{col}_sc2", f"{col}_sc1"
        if c2 in merged.columns:
            need = merged[col].isna()
            merged.loc[need, col] = merged.loc[need, c2].to_numpy()
        if c1 in merged.columns:
            need = merged[col].isna()
            merged.loc[need, col] = merged.loc[need, c1].to_numpy()

    # ---- REPAIR DATES using scores' date ----
    # choose a scores date from either strict/fallback
    sc_date = _s(merged.get("_DateISO_sc2",""))
    sc_date = sc_date.where(sc_date != "", _s(merged.get("_DateISO_sc1","")))
    sc_year = sc_date.str.slice(0, 4)
    ed_year = _s(merged["_season"]).str.extract(r"(\d{4})", expand=False).fillna("")
    # Need date if empty OR year mismatch with season
    need_date = (merged["_DateISO"] == "") | ((sc_year != "") & (ed_year != "") & (sc_year != ed_year))
    merged.loc[need_date & (sc_date != ""), "_DateISO"] = sc_date[need_date & (sc_date != "")]
    merged["_key_date"] = merged["_DateISO"]

    # Cleanup helper cols
    drop_cols = [c for c in merged.columns if c.endswith("_sc1") or c.endswith("_sc2")]
    if drop_cols:
        merged = merged.drop(columns=drop_cols, errors="ignore")

    merged["_joined_with_scores"] = merged["home_score"].notna() & merged["away_score"].notna()
    return merged

# ---------------- main ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="", help="Edges CSV (graded edges to settle)")
    ap.add_argument("--scores", default="", help="Scores CSV (optional)")
    ap.add_argument("--odds", default="", help="Odds/lines CSV (optional)")
    ap.add_argument("--season", default="All", help='Season filter (e.g., 2024 or "All")')
    ap.add_argument("--week", default="All Weeks", help='Week filter (e.g., 1 or "All Weeks")')

    # Assumption knobs
    ap.add_argument("--assume-ml-price", choices=["even","pwin","none"], default="even",
                    help="Fill missing H2H prices: even=+100, pwin=estimate from p_win, none=no P/L")
    ap.add_argument("--st-default-price", type=float, default=-110.0,
                    help="Default price for spreads/totals when price missing")
    ap.add_argument("--odds-coverage-starts", type=int, default=2006,
                    help="Seasons before this lack spread/total lines; void ST bets there")

    args = ap.parse_args()

    # ---- load edges
    src = Path(args.src) if args.src else None
    if not src or not src.exists():
        print("ERROR: --src CSV not found")
        return
    print(f"[load] {src.as_posix()}")
    edges = pd.read_csv(src, low_memory=False)

    # ---- attach scores (optional)
    if args.scores:
        sc_path = Path(args.scores)
        if sc_path.exists():
            print(f"[attach] scores -> {sc_path.as_posix()}")
            scores_raw = pd.read_csv(sc_path, low_memory=False)
            edges = attach_scores(edges, scores_raw)
        else:
            print("[warn] scores file not found")

    # ---- attach odds (optional)
    if args.odds:
        od_path = Path(args.odds)
        if od_path.exists():
            print(f"[attach] odds -> {od_path.as_posix()}")
            odds_raw = pd.read_csv(od_path, low_memory=False)
            odds_tidy = normalize_odds_lines(odds_raw)
            edges = attach_odds(edges, odds_tidy, prefer_books=["Pinnacle","Circa","Bookmaker","DK","FD"])
        else:
            print("[warn] odds file not found")

    # ---- filter by season/week (if present)
    df = filter_by_season_week(edges, season=args.season, week=args.week)

    print(f"[rows] total after filter: {len(df):,}")

    # ---- settle with assumptions
    df = settle_bets(
        df,
        assume_ml_price=args.assume_ml_price,
        st_default_price=args.st_default_price,
        odds_coverage_starts=args.odds_coverage_starts,
    )

    # ---- market metrics
    mkt = metrics_by_market(df)
    print("\n[markets]")
    if not mkt.empty:
        print(mkt.to_string(index=False))
    else:
        print("(no rows)")

    # ---- team metrics (top 10)
    teams = metrics_by_team(df)
    print("\n[teams — top 10 by profit]")
    if not teams.empty:
        print(teams.head(10).to_string(index=False))
    else:
        print("(no rows)")

    # ---- basic diagnostics (optional but helpful)
    try:
        season_counts = (
            df.groupby(["_season","market"], dropna=False)["_result"]
              .value_counts()
              .unstack(fill_value=0)
              .reset_index()
        )
        print("\n[diag] counts by season/market (first 12 rows):")
        print(season_counts.head(12).to_string(index=False))
    except Exception:
        pass


if __name__ == "__main__":
    pd.set_option("display.width", 140)
    pd.set_option("display.max_columns", 20)
    main()

