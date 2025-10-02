# tools/grade_edges_from_scores.py
import pandas as pd
from pathlib import Path
import argparse
import shutil

def norm(x):
    return (str(x) if pd.notna(x) else "").strip().lower()

def grade_row(r):
    market = norm(r.get("market"))
    side   = norm(r.get("side"))
    line   = r.get("line")
    try:
        line = float(line)
    except Exception:
        line = None

    hs = r.get("home_score"); as_ = r.get("away_score")
    if pd.isna(hs) or pd.isna(as_):
        return None  # no score -> cannot grade

    hs = float(hs); as_ = float(as_)
    total_pts = hs + as_

    # who is the bet's team?
    home_team = norm(r.get("home_team"))
    away_team = norm(r.get("away_team"))

    # Simple ML grading
    if market in ("ml","moneyline","money line"):
        if side == home_team:
            return "win" if hs > as_ else ("push" if hs == as_ else "lose")
        if side == away_team:
            return "win" if as_ > hs else ("push" if hs == as_ else "lose")
        # If side is a team string not matching, leave ungraded
        return None

    # Spread grading (assumes side is team, line is that team's handicap)
    if market in ("spread","spreads","ats","line"):
        if line is None:
            return None
        if side == home_team:
            margin = (hs - as_) - line
        elif side == away_team:
            margin = (as_ - hs) - line
        else:
            return None
        return "win" if margin > 0 else ("push" if margin == 0 else "lose")

    # Total grading
    if market in ("total","totals","o/u","ou","over_under","overunder"):
        if line is None:
            return None
        if side in ("over","o"):
            return "win" if total_pts > line else ("push" if total_pts == line else "lose")
        if side in ("under","u"):
            return "win" if total_pts < line else ("push" if total_pts == line else "lose")
        return None

    # Unknown / props -> leave as-is
    return None

def main(edges_path, games_path):
    edges = pd.read_csv(edges_path)
    games = pd.read_csv(games_path)

    # normalize columns
    edges.columns = [c.strip().lower() for c in edges.columns]
    games.columns = [c.strip().lower() for c in games.columns]

    need_games = {"game_id","home_team","away_team","home_score","away_score"}
    missing = need_games - set(games.columns)
    if missing:
        raise SystemExit(f"games.csv missing columns: {sorted(missing)}")

    # Merge scores into edges
    merged = edges.merge(
        games[list(need_games)],
        on="game_id",
        how="left",
        suffixes=("","_g")
    )

    # Only grade rows where result is empty/NaN
    mask_ungraded = merged["result"].isna() | (merged["result"].astype(str).str.strip() == "")
    graded = 0
    results = []

    for _, r in merged.iterrows():
        if mask_ungraded.loc[_]:
            res = grade_row(r)
        else:
            res = r.get("result")
        results.append(res)
        if res in ("win","lose","push"):
            graded += 1

    merged["result"] = results

    # Write back to edges.csv (with backup)
    backup = Path(str(edges_path) + ".bak")
    shutil.copy2(edges_path, backup)
    merged.drop(columns=[c for c in ["home_team","away_team","home_score","away_score"] if c in merged.columns], inplace=True)

    # Keep original column order where possible
    merged = merged[edges.columns] if set(edges.columns).issubset(merged.columns) else merged
    merged.to_csv(edges_path, index=False, encoding="utf-8-sig")
    print(f"Graded {graded} rows. Backup written to {backup}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", default="exports/edges.csv")
    ap.add_argument("--games", default="exports/games.csv")
    args = ap.parse_args()
    main(args.edges, args.games)

