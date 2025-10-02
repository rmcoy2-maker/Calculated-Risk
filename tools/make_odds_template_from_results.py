#!/usr/bin/env python
import argparse
from pathlib import Path
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="exports/results.csv")
    ap.add_argument("--odds-merged", default="exports/historical_odds_merged.csv")
    ap.add_argument("--seasons", nargs="*", type=int, default=[2019,2020,2021,2022,2023])
    ap.add_argument("--out", default="exports/odds_template_missing_2019_2023.csv")
    args = ap.parse_args()

    res = pd.read_csv(args.results)
    res["home"] = res["home"].astype(str).str.strip()
    res["away"] = res["away"].astype(str).str.strip()
    for c in ("season","week"):
        if c in res.columns:
            res[c] = pd.to_numeric(res[c], errors="coerce").astype("Int64")

    res = res[res["season"].isin(args.seasons)].copy()
    # canonical unique games by season+week+teams
    base = res[["season","week","date","home","away"]].drop_duplicates().copy()

    # What do we already have?
    has = pd.DataFrame()
    odspath = Path(args.odds_merged)
    if odspath.exists():
        has = pd.read_csv(odspath)
        has["home"] = has["home"].astype(str).str.strip()
        has["away"] = has["away"].astype(str).str.strip()
        for c in ("season","week"):
            if c in has.columns:
                has[c] = pd.to_numeric(has[c], errors="coerce").astype("Int64")
        has = has[["season","week","home","away","spread_close","total_close","spread_open","total_open"]]

    merged = base.merge(has, on=["season","week","home","away"], how="left")

    # “Missing” = neither close nor open present
    missing = merged.loc[
        merged[["spread_close","total_close","spread_open","total_open"]].isna().all(axis=1),
        ["season","week","date","home","away"]
    ].sort_values(["season","week","home","away"])

    # Provide empty columns for you to paste lines into
    for c in ("spread_close","total_close","spread_open","total_open","ml_home","ml_away"):
        missing[c] = ""

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    missing.to_csv(outp, index=False)
    print(f"[write] {outp} rows={len(missing)}")

if __name__ == "__main__":
    main()

