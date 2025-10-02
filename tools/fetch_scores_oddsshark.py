import re, time, argparse
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import pandas as pd

OUT_DIR = Path("exports/scores_oddsshark")
OUT_DIR.mkdir(parents=True, exist_ok=True)

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

def norm_team(x: str) -> str:
    x = x.strip()
    return TEAM_FIX.get(x, x)

def parse_week(season: int, week: int) -> pd.DataFrame:
    # Oddsshark historical results URL pattern (works for regular season & playoffs pages)
    url = f"https://www.oddsshark.com/nfl/scores"
    params = {"season": season, "week": week}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    # Table rows generally contain team names & final score; structure can vary slightly season-to-season.
    rows = []
    for row in soup.select("table tr"):
        cols = [c.get_text(strip=True) for c in row.find_all(["td","th"])]
        if len(cols) < 5: 
            continue
        # Heuristic: [Date, Away, AwayScore, Home, HomeScore, ...]
        # Some seasons swap score positions; try to detect ints
        nums = [re.match(r"^-?\d+$", c) is not None for c in cols]
        if nums.count(True) < 2:
            continue
        # Find two integers as scores
        ints = [(i, int(cols[i])) for i, ok in enumerate(nums) if ok]
        if len(ints) < 2:
            continue
        i1, s1 = ints[0]
        i2, s2 = ints[1]
        # Guess team positions relative to scores
        try:
            away = cols[i1-1]; home = cols[i2-1]
        except IndexError:
            continue
        date = cols[0]
        rows.append({
            "season": season,
            "week": week,
            "date": pd.to_datetime(date, errors="coerce"),
            "away": norm_team(away),
            "home": norm_team(home),
            "away_score": s1,
            "home_score": s2,
            "source": "oddsshark"
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df

def fetch_season(season: int, max_weeks: int = 23, delay: float = 0.8) -> pd.DataFrame:
    frames = []
    for w in range(1, max_weeks+1):
        try:
            dfw = parse_week(season, w)
            if dfw.empty:
                # stop early if we hit a stretch of empty weeks (postseason endings vary)
                if w > 18:
                    break
            frames.append(dfw)
        except Exception as e:
            # tolerate odd pages; continue
            print(f"[warn] season {season} week {w}: {e}")
        time.sleep(delay)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--outdir", type=str, default=str(OUT_DIR))
    args = ap.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    all_frames = []
    for season in range(args.start, args.end+1):
        out_file = outdir / f"nfl_scores_{season}.csv"
        if out_file.exists():
            print(f"[skip] {out_file} exists")
            df = pd.read_csv(out_file)
        else:
            print(f"[fetch] season {season}")
            df = fetch_season(season)
            if df.empty:
                print(f"[warn] season {season} yielded 0 games")
            df.to_csv(out_file, index=False)
        all_frames.append(df)

    all_df = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
    combo = outdir / "nfl_scores_oddsshark_all.csv"
    all_df.to_csv(combo, index=False)
    print(f"[done] wrote {combo} with {len(all_df):,} rows")

if __name__ == "__main__":
    main()

