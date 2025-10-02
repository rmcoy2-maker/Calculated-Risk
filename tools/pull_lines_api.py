import os, json, time, csv, sys
from datetime import datetime, timezone
import requests
from pathlib import Path

REPO = Path(r"C:\Projects\edge-finder")
EXPORTS = REPO / "exports"
EXPORTS.mkdir(parents=True, exist_ok=True)
OUT_CSV = EXPORTS / "lines_live.csv"

def get_env(key, default=None):
    v = os.environ.get(key, default)
    # Fallback to .env if present (simple parser)
    if v is None:
        env_path = REPO / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if "=" in line:
                    k, val = line.split("=",1)
                    if k.strip() == key:
                        return val.strip()
    return v

def fetch_odds(api_key, sport="americanfootball_nfl", regions="us", markets=("h2h","spreads","totals")):
    base = "https://api.the-odds-api.com/v4/sports/{sport}/odds"
    rows = []
    for mkt in markets:
        url = base.format(sport=sport)
        params = {
            "apiKey": api_key,
            "regions": regions,
            "markets": mkt,
            "oddsFormat": "american"
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        ts = datetime.now(timezone.utc).isoformat()
        for game in data:
            gid = game.get("id")
            home = game.get("home_team")
            away = game.get("away_team")
            commence = game.get("commence_time")
            for bk in game.get("bookmakers", []):
                bname = bk.get("title")
                for mk in bk.get("markets", []):
                    market_key = mk.get("key")
                    for outc in mk.get("outcomes", []):
                        name = outc.get("name")
                        price = outc.get("price")
                        point = outc.get("point")
                        rows.append({
                            "pulled_ts": ts,
                            "game_id": gid,
                            "commence_time": commence,
                            "home": home,
                            "away": away,
                            "book": bname,
                            "market": market_key,
                            "selection": name,
                            "price_american": price,
                            "point": point
                        })
    return rows

def write_csv(rows, path):
    if not rows:
        # still write header for UI
        header = ["pulled_ts","game_id","commence_time","home","away","book","market","selection","price_american","point"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)
        return
    header = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)

def main():
    api_key = get_env("ODDS_API_KEY")
    if not api_key:
        print("ERROR: ODDS_API_KEY missing. Set environment variable or .env.", file=sys.stderr)
        sys.exit(2)
    try:
        rows = fetch_odds(api_key)
        write_csv(rows, OUT_CSV)
        print(f"Wrote {OUT_CSV} with {len(rows)} rows.")
    except requests.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)
        sys.exit(4)

if __name__ == "__main__":
    main()

