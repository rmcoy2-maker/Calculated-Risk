import argparse, hashlib
from pathlib import Path
import pandas as pd
import numpy as np

TEAM_FIX = {
    "St. Louis Rams":"Los Angeles Rams",
    "LA Rams":"Los Angeles Rams",
    "San Diego Chargers":"Los Angeles Chargers",
    "LA Chargers":"Los Angeles Chargers",
    "Washington Redskins":"Washington Commanders",
    "Washington Football Team":"Washington Commanders",
    "Oakland Raiders":"Las Vegas Raiders",
    "Phoenix Cardinals":"Arizona Cardinals",
    "Tennessee Oilers":"Tennessee Titans",
}

def norm_team(x):
    if pd.isna(x):
        return x
    s = str(x).strip()
    return TEAM_FIX.get(s, s)

def mk_gid(date, home, away, league="NFL"):
    d = pd.to_datetime(date, errors="coerce").strftime("%Y-%m-%d")
    key = f"{d}|{norm_team(home)}|{norm_team(away)}|{league}"
    return hashlib.md5(key.encode()).hexdigest()[:12]

def load_scores(path):
    df = pd.read_csv(path)

    # unify common schemas -> [date, home, away, home_score, away_score, season, week]
    colmap = {
        # generic/datasets
        "game_date":"date", "start_time":"date", "date_utc":"date", "date":"date",
        "home_team":"home", "team_home":"home", "home":"home",
        "away_team":"away", "team_away":"away", "away":"away",
        "score_home":"home_score", "home_points":"home_score", "pts_home":"home_score",
        "score_away":"away_score", "away_points":"away_score", "pts_away":"away_score",
        "season":"season", "schedule_season":"season", "year":"season",
        "week":"week", "schedule_week":"week",
    }
    for a,b in colmap.items():
        if a in df.columns and b not in df.columns:
            df[b] = df[a]

    need = ["date","home","away","home_score","away_score","season"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise SystemExit(f"{path} missing columns {missing}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["home"] = df["home"].map(norm_team)
    df["away"] = df["away"].map(norm_team)
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    if "week" not in df.columns:
        df["week"] = np.nan

    df["game_id_unified"] = df.apply(lambda r: mk_gid(r["date"], r["home"], r["away"]), axis=1)
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oddsshark_all", required=False)
    ap.add_argument("--new2017", required=False)
    ap.add_argument("--extra", nargs="*", default=[], help="additional CSVs")
    ap.add_argument("--out", default="exports/scores_unified.csv")
    args = ap.parse_args()

    parts = []
    if args.oddsshark_all: parts.append(("odd", load_scores(args.oddsshark_all)))
    if args.new2017:       parts.append(("new2017", load_scores(args.new2017)))
    for p in args.extra:   parts.append((p, load_scores(p)))

    if not parts:
        raise SystemExit("No inputs provided. Pass at least one of --oddsshark_all, --new2017, or --extra")

    tag_to_df = dict(parts)
    if "odd" in tag_to_df and "new2017" in tag_to_df:
        odd = tag_to_df["odd"]; new = tag_to_df["new2017"]
        odd_pre2017 = odd[odd["season"] < 2017]
        new_2017p   = new[new["season"] >= 2017]
        odd_2017p   = odd[(odd["season"] >= 2017) & (~odd["game_id_unified"].isin(new_2017p["game_id_unified"]))]
        uni = pd.concat([odd_pre2017, new_2017p, odd_2017p], ignore_index=True)
        for key, df in parts:
            if key not in ("odd","new2017"):
                uni = pd.concat([uni, df], ignore_index=True)
    else:
        uni = pd.concat([df for _, df in parts], ignore_index=True)

    uni = uni.drop_duplicates(subset=["game_id_unified"])
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    uni.to_csv(args.out, index=False)
    seasons = ", ".join(str(int(s)) for s in sorted(uni["season"].dropna().unique()))
    print(f"[done] wrote {args.out} with {len(uni):,} games; seasons: {seasons}")

if __name__ == "__main__":
    main()

