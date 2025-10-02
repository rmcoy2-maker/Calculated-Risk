# -*- coding: utf-8 -*-
"""
pull_odds_and_props.py — consolidated fetcher for game lines & player props (The Odds API v4 style)
Requires env var THE_ODDS_API_KEY.
Writes:
  exports/odds_lines_all.csv
  exports/odds_props_all.csv
"""
from __future__ import annotations
import os, sys, time, json, math
from pathlib import Path
from typing import Iterable, Dict, Any, List, Optional
import argparse
import csv
import datetime as dt
import urllib.request
import urllib.parse

API_BASE = "https://api.the-odds-api.com/v4"

def _get_api_key() -> str:
    k = os.environ.get("THE_ODDS_API_KEY", "").strip()
    if not k:
        print("ERROR: THE_ODDS_API_KEY not set.", file=sys.stderr)
        sys.exit(2)
    return k

def _http_get(url: str, params: Dict[str, Any], retries: int = 3, backoff: float = 1.5) -> Any:
    """Basic GET with exponential backoff + JSON parse."""
    q = urllib.parse.urlencode({k: (",".join(v) if isinstance(v, list) else v) for k, v in params.items() if v is not None})
    full = f"{url}?{q}" if q else url
    last_err = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(full, timeout=30) as r:
                b = r.read()
                return json.loads(b.decode("utf-8"))
        except Exception as e:
            last_err = e
            time.sleep(backoff * (2 ** i))
    raise last_err

def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)

def _write_csv(path: Path, rows: Iterable[Dict[str, Any]], header: List[str]) -> None:
    _ensure_dir(path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

def _normalize_price_to_decimal(price_american: Optional[float]) -> Optional[float]:
    if price_american is None: return None
    try:
        p = float(price_american)
    except Exception:
        return None
    if p > 0:
        return 1.0 + (p / 100.0)
    elif p < 0:
        return 1.0 + (100.0 / abs(p))
    return 1.0

def list_sports(api_key: str) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/sports"
    return _http_get(url, {"apiKey": api_key})

def list_events(api_key: str, sport_key: str, regions: str = "us", odds_market: str = "h2h") -> List[Dict[str, Any]]:
    # Not all APIs expose a top-level events list; Odds API uses /odds for upcoming events
    url = f"{API_BASE}/sports/{sport_key}/odds"
    data = _http_get(url, {"apiKey": api_key, "regions": regions, "markets": odds_market})
    return data if isinstance(data, list) else []

def fetch_lines(api_key: str, sport_key: str, regions: str, markets: List[str], bookmakers: Optional[List[str]]) -> List[Dict[str, Any]]:
    """Pulls odds lines for multiple markets (e.g., h2h, spreads, totals)"""
    url = f"{API_BASE}/sports/{sport_key}/odds"
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": ",".join(markets),
        "bookmakers": ",".join(bookmakers) if bookmakers else None,
    }
    data = _http_get(url, params)
    if not isinstance(data, list):
        return []
    rows: List[Dict[str, Any]] = []
    now_iso = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    for ev in data:
        event_id = ev.get("id")
        commence = ev.get("commence_time")
        home = ev.get("home_team")
        away = ev.get("away_team")
        for book in ev.get("bookmakers", []):
            book_key = book.get("key")
            for mk in book.get("markets", []):
                mkt_key = mk.get("key")  # h2h, spreads, totals
                last_upd = mk.get("last_update")
                outcomes = mk.get("outcomes", [])
                # For spreads & totals we may have line/point; for h2h we only have price.
                for oc in outcomes:
                    side = oc.get("name")  # e.g., home/away/team name/over/under
                    price = oc.get("price")
                    point = oc.get("point")  # spread/total line
                    rows.append({
                        "_fetched_at": now_iso,
                        "event_id": event_id,
                        "sport_key": sport_key,
                        "commence_time": commence,
                        "home": home,
                        "away": away,
                        "book": book_key,
                        "market": mkt_key,
                        "side": side,
                        "line": point,
                        "price_american": price,
                        "price_decimal": _normalize_price_to_decimal(price),
                        "last_update": last_upd,
                    })
    return rows

