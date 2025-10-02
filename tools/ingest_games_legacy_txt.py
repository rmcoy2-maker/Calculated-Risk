#!/usr/bin/env python
import argparse, pandas as pd
from pathlib import Path
from datetime import datetime

def parse_date_from_gameid(gid):
    s = str(gid)
    try:
        return datetime.strptime(s[:8], "%Y%m%d").date()
    except Exception:
        return pd.NaT

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--txt", required=True, help="Path to 'games 1966-2017.txt'")
    ap.add_argument("--out", required=True, help="CSV to write (results format)")
    args = ap.parse_args()

    df = pd.read_csv(args.txt)
    # Normalize header names we care about
    rename = {
        "Year":"season", "Week":"week", "GameID":"game_id",
        "Team Home Name":"home", " Team Home Name":"home",  # your file has a leading space
        " Team Home Score":"home_score", "Team Away Name":"away",
        "Team Away Score":"away_score"
    }
    df = df.rename(columns={k:v for k,v in rename.items() if k in df.columns})

    # Basic typing
    for c in ["season","week","home_score","away_score"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Date from GameID (YYYYMMDDxxxx)
    if "game_id" in df.columns:
        df["date"] = df["game_id"].astype(str).map(parse_date_from_gameid)

    # Keep only what backtest needs; market/line/side are optional and can be absent
    keep = ["season","week","date","game_id","home","away","home_score","away_score"]
    df = df[[c for c in keep if c in df.columns]].copy()

    # Write
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"[write] {out} rows={len(df)}")

if __name__ == "__main__":
    main()

