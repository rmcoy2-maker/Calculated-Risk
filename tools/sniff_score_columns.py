import pandas as pd, pathlib as p, re

candidates = [
    "exports/spreadspoke_scores.csv",
    "datasets/nfl/scores/2017-2025_scores.csv",
    "datasets/nfl/scores/2017_scores.csv",
    "datasets/nfl/scores/2018_scores.csv",
    "datasets/nfl/scores/2019_scores.csv",
    "datasets/nfl/scores/2020_scores.csv",
    "datasets/nfl/scores/2021_scores.csv",
    "datasets/nfl/scores/2022_scores.csv",
    "datasets/nfl/scores/2023_scores.csv",
    "datasets/nfl/scores/2024_scores.csv",
    "datasets/nfl/scores/2025_scores.csv",
    "exports/parlay_scores.csv",
]

def sniff(path):
    try:
        df = pd.read_csv(path, nrows=200)  # small peek
    except Exception as e:
        print(f"[open-fail] {path}: {e}")
        return
    cols = [c for c in df.columns]
    print(f"\n=== {path} ===")
    print("columns:", cols)

    # show candidates for date/home/away
    date_like = [c for c in cols if re.search(r"(date|time|start|sched|kickoff|gameday)", str(c), re.I)]
    home_like = [c for c in cols if re.search(r"(home.*team|team.*home|home$|home_?name|home_?abbr)", str(c), re.I)]
    away_like = [c for c in cols if re.search(r"(away.*team|team.*away|away$|away_?name|away_?abbr)", str(c), re.I)]
    spread_like = [c for c in cols if re.search(r"(spread|line)", str(c), re.I)]
    total_like = [c for c in cols if re.search(r"(total|over[_/ ]?under)", str(c), re.I)]
    ml_like = [c for c in cols if re.search(r"(moneyline|ml_)", str(c), re.I)]

    print("date-like:", date_like)
    print("home-like:", home_like)
    print("away-like:", away_like)
    print("spread-like:", spread_like)
    print("total-like:", total_like)
    print("moneyline-like:", ml_like)

    # show a few non-null sample rows for those
    show = list(dict.fromkeys((date_like[:1] + home_like[:1] + away_like[:1] + spread_like[:1] + total_like[:1] + ml_like[:2])))
    if show:
        print(df[show].head(5).to_string(index=False))

for c in candidates:
    fp = p.Path(c)
    if fp.exists() and fp.stat().st_size>0:
        sniff(str(fp))
    else:
        print(f"[skip-missing] {c}")

