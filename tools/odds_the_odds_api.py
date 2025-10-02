# tools/odds_the_odds_api.py
# Pulls historical NFL odds snapshots from The Odds API (v4) and writes exports/odds_history.csv

from __future__ import annotations
import csv
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any

import requests

# ==== YOUR SETTINGS (baked-in per your ask) ====
API_BASE = "https://api.the-odds-api.com"
API_KEY  = "109093b594be16dcc337624f7202c318"
SPORT    = "americanfootball_nfl"       # NFL
REGIONS  = "us"                         # or "us2"
MARKETS  = "h2h,spreads,totals"         # featured markets
ODDS_FMT = "american"                   # prices in +/- American
# Choose snapshot times (UTC). Noon UTC on each game day works well.
SNAP_HOUR_UTC = 16  # 16:00Z ~ 12pm ET (adjust if you want)
SLEEP_S = 0.6       # pause between calls (be polite)

# Output CSV
OUT_PATH = Path(__file__).resolve().parents[1] / "exports" / "odds_history.csv"
OUT_FIELDS = [
    "_date_iso", "game_id", "home", "away",
    "market_norm", "side_norm", "line", "odds", "book",
    "source", "pulled_ts"
]

def _iso_date(dt: datetime) -> str:
    return dt.date().isoformat()

def _to_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def _write_rows(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in OUT_FIELDS})

def fetch_snapshot(dt_utc: datetime) -> List[Dict[str, Any]]:
    """
    Calls v4 historical snapshot for NFL featured markets at or before dt_utc.
    API: /v4/historical/sports/{sport}/odds
    """
    url = f"{API_BASE}/v4/historical/sports/{SPORT}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": ODDS_FMT,
        "date": _to_z(dt_utc),
        "dateFormat": "iso",
    }
    r = requests.get(url, params=params, timeout=40)
    r.raise_for_status()
    payload = r.json()
    data = payload.get("data", payload)  # some SDKs return {"data":[...]} vs raw list
    rows: List[Dict[str, Any]] = []
    pulled_ts = _to_z(dt_utc)

    # Normalize
    def _side_for(mkey: str, name: str, home: str, away: str) -> str:
        name_u = (name or "").upper()
        if mkey == "H2H" or mkey == "SPREADS":
            if name_u in (home.upper(), "HOME"): return "HOME"
            if name_u in (away.upper(), "AWAY"): return "AWAY"
            return name_u
        if mkey == "TOTALS":
            if "OVER" in name_u: return "OVER"
            if "UNDER" in name_u: return "UNDER"
            return name_u
        return name_u

    for ev in data:
        gid  = ev.get("id")
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")
        commence = ev.get("commence_time") or pulled_ts
        game_date = commence[:10] if isinstance(commence, str) else _iso_date(datetime.fromisoformat(str(commence)))
        for bm in ev.get("bookmakers", []):
            book = bm.get("title") or bm.get("key") or ""
            for mk in bm.get("markets", []):
                mkey = (mk.get("key", "") or "").upper()   # 'H2H'/'SPREADS'/'TOTALS'
                if mkey not in ("H2H", "SPREADS", "TOTALS"):
                    continue
                for oc in mk.get("outcomes", []):
                    side = _side_for(mkey, oc.get("name", ""), home, away)
                    price = oc.get("price", None)
                    point = oc.get("point", None)
                    rows.append({
                        "_date_iso": game_date,        # game date
                        "game_id": gid,
                        "home": home, "away": away,
                        "market_norm": mkey, "side_norm": side,
                        "line": point, "odds": price, "book": book,
                        "source": "the-odds-api", "pulled_ts": pulled_ts,
                    })
    return rows

def backfill(from_date: str, to_date: str) -> Path:
    """
    Pull one snapshot per day between [from_date, to_date], inclusive.
    Example dates: "2020-08-01", "2025-02-15"
    """
    start = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc)
    end   = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc)
    total = 0
    dt = start
    while dt <= end:
        snap = dt.replace(hour=SNAP_HOUR_UTC, minute=0, second=0, microsecond=0)
        try:
            rows = fetch_snapshot(snap)
            if rows:
                _write_rows(OUT_PATH, rows)
                total += len(rows)
                print(f"[{_iso_date(snap)}] +{len(rows)} rows")
        except requests.HTTPError as e:
            # Helpful diagnostics (rate limit, etc.)
            print(f"[warn] {_iso_date(snap)} HTTP {e.response.status_code}: {e}", flush=True)
            if e.response is not None:
                try:
                    print(e.response.text[:500], flush=True)
                except Exception:
                    pass
        except Exception as e:
            print(f"[warn] {_iso_date(snap)}: {e}", flush=True)
        time.sleep(SLEEP_S)
        dt += timedelta(days=1)
    print(f"[done] wrote {total} rows → {OUT_PATH}")
    return OUT_PATH

if __name__ == "__main__":
    # Example: pull 2019-07-01 through today (adjust as you like)
    today = datetime.now(timezone.utc).date().isoformat()
    backfill("2019-07-01", today)
