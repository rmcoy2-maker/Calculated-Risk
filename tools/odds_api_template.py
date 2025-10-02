
"""
tools/odds_api_template.py
Provider-agnostic odds-history puller that writes exports/odds_history.csv

Fill in YOUR API base URL, key, and route specifics in _fetch_page().
This template supports incremental backfills by date, with simple retry.
"""
from __future__ import annotations
import csv, os, time, math, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Dict, Any, List, Optional
import json

# --------- CONFIG ---------
API_BASE   = os.environ.get("ODDS_API_BASE",   "https://YOUR_ODDS_API")
API_KEY    = os.environ.get("ODDS_API_KEY",    "REPLACE_ME")
SPORT      = os.environ.get("ODDS_SPORT",      "americanfootball_nfl")
MARKETS    = os.environ.get("ODDS_MARKETS",    "h2h,spreads,totals")  # comma list
BOOKS      = os.environ.get("ODDS_BOOKS",      "")                     # blank = all
DAYS_BACK  = int(os.environ.get("ODDS_DAYS_BACK", "3650"))             # 10 years default
SLEEP_S    = float(os.environ.get("ODDS_SLEEP_S", "0.8"))
OUT_PATH   = Path(os.environ.get("ODDS_OUT", str(Path(__file__).resolve().parents[1] / "exports" / "odds_history.csv")))

# CSV schema we write
CSV_FIELDS = [
    "_date_iso","game_id","home","away","market_norm","side_norm","line","odds","book",
    "source","pulled_ts"
]

def _today_utc() -> datetime:
    return datetime.now(timezone.utc)

def _daterange(start: datetime, end: datetime) -> Iterable[datetime]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)

def _fetch_page(date: datetime) -> List[Dict[str, Any]]:
    """
    TODO: implement YOUR provider fetch here. Return a list of rows with keys matching CSV_FIELDS.
    The template below shows the structure; replace with real HTTP requests & parsing.
    """
    # Example (mock) — replace with requests.get(...) + parsing
    # rows = []
    # r = requests.get(f"{API_BASE}/odds?key={API_KEY}&sport={SPORT}&date={date:%Y-%m-%d}&markets={MARKETS}&books={BOOKS}")
    # for game in r.json()["data"]:
    #   ...
    # return rows
    return []

def _write_rows(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not exists:
            w.writeheader()
        for r in rows:
            # ensure order/type
            out = {k: r.get(k, "") for k in CSV_FIELDS}
            w.writerow(out)

def backfill(days_back: int = DAYS_BACK) -> Path:
    end = _today_utc().date()
    start = end - timedelta(days=days_back)
    n_total = 0
    for d in _daterange(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
                        datetime.combine(end,   datetime.min.time(), tzinfo=timezone.utc)):
        try:
            rows = _fetch_page(d)
            if rows:
                _write_rows(OUT_PATH, rows)
                n_total += len(rows)
        except Exception as e:
            print(f"[warn] {d.date()} failed: {e}", file=sys.stderr)
        time.sleep(SLEEP_S)
    print(f"[done] wrote {n_total} rows → {OUT_PATH}")
    return OUT_PATH

if __name__ == "__main__":
    backfill()