def fetch_props_for_event(api_key: str, sport_key: str, event_id: str, regions: str, prop_markets: List[str], bookmakers: Optional[List[str]]) -> List[Dict[str, Any]]:
    """
    Fetch props for a single event. Odds API v4 style:
      /sports/{sport}/events/{event_id}/odds?markets=player_points,player_assists,...
    """
    url = f"{API_BASE}/sports/{sport_key}/events/{event_id}/odds"
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": ",".join(prop_markets),
        "bookmakers": ",".join(bookmakers) if bookmakers else None,
    }
    data = _http_get(url, params)
    if not isinstance(data, dict):
        return []
    # data includes bookmakers -> markets -> outcomes similar to lines
    rows: List[Dict[str, Any]] = []
    now_iso = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    for book in data.get("bookmakers", []):
        book_key = book.get("key")
        for mk in book.get("markets", []):
            mkt_key = mk.get("key")  # e.g., player_points, player_pass_yards, etc.
            last_upd = mk.get("last_update")
            for oc in mk.get("outcomes", []):
                rows.append({
                    "_fetched_at": now_iso,
                    "event_id": data.get("id") or event_id,
                    "sport_key": sport_key,
                    "commence_time": data.get("commence_time"),
                    "home": data.get("home_team"),
                    "away": data.get("away_team"),
                    "book": book_key,
                    "market": mkt_key,
                    "player": oc.get("description") or oc.get("name"),
                    "side": oc.get("name"),  # Over/Under or player side
                    "line": oc.get("point"),
                    "price_american": oc.get("price"),
                    "price_decimal": _normalize_price_to_decimal(oc.get("price")),
                    "last_update": last_upd,
                })
    return rows

def fetch_props(api_key: str, sport_key: str, regions: str, prop_markets: List[str], bookmakers: Optional[List[str]], max_events: int = 100) -> List[Dict[str, Any]]:
    # Get upcoming events first (using /odds list as proxy)
    events = list_events(api_key, sport_key, regions=regions, odds_market="h2h")
    rows: List[Dict[str, Any]] = []
    for i, ev in enumerate(events[:max_events]):
        ev_id = ev.get("id")
        if not ev_id:
            continue
        try:
            rows.extend(fetch_props_for_event(api_key, sport_key, ev_id, regions, prop_markets, bookmakers))
            time.sleep(0.25)  # be nice to rate limits
        except Exception as e:
            print(f"[warn] props fetch failed for event {ev_id}: {e}", file=sys.stderr)
            time.sleep(0.5)
    return rows

def main():
    p = argparse.ArgumentParser(description="Fetch game lines and player props into CSVs.")
    p.add_argument("--sport", default="americanfootball_nfl", help="Sport key (e.g., americanfootball_nfl, basketball_nba)")
    p.add_argument("--regions", default="us", help="Comma regions (us, eu, uk, au)")
    p.add_argument("--markets", default="h2h,spreads,totals", help="Markets to pull for lines")
    p.add_argument("--prop-markets", default="player_points,player_pass_yards,player_rush_yards,player_receiving_yards", help="Prop markets to pull")
    p.add_argument("--bookmakers", default="", help="Optional comma list of books (e.g., draftkings,fanduel,betmgm)")
    p.add_argument("--max-events", type=int, default=100, help="Max events for props pull")
    p.add_argument("--out-lines", default="exports/odds_lines_all.csv", help="CSV path for lines")
    p.add_argument("--out-props", default="exports/odds_props_all.csv", help="CSV path for props")
    args = p.parse_args()

    api_key = _get_api_key()
    sport = args.sport
    regions = args.regions
    markets = [m.strip() for m in args.markets.split(",") if m.strip()]
    prop_markets = [m.strip() for m in args.prop_markets.split(",") if m.strip()]
    bookmakers = [b.strip() for b in args.bookmakers.split(",") if b.strip()] if args.bookmakers else None

    print(f"[pull] sport={sport} regions={regions} markets={markets} prop_markets={prop_markets} books={bookmakers}")

    # 1) Lines
    lines = fetch_lines(api_key, sport, regions, markets, bookmakers)
    if lines:
        headers = [
            "_fetched_at","event_id","sport_key","commence_time","home","away",
            "book","market","side","line","price_american","price_decimal","last_update"
        ]
        _write_csv(Path(args.out_lines), lines, headers)
        print(f"[ok] wrote lines: {len(lines):,} rows -> {args.out_lines}")
    else:
        print("[warn] no line rows found.")

    # 2) Props
    props = fetch_props(api_key, sport, regions, prop_markets, bookmakers, max_events=args.max_events)
    if props:
        headers = [
            "_fetched_at","event_id","sport_key","commence_time","home","away",
            "book","market","player","side","line","price_american","price_decimal","last_update"
        ]
        _write_csv(Path(args.out_props), props, headers)
        print(f"[ok] wrote props: {len(props):,} rows -> {args.out_props}")
    else:
        print("[warn] no prop rows found.")

if __name__ == "__main__":
    main()
