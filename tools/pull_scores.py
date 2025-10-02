# tools/pull_scores.py
from __future__ import annotations
import os, json
from pathlib import Path
from datetime import datetime, timezone
import requests
import pandas as pd

SPORT_KEY = "americanfootball_nfl"  # adjust if you add other leagues
API_KEY   = os.getenv("109093b594be16dcc337624f7202c318")  # set in env or .streamlit/secrets.toml

def exports_dir() -> Path:
    env = os.environ.get("EDGE_EXPORTS_DIR", "").strip()
    if env:
        p = Path(env); p.mkdir(parents=True, exist_ok=True); return p
    here = Path(__file__).resolve()
    for up in [here.parent] + list(here.parents):
        if up.name.lower() == "edge-finder":
            p = up / "exports"; p.mkdir(parents=True, exist_ok=True); return p
    return here.parent

def fetch_scores(days_from: int = 3) -> pd.DataFrame:
    if not API_KEY:
        raise RuntimeError("Set THE_ODDS_API_KEY in environment or secrets.")
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/scores"
    params = {"apiKey": API_KEY, "daysFrom": days_from, "dateFormat": "iso"}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    # Normalize
    recs = []
    for g in data:
        # expected keys: commence_time, completed, scores: [{name, score}, ...]
        ct = g.get("commence_time")
        teams = [s.get("name","") for s in g.get("scores", [])]
        vals  = [s.get("score") for s in g.get("scores", [])]
        # Try to map home/away from whatever you store in edges (you may already have this mapping)
        home = g.get("home_team") or (teams[1] if len(teams)==2 else "")
        away = g.get("away_team") or (teams[0] if len(teams)==2 else "")
        try:
            hs = float(vals[1]) if len(vals)==2 else None
            as_ = float(vals[0]) if len(vals)==2 else None
        except Exception:
            hs = as_ = None

        recs.append({
            "_date_iso": ct[:10] if isinstance(ct,str) else None,
            "commence_time": ct,
            "home": home, "away": away,
            "home_score": hs, "away_score": as_,
            "game_id": g.get("id", ""),
        })
    return pd.DataFrame(recs)

def nickify(s: pd.Series) -> pd.Series:
    return s.astype("string").str.upper().str.replace(r"[^A-Z0-9 ]+","",regex=True).str.strip().str.replace(r"\s+","_",regex=True)

def synth_gid(df: pd.DataFrame) -> pd.Series:
    date = pd.to_datetime(df["_date_iso"], errors="coerce").dt.date.astype("string")
    return date + "::" + nickify(df["away"]) + "@" + nickify(df["home"])

def main():
    EXP = exports_dir()
    dest = EXP / "scores_1966-2025.csv"          # your legacy rollup
    live = EXP / "scores_live.csv"               # rolling window
    norm = EXP / "scores_normalized_std_maxaligned.csv"  # your normalized source

    live_df = fetch_scores(days_from=5)
    if live_df.empty:
        print("[live] no rows")
        return
    live_df["_gid"] = synth_gid(live_df)

    # Start from the best foundation available
    base = None
    if norm.exists():
        base = pd.read_csv(norm)
    elif dest.exists():
        base = pd.read_csv(dest)
    else:
        base = pd.DataFrame()

    # Normalize base into canonical columns and _gid
    if not base.empty:
        if "_date_iso" not in base.columns and "Date" in base.columns:
            base["_date_iso"] = pd.to_datetime(base["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
        if "_gid" not in base.columns:
            away = base.get("_away_nick", base.get("_AwayNick","")).astype(str)
            home = base.get("_home_nick", base.get("_HomeNick","")).astype(str)
            base["_gid"] = pd.to_datetime(base["_date_iso"], errors="coerce").dt.date.astype("string") + "::" + away.str.upper().str.replace(r"\\s+","_",regex=True) + "@" + home.str.upper().str.replace(r"\\s+","_",regex=True)

    # Merge and de-dup by _gid (prefer freshest non-null scores from live)
    merged = pd.concat([base, live_df], ignore_index=True, sort=False)
    merged = merged.sort_values(["_gid"]).drop_duplicates("_gid", keep="last")

    # Write files
    live_df.to_csv(live, index=False)
    merged.to_csv(dest, index=False)
    print(f"[live] wrote {live} ({len(live_df)})  |  [rollup] wrote {dest} ({len(merged)})")

if __name__ == "__main__":
    main()
