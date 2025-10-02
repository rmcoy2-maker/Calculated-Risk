import pandas as pd, numpy as np, hashlib, pathlib as p

TEAM_FIX = {
    "St. Louis Rams":"Los Angeles Rams","LA Rams":"Los Angeles Rams",
    "San Diego Chargers":"Los Angeles Chargers","LA Chargers":"Los Angeles Chargers",
    "Washington Redskins":"Washington Commanders","Washington Football Team":"Washington Commanders",
    "Oakland Raiders":"Las Vegas Raiders","Phoenix Cardinals":"Arizona Cardinals","Tennessee Oilers":"Tennessee Titans",
}
def norm_team(x):
    if pd.isna(x): return x
    s = str(x).strip(); return TEAM_FIX.get(s, s)

def parse_dt(df):
    for c in ["date","game_date","start_time","date_utc","gameday","scheduled","kickoff","start_date"]:
        if c in df.columns:
            s = pd.to_datetime(df[c], errors="coerce", utc=True)
            if s.notna().any():
                # make tz-naive UTC for stable keys
                return s.dt.tz_convert("UTC").dt.tz_localize(None)
    return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")

def mk_gid_row(r):
    # only build if we have a date
    if pd.isna(r["_dt"]): return np.nan
    d = r["_dt"].strftime("%Y-%m-%d")
    key = f"{d}|{norm_team(r['home'])}|{norm_team(r['away'])}|NFL"
    return hashlib.md5(key.encode()).hexdigest()[:12]

def coerce_numeric(s):
    return pd.to_numeric(s, errors="coerce")

def load_one(path):
    df = pd.read_csv(path)
    # map common names
    if "home" not in df: 
        for c in ["home_team","team_home"]: 
            if c in df: df["home"]=df[c]; break
    if "away" not in df:
        for c in ["away_team","team_away"]:
            if c in df: df["away"]=df[c]; break
    if "season" not in df:
        for c in ["schedule_season","year"]:
            if c in df: df["season"]=df[c]; break
    if "week" not in df and "schedule_week" in df: df["week"]=df["schedule_week"]

    # closing lines (varies by set)
    for tgt,cands in {
        "spread_close":["spread_close","spread_line","vegas_line","spread_favorite","closing_spread"],
        "total_close" :["total_close","total_line","over_under","over_under_line","closing_total"],
        "ml_home"     :["ml_home","moneyline_home","home_moneyline","home_ml"],
        "ml_away"     :["ml_away","moneyline_away","away_moneyline","away_ml"],
    }.items():
        if tgt not in df:
            for c in cands:
                if c in df: df[tgt]=df[c]; break

    df["_dt"]=parse_dt(df)
    df["home"]=df["home"].map(norm_team) if "home" in df else np.nan
    df["away"]=df["away"].map(norm_team) if "away" in df else np.nan
    # build key only when date/home/away exist
    ok = df["_dt"].notna() & df["home"].notna() & df["away"].notna()
    df = df.loc[ok].copy()
    if df.empty: return df

    df["game_id_unified"]=df.apply(mk_gid_row, axis=1)
    keep = ["game_id_unified","_dt","season","week","home","away","spread_close","total_close","ml_home","ml_away"]
    out = df[[c for c in keep if c in df.columns]].dropna(subset=["game_id_unified"]).drop_duplicates("game_id_unified")
    for c in ["spread_close","total_close","ml_home","ml_away"]: 
        if c in out: out[c]=coerce_numeric(out[c])
    return out

parts=[]
for candidate in [
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
]:
    fp = p.Path(candidate)
    if fp.exists() and fp.stat().st_size>0:
        try:
            part = load_one(fp)
            if not part.empty: parts.append(part)
            else: print(f"[skip-empty] {fp}")
        except Exception as e:
            print(f"[skip] {fp}: {e}")

if not parts:
    raise SystemExit("No usable rows—check that at least one CSV has date+home+away columns populated.")

odds = pd.concat(parts, ignore_index=True).drop_duplicates("game_id_unified")
odds = odds.sort_values("_dt")
odds.drop(columns=["_dt"], inplace=True, errors="ignore")
odds.to_csv("exports/historical_odds.csv", index=False)
print(f"[done] exports/historical_odds.csv rows={len(odds):,}")

