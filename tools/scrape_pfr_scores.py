#!/usr/bin/env python
import time, random, re
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

# --- polite fetch with browser-y headers + basic retry ---
def fetch(url: str, tries: int = 5, sleep_base: float = 1.25) -> str:
    ses = requests.Session()
    ses.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/122.0.0.0 Safari/537.36"),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
        "Cache-Control": "no-cache",
    })
    last = None
    for i in range(tries):
        r = ses.get(url, timeout=30)
        last = r
        if r.status_code == 200:
            return r.text
        if r.status_code in (403, 429, 502, 503):
            time.sleep(sleep_base + i*0.75 + random.random())
            continue
        r.raise_for_status()
    raise requests.HTTPError(f"{last.status_code} fetching {url}")

# --- normalize team names a bit to align with your odds/backtest ---
NFL_ALIASES = {
    "49ers": ["49ers","san francisco 49ers","san francisco","sf","sfo","niners"],
    "Bears": ["bears","chicago bears","chicago","chi"],
    "Bengals": ["bengals","cincinnati bengals","cincinnati","cin"],
    "Bills": ["bills","buffalo bills","buffalo","buf"],
    "Broncos": ["broncos","denver broncos","denver","den"],
    "Browns": ["browns","cleveland browns","cleveland","cle"],
    "Buccaneers": ["buccaneers","tampa bay buccaneers","tampa bay","tb","tampa","bucs"],
    "Cardinals": ["cardinals","arizona cardinals","arizona","ari","cards","st. louis cardinals","phoenix cardinals"],
    "Chargers": ["chargers","los angeles chargers","la chargers","lac","san diego chargers","san diego","sd"],
    "Chiefs": ["chiefs","kansas city chiefs","kansas city","kc"],
    "Colts": ["colts","indianapolis colts","indianapolis","ind","baltimore colts"],
    "Commanders": ["commanders","washington commanders","washington","wsh","was","redskins","football team"],
    "Cowboys": ["cowboys","dallas cowboys","dallas","dal"],
    "Dolphins": ["dolphins","miami dolphins","miami","mia"],
    "Eagles": ["eagles","philadelphia eagles","philadelphia","phi"],
    "Falcons": ["falcons","atlanta falcons","atlanta","atl"],
    "Giants": ["giants","new york giants","ny giants","nyg"],
    "Jaguars": ["jaguars","jacksonville jaguars","jacksonville","jax","jags"],
    "Jets": ["jets","new york jets","ny jets","nyj"],
    "Lions": ["lions","detroit lions","detroit","det"],
    "Packers": ["packers","green bay packers","green bay","gb"],
    "Panthers": ["panthers","carolina panthers","carolina","car"],
    "Patriots": ["patriots","new england patriots","new england","ne","nwe","boston patriots"],
    "Raiders": ["raiders","las vegas raiders","las vegas","lv","oakland raiders","oakland","oak","la raiders","los angeles raiders"],
    "Rams": ["rams","los angeles rams","la rams","lar","st. louis rams","st louis rams","los angeles rams (1946–1994)"],
    "Ravens": ["ravens","baltimore ravens","baltimore","bal"],
    "Saints": ["saints","new orleans saints","new orleans","no","nor"],
    "Seahawks": ["seahawks","seattle seahawks","seattle","sea"],
    "Steelers": ["steelers","pittsburgh steelers","pittsburgh","pit"],
    "Texans": ["texans","houston texans","houston","hou"],
    "Titans": ["titans","tennessee titans","tennessee","ten","houston oilers","tennessee oilers","oilers"],
    "Vikings": ["vikings","minnesota vikings","minnesota","min"],
}
ALIAS_TO_TEAM = {a.lower(): canon for canon, aliases in NFL_ALIASES.items() for a in aliases}

