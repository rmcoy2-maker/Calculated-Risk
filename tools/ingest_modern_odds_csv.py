#!/usr/bin/env python
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

ALIASES = {
    "season": ["season","year"],
    "week":   ["week","wk"],
    "date":   ["date","game_date","kickoff"],
    "home":   ["home","home_team","team_home"],
    "away":   ["away","away_team","team_away"],
    # spread/total: accept either opening or closing; we’ll map into *_open / *_close
    "spread_close": ["spread_close","closing_spread","final_spread"],
    "total_close":  ["total_close","closing_total","final_total","ou_close","o/u_close","ou"],
    "spread_open":  ["spread_open","opening_spread","open_spread","line_open","opening_line","open"],
    "total_open":   ["total_open","opening_total","open_total"],
    "ml_home": ["ml_home","home_ml","moneyline_home","home_price"],
    "ml_away": ["ml_away","away_ml","moneyline_away","away_price"],
}

def pick(df, names):
    lower = {c.lower(): c for c in df.columns}
    for n in names:
        if n.lower() in lower: return lower[n.lower()]
    return None

def normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = {}
    for std, alts in ALIASES.items():
        src = pick(df, alts)
        if src is not None:
            out[std] = df[src]
    nd = pd.DataFrame(out)

    # ensure required cols exist
    for c in ["season","week","home","away","spread_close","total_close","spread_open","total_open","ml_home","ml_away","date"]:
        if c not in nd.columns: nd[c] = np.nan

    nd["season"] = pd.to_numeric(nd["season"], errors="coerce").astype("Int64")
    nd["week"]   = pd.to_numeric(nd["week"],   errors="coerce").astype("Int64")

    for c in ["spread_close","total_close","spread_open","total_open","ml_home","ml_away"]:
        nd[c] = pd.to_numeric(nd[c], errors="coerce")

    for c in ["home","away"]:
        nd[c] = nd[c].astype(str).str.strip()

    # prefer closers; if missing but opening exists, we’ll keep opening around for fallback in consolidate
    keep = ["season","week","date","home","away","spread_close","total_close","spread_open","total_open","ml_home","ml_away"]
    return nd[keep]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", nargs="+", required=True, help="One or more CSVs with modern odds (2019+)")
    ap.add_argument("--out", default="exports/historical_odds_modern.csv", help="Output path")
    args = ap.parse_args()

    frames = []
    for p in args.csv:
        path = Path(p)
        if not path.exists(): 
            print(f"[warn] missing {p}")
            continue
        try:
            df = pd.read_csv(path)
            nd = normalize(df)
            if not nd.empty:
                frames.append(nd)
                print(f"[ok] {path} rows={len(nd)}")
        except Exception as e:
            print(f"[warn] failed {p}: {e}")

    if not frames:
        raise SystemExit("No rows ingested.")

    out = pd.concat(frames, ignore_index=True)
    out.to_csv(args.out, index=False)
    print(f"[write] {args.out} rows={len(out)}")

if __name__ == "__main__":
    main()

