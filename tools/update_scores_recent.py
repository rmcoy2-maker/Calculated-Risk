from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import requests, pandas as pd, numpy as np

API_BASE = "https://api.the-odds-api.com"
API_KEY  = "109093b594be16dcc337624f7202c318"
SPORT    = "americanfootball_nfl"

ROOT = Path(__file__).resolve().parents[1]
BASE_SCORES = ROOT / "exports" / "scores_normalized_std_maxaligned.csv"
OUT_SCORES  = ROOT / "exports" / "scores_1966-2025.csv"
DAYS_FROM   = 3  # safe for free/basic plan

def _nick(s: pd.Series) -> pd.Series:
    s = s.astype("string").fillna("").str.upper()
    s = s.str.replace(r"[^A-Z0-9 ]+","", regex=True).str.strip()
    return s.str.replace(r"\s+", "_", regex=True)

def fetch_recent_scores(days_from: int) -> pd.DataFrame:
    url = f"{API_BASE}/v4/sports/{SPORT}/scores"
    params = {"apiKey": API_KEY, "daysFrom": str(int(days_from)), "dateFormat": "iso"}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected response: {data}")

    rows = []
    for ev in data:
        gid   = ev.get("id")
        home  = ev.get("home_team") or ""
        away  = ev.get("away_team") or ""
        comp  = (ev.get("commence_time") or "")[:10]

        home_score, away_score = None, None
        scores_list = ev.get("scores") or []
        for s in scores_list:
            name = (s.get("name") or "").upper()
            if name == home.upper():
                home_score = s.get("score")
            elif name == away.upper():
                away_score = s.get("score")

        if home_score is None: home_score = ev.get("home_score")
        if away_score is None: away_score = ev.get("away_score")

        # Normalize to numbers (convert to float, allow NaN)
        hs = pd.to_numeric(home_score, errors="coerce")
        as_ = pd.to_numeric(away_score, errors="coerce")

        # Ensure both are floats (so NaN is possible)
        hs = float(hs) if hs is not None and not pd.isna(hs) else np.nan
        as_ = float(as_) if as_ is not None and not pd.isna(as_) else np.nan

        total_points = hs + as_ if (pd.notna(hs) and pd.notna(as_)) else np.nan


        status_raw = str(ev.get("status") or ev.get("completed") or "").lower()
        is_final = (ev.get("completed") is True) or ("final" in status_raw)

        rows.append({
            "_date_iso": comp,
            "home": home,
            "away": away,
            "home_score": hs,
            "away_score": as_,
            "total_points": total_points,
            "season": pd.to_datetime(comp, errors="coerce").year if comp else pd.NA,
            "week": pd.NA,
            "status": "final" if is_final else status_raw,
            "game_id": gid,
        })

    df = pd.DataFrame(rows)
    df["_home_nick"] = _nick(df["home"])
    df["_away_nick"] = _nick(df["away"])
    return df

def main():
    base = pd.read_csv(BASE_SCORES) if BASE_SCORES.exists() else pd.DataFrame()
    recent = fetch_recent_scores(DAYS_FROM)
    # merge + dedupe logic...
    # (keep the clean version we wrote before)
    ...

if __name__ == "__main__":
    main()
