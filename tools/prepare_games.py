# tools/prepare_games.py
from __future__ import annotations
import pandas as pd, argparse
from _io import read_csv, to_int, norm_team

def main(in_path, out_path):
    g = read_csv(in_path)
    # expected cols: season, week, game_date, home_team, away_team, home_score, away_score, status (any casing)
    g["league"] = g.get("league", "nfl")
    g["season"] = to_int(g["season"])
    g["week"]   = to_int(g["week"])
    g["home_team"] = g["home_team"].map(norm_team)
    g["away_team"] = g["away_team"].map(norm_team)
    g["home_score"] = to_int(g.get("home_score"))
    g["away_score"] = to_int(g.get("away_score"))
    g["status"] = g.get("status", "final").str.lower()

    # build game_id if missing
    if "game_id" not in g.columns or g["game_id"].eq("").any():
        g["game_id"] = (
            g["season"].astype(str) + "_" +
            g["week"].astype(str).str.zfill(2) + "_" +
            g["away_team"] + "@" + g["home_team"]
        )

    cols = ["game_id","season","week","league","game_date","home_team","away_team","home_score","away_score","status"]
    g[cols].to_csv(out_path, index=False)
    print(f"[ok] wrote {out_path} rows={len(g)} finals={(g['status']=='final').sum()}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()
    main(args.inp, args.out)

