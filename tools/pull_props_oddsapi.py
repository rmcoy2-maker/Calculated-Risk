from __future__ import annotations
import os, sys, time
from pathlib import Path
from datetime import datetime, timezone
import requests, pandas as pd

API_KEY = os.getenv("THE_ODDS_API_KEY")
SPORT   = os.getenv("PROPS_SPORT", "americanfootball_nfl")
REGIONS = os.getenv("PROPS_REGIONS", "us")
ODDSFMT = os.getenv("PROPS_ODDS_FORMAT", "american")

# Pick your targets; we'll auto-intersect per event
MARKETS = os.getenv("PROPS_MARKETS",
    "player_pass_yds,player_pass_tds,player_rush_yds,player_rec_yds,player_anytime_td"
).split(",")

EXP = Path(os.environ.get("EDGE_EXPORTS_DIR","") or Path(__file__).resolve().parents[1] / "exports")
EXP.mkdir(parents=True, exist_ok=True)
DEST_ROLL = EXP / "props_odds_all.csv"        # rolling store

S = requests.Session()

def _events():
    r = S.get(f"https://api.the-odds-api.com/v4/sports/{SPORT}/events",
              params={"apiKey": API_KEY, "daysFrom": 5}, timeout=30)
    r.raise_for_status()
    return r.json()

def _event_markets(event_id: str) -> set[str]:
    # Discover which market keys exist for this event in this region
    r = S.get(f"https://api.the-odds-api.com/v4/sports/{SPORT}/events/{event_id}/markets",
              params={"apiKey": API_KEY, "regions": REGIONS}, timeout=30)
    if r.status_code == 404:
        return set()
    r.raise_for_status()
    data = r.json() or []
    # Response is list of {key: "<market_key>", ...}
    keys = {m.get("key") for m in data if isinstance(m, dict) and "key" in m}
    return {k for k in keys if k}

def _event_props(event_id: str, markets: list[str]):
    # request only the markets that actually exist for this event
    r = S.get(f"https://api.the-odds-api.com/v4/sports/{SPORT}/events/{event_id}/odds",
              params={"apiKey": API_KEY, "regions": REGIONS, "oddsFormat": ODDSFMT, "markets": ",".join(markets)},
              timeout=30)
    if r.status_code == 404:
        return None
    if r.status_code == 422:
        # return None so caller can skip; useful when a market becomes unavailable mid-loop
        return None
    r.raise_for_status()
    return r.json()

def _flatten(event, payload):
    rows = []
    if not payload:
        return rows
    kickoff = event.get("commence_time")
    game_id = event.get("id")
    captured_at = datetime.now(timezone.utc).isoformat()
    for bk in payload.get("bookmakers", []):
        book = bk.get("title") or bk.get("key")
        for m in bk.get("markets", []):
            market_key = m.get("key")  # e.g., player_pass_yds
            for o in m.get("outcomes", []):
                side = (o.get("name") or o.get("label") or "").upper()
                if "OVER" in side: side = "OVER"
                elif "UNDER" in side: side = "UNDER"
                rows.append({
                    "captured_at": captured_at,
                    "kickoff": kickoff,
                    "game_id": game_id,
                    "book": (book or "").strip(),
                    "player_name": (o.get("description") or o.get("name") or o.get("player") or "").strip(),
                    "team": (o.get("team") or "").strip(),
                    "stat": market_key,
                    "market": "PLAYER_TOTAL",
                    "side": side if side in ("OVER","UNDER","YES","NO") else "",
                    "line": o.get("point"),
                    "odds": o.get("price") or o.get("odds"),
                })
    return rows

def main():
    if not API_KEY:
        print("Missing THE_ODDS_API_KEY"); sys.exit(2)
    evs = _events()
    all_rows = []
    for ev in evs:
        ev_id = ev.get("id")
        if not ev_id: continue
        # discover available markets for this event, then intersect with our desired list
        avail = _event_markets(ev_id)
        want  = [m for m in MARKETS if m in avail]
        if not want:
            continue
        data = _event_props(ev_id, want)
        rows = _flatten(ev, data)
        if rows:
            all_rows.extend(rows)
        time.sleep(0.2)  # gentle pacing
    if not all_rows:
        print("[props] no rows fetched (markets may not be listed yet for upcoming games)"); return
    df = pd.DataFrame(all_rows)
    # normalize
    df["captured_at"] = pd.to_datetime(df["captured_at"], errors="coerce", utc=True)
    df["kickoff"]     = pd.to_datetime(df["kickoff"], errors="coerce", utc=True)
    df["line"]        = pd.to_numeric(df["line"], errors="coerce")
    df["odds"]        = pd.to_numeric(df["odds"], errors="coerce")
    for c in ["book","player_name","team","stat","market","side","game_id"]:
        df[c] = df[c].astype("string").str.strip()
    # append to rolling
    header = not DEST_ROLL.exists() or DEST_ROLL.stat().st_size == 0
    df.to_csv(DEST_ROLL, mode="a", header=header, index=False)
    print(f"[props] wrote {len(df)} rows; appended -> {DEST_ROLL}")

if __name__ == "__main__":
    main()