def teamify(x: str):
    t = (x or "").strip().lower()
    if not t: return None
    # direct alias substring (PFR uses full names; substring is ok)
    matches = [ALIAS_TO_TEAM[a] for a in ALIAS_TO_TEAM if a in t]
    if len(set(matches)) == 1:
        return matches[0]
    # last-resort: titlecase word
    tt = re.sub(r"[^\w\s]", " ", t)
    words = {w for w in tt.split() if len(w) > 2}
    for canon, aliases in NFL_ALIASES.items():
        if any(a in words for a in aliases):
            return canon
    return x  # keep original if unsure

def parse_season(season: int):
    url = f"https://www.pro-football-reference.com/years/{season}/games.htm"
    html = fetch(url)
    # PFR tables load without JS; read_html works fine if we pass a buffer
    tables = pd.read_html(StringIO(html))
    # find the schedule-like table: must contain Winner/tie & Loser/tie
    sched = None
    for t in tables:
        cols = [c.lower() for c in map(str, t.columns)]
        if any("winner/tie" in c for c in cols) and any("loser/tie" in c for c in cols):
            sched = t
            break
    if sched is None:
        return pd.DataFrame()

    # unify column names we care about
    # Typical columns: Week, Day, Date, Time, Winner/tie, at, Loser/tie, PtsW, PtsL, ...
    ren = {}
    for c in sched.columns:
        cl = str(c).lower()
        if cl.startswith("winner"): ren[c] = "winner"
        elif cl.startswith("loser"): ren[c] = "loser"
        elif cl == "ptsw": ren[c] = "ptsw"
        elif cl == "ptsl": ren[c] = "ptsl"
        elif cl.strip() == "at": ren[c] = "at"
        elif cl.startswith("date"): ren[c] = "date"
        elif cl.startswith("week"): ren[c] = "week_label"
    sched = sched.rename(columns=ren)

    # drop playoff rows if you only want regular season for now (optional)
    # PFR labels weeks like "Week 1" ... "Week 17/18", and playoff rounds as "Wildcard", etc.
    # Keep everything; you can filter later by week_label.

    # derive home/away from "at" (if '@', winner was away)
    def home_away(row):
        if str(row.get("at")) == "@":
            away = teamify(row.get("winner"))
            home = teamify(row.get("loser"))
            awa_pts = row.get("ptsw")
            hom_pts = row.get("ptsl")
        else:
            home = teamify(row.get("winner"))
            away = teamify(row.get("loser"))
            hom_pts = row.get("ptsw")
            awa_pts = row.get("ptsl")
        return pd.Series({
            "home": home, "away": away,
            "home_score": pd.to_numeric(hom_pts, errors="coerce"),
            "away_score": pd.to_numeric(awa_pts, errors="coerce"),
        })

    core = sched.assign(season=season)
    core[["home","away","home_score","away_score"]] = core.apply(home_away, axis=1)
    # parse date (drop rows with NaT date if PFR has non-game rows)
    core["date"] = pd.to_datetime(core.get("date"), errors="coerce").dt.date

    keep_cols = ["season","date","week_label","home","away","home_score","away_score"]
    out = core[keep_cols].dropna(subset=["home","away"])
    # Deduplicate just in case
    out = out.drop_duplicates(subset=["season","date","home","away","home_score","away_score"])
    return out

def main():
    exports = Path("exports"); exports.mkdir(exist_ok=True)
    rows = []
    for season in range(1966, 2025):  # adjust upper bound as needed
        try:
            df = parse_season(season)
            print(f"[ok] {season} rows={len(df)}")
            rows.append(df)
            # be kind to PFR
            time.sleep(0.75 + random.random()*0.6)
        except Exception as e:
            print(f"[err] {season} -> {e}")

    if not rows:
        print("[warn] no rows scraped")
        return

    all_ = pd.concat(rows, ignore_index=True)
    all_.to_csv(exports / "pfr_scores_1966_2024.csv", index=False)
    print(f"[write] exports/pfr_scores_1966_2024.csv rows={len(all_)}")

if __name__ == "__main__":
    main()

