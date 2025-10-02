#!/usr/bin/env python
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

RENAME_MAP = {
    # teams
    "HomeTeam":"home","AwayTeam":"away","Home":"home","Away":"away","home_team":"home","away_team":"away",
    # scores
    "HomeScore":"home_score","AwayScore":"away_score","HScore":"home_score","AScore":"away_score",
    # dates / keys
    "Date":"date","GameDate":"date","game_date":"date","Kickoff":"date","kickoff":"date",
    # season/week
    "Season":"season","Year":"season","Week":"week","week_num":"week"
}

def _teamify_strings(df, cols=("home","away")):
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    return df

def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    # 1) rename headers we know
    df = df.rename(columns={k:v for k,v in RENAME_MAP.items() if k in df.columns}).copy()

    # 2) trim whitespace on teams
    df = _teamify_strings(df, ("home","away"))

    # 3) coerce scores to numeric
    for c in ("home_score","away_score"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # 4) parse date if present
    if "date" in df.columns:
        # tolerate many formats
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    # 5) season/week coercion
    if "season" in df.columns:
        df["season"] = pd.to_numeric(df["season"], errors="coerce").astype("Int64")
    else:
        # derive season from date when missing (Jan/Feb -> previous season)
        if "date" in df.columns:
            s = pd.to_datetime(df["date"], errors="coerce")
            df["season"] = (s.dt.year - (s.dt.month <= 2).astype("int")).astype("Int64")

    if "week" in df.columns:
        # extract digits from things like "Week 9", "WK 12", etc.
        wk = df["week"].astype(str).str.extract(r"(\d+)", expand=False)
        df["week"] = pd.to_numeric(wk, errors="coerce").astype("Int64")

    # 6) keep only columns we care about; ignore those Excel-converted “records” like 3-5 -> 3-May
    keep = [c for c in ("season","week","date","home","away","home_score","away_score") if c in df.columns]
    df = df[keep].copy()

    # 7) drop rows without teams or numeric scores (filters schedules)
    df = df.dropna(subset=["home","away","home_score","away_score"]).copy()

    return df

def read_any_csv(p: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(p)
        return _normalize_cols(df)
    except Exception as e:
        print(f"[warn] failed reading {p}: {e}")
        return pd.DataFrame()

def discover_modern_sources(explicit: list[str] | None) -> list[Path]:
    out = []
    if explicit:
        for s in explicit:
            p = Path(s)
            if p.is_dir():
                out.extend(sorted(p.glob("*.csv")))
            elif p.exists():
                out.append(p)
    candidates = [
        Path("2017-2025_scores.csv"),
        Path("exports/results_core_2018_plus.csv"),
        Path("datasets/nfl/scores/2017_scores.csv"),
        Path("datasets/nfl/scores/2018_scores.csv"),
        Path("datasets/nfl/scores/2019_scores.csv"),
        Path("datasets/nfl/scores/2020_scores.csv"),
        Path("datasets/nfl/scores/2021_scores.csv"),
        Path("datasets/nfl/scores/2022_scores.csv"),
        Path("datasets/nfl/scores/2023_scores.csv"),
        Path("datasets/nfl/scores/2024_scores.csv"),
        Path("datasets/nfl/scores/2025_scores.csv"),
    ]
    for c in candidates:
        if c.exists():
            out.append(c)

    seen, uniq = set(), []
    for p in out:
        k = p.resolve()
        if k not in seen:
            seen.add(k); uniq.append(p)
    return uniq

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy", default="exports/results_core_1966_2017.csv",
                    help="CSV with 1966–2017 core results")
    ap.add_argument("--modern", nargs="*", default=None,
                    help="One or more files/dirs for 2017+ results (if omitted, auto-discover)")
    ap.add_argument("--out", default="exports/results.csv",
                    help="Output merged results CSV")
    args = ap.parse_args()

    exports = Path("exports"); exports.mkdir(parents=True, exist_ok=True)
    frames = []

    # legacy
    legacy_path = Path(args.legacy)
    if legacy_path.exists():
        dfl = read_any_csv(legacy_path)
        if not dfl.empty:
            frames.append(dfl)
            print(f"[ok] legacy: {legacy_path} rows={len(dfl)}")
    else:
        print(f"[warn] legacy file not found: {legacy_path}")

    # modern
    total_modern = 0
    for p in discover_modern_sources(args.modern):
        dfm = read_any_csv(p)
        if not dfm.empty:
            frames.append(dfm)
            total_modern += len(dfm)
            print(f"[ok] modern: {p} rows={len(dfm)}")

    if not frames:
        raise SystemExit("No input rows found. Provide --legacy and/or --modern files.")

    merged = pd.concat(frames, ignore_index=True)

    # de-dupe by season+date+teams
    for c in ("season","date","home","away"):
        if c not in merged.columns:
            merged[c] = pd.NA

    merged["game_key"] = (
        merged["season"].astype("Int64").astype(str) + "|" +
        merged["date"].astype(str) + "|" +
        merged["home"].astype(str).str.lower() + "|" +
        merged["away"].astype(str).str.lower()
    )

    merged = (
        merged.sort_values(["season","week","date","home","away"], na_position="last")
              .drop_duplicates(subset=["game_key"], keep="first")
              .drop(columns=["game_key"])
    )

    want = ["season","week","date","home","away","home_score","away_score"]
    cols = [c for c in want if c in merged.columns] + [c for c in merged.columns if c not in want]
    merged = merged[cols]

    outp = Path(args.out)
    merged.to_csv(outp, index=False)
    print(f"[write] {outp} rows={len(merged)}")

if __name__ == "__main__":
    main()

