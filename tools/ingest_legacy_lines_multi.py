#!/usr/bin/env python
import re, sys, argparse
from pathlib import Path
import pandas as pd
import numpy as np

# ---------- regex helpers ----------
NUM_RE = re.compile(r'(-?\d+(?:\.\d+)?)')
PK_RE  = re.compile(r'\bP(?:K|k)\b')

# Headings (multiple styles):
HDRS = [
    re.compile(r'Closing\s+NFL\s+Lines(?:\s+From)?\s+Week\s+(\d{1,2})[, ]+\s*(20\d{2})', re.IGNORECASE),
    re.compile(r'Closing\s+NFL\s+Lines\s*[–-]\s*Week\s+(\d{1,2})\s*\(?\s*(20\d{2})\s*\)?', re.IGNORECASE),
    re.compile(r'\bWeek\s+(\d{1,2})[, ]+\s*(20\d{2})\b', re.IGNORECASE),
]

# ---------- team canon (expandable) ----------
TEAMS = {
 "49ers":"49ers","San Francisco":"49ers","SF":"49ers",
 "Bears":"Bears","Chicago":"Bears","CHI":"Bears",
 "Bengals":"Bengals","Cincinnati":"Bengals","CIN":"Bengals",
 "Bills":"Bills","Buffalo":"Bills","BUF":"Bills",
 "Broncos":"Broncos","Denver":"Broncos","DEN":"Broncos",
 "Browns":"Browns","Cleveland":"Browns","CLE":"Browns",
 "Buccaneers":"Buccaneers","Tampa Bay":"Buccaneers","TB":"Buccaneers","Tampa":"Buccaneers",
 "Cardinals":"Cardinals","Arizona":"Cardinals","ARI":"Cardinals","St. Louis Cardinals":"Cardinals",
 "Chargers":"Chargers","LA Chargers":"Chargers","Los Angeles Chargers":"Chargers","San Diego":"Chargers","SD":"Chargers","LAC":"Chargers",
 "Chiefs":"Chiefs","Kansas City":"Chiefs","KC":"Chiefs",
 "Colts":"Colts","Indianapolis":"Colts","IND":"Colts",
 "Commanders":"Commanders","Washington":"Commanders","WAS":"Commanders","WSH":"Commanders","Redskins":"Commanders",
 "Cowboys":"Cowboys","Dallas":"Cowboys","DAL":"Cowboys",
 "Dolphins":"Dolphins","Miami":"Dolphins","MIA":"Dolphins",
 "Eagles":"Eagles","Philadelphia":"Eagles","PHI":"Eagles",
 "Falcons":"Falcons","Atlanta":"Falcons","ATL":"Falcons",
 "Giants":"Giants","NY Giants":"Giants","New York Giants":"Giants","NYG":"Giants",
 "Jaguars":"Jaguars","Jacksonville":"Jaguars","JAX":"Jaguars",
 "Jets":"Jets","NY Jets":"Jets","New York Jets":"Jets","NYJ":"Jets",
 "Lions":"Lions","Detroit":"Lions","DET":"Lions",
 "Packers":"Packers","Green Bay":"Packers","GB":"Packers","Pack":"Packers",
 "Panthers":"Panthers","Carolina":"Panthers","CAR":"Panthers",
 "Patriots":"Patriots","New England":"Patriots","NE":"Patriots","NWE":"Patriots",
 "Raiders":"Raiders","Las Vegas":"Raiders","Oakland":"Raiders","OAK":"Raiders","LV":"Raiders",
 "Rams":"Rams","LA Rams":"Rams","Los Angeles Rams":"Rams","St. Louis":"Rams","Saint Louis":"Rams","LAR":"Rams",
 "Ravens":"Ravens","Baltimore":"Ravens","BAL":"Ravens",
 "Saints":"Saints","New Orleans":"Saints","NO":"Saints","NOR":"Saints",
 "Seahawks":"Seahawks","Seattle":"Seahawks","SEA":"Seahawks",
 "Steelers":"Steelers","Pittsburgh":"Steelers","PIT":"Steelers",
 "Texans":"Texans","Houston":"Texans","HOU":"Texans",
 "Titans":"Titans","Tennessee":"Titans","TEN":"Titans",
 "Vikings":"Vikings","Minnesota":"Vikings","MIN":"Vikings","Vikes":"Vikings",
}

def _canon(name: str):
    if not name: return None
    name = name.strip()
    name = re.sub(r'^(At\s+|at\s+)', '', name)
    return TEAMS.get(name, name)

def _to_float(x):
    if x is None: return None
    s = str(x)
    if PK_RE.search(s): return 0.0
    m = NUM_RE.search(s)
    return float(m.group(1)) if m else None

# ---------- per-block parsing ----------
def parse_block(lines, season:int, week:int) -> pd.DataFrame:
    """
    Accepts either:
      A) one line with 5 tab-separated columns:
         Date/Time \t Favorite \t Line \t Underdog \t Total
      B) 5-line blocks (date/time, favorite, line, underdog, total)
    """
    rows = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Try tabbed 5-col first
        parts = [p.strip() for p in line.split('\t') if p.strip()]
        if len(parts) < 5:
            # fallback: split by 2+ spaces
            parts = re.split(r'\s{2,}', line.strip())
        if len(parts) >= 5:
            dt, fav, ln, dog, tot = parts[:5]
            if fav and dog and (NUM_RE.search(ln) or PK_RE.search(ln)):
                fav_c = _canon(fav); dog_c = _canon(dog)
                ln_v  = _to_float(ln);  tot_v = _to_float(tot)
                fav_is_home = fav.lower().startswith("at ")
                dog_is_home = dog.lower().startswith("at ")
                if fav_is_home and not dog_is_home:
                    home, away = fav_c, dog_c; spread_home = -ln_v if ln_v is not None else None
                elif dog_is_home and not fav_is_home:
                    home, away = dog_c, fav_c; spread_home = ln_v if ln_v is not None else None
                else:
                    home, away = dog_c, fav_c; spread_home = ln_v if ln_v is not None else None

                rows.append({"season":season,"week":week,"home":home,"away":away,
                             "spread_close":spread_home,"total_close":tot_v})
                i += 1
                continue

        # Try 5-line block
        if i + 4 < len(lines):
            fav   = lines[i+1] if lines[i+1] else ""
            ln    = lines[i+2] if lines[i+2] else ""
            dog   = lines[i+3] if lines[i+3] else ""
            tot   = lines[i+4] if lines[i+4] else ""
            if fav and dog and (NUM_RE.search(ln) or PK_RE.search(ln)):
                fav_c = _canon(fav); dog_c = _canon(dog)
                ln_v  = _to_float(ln);  tot_v = _to_float(tot)
                fav_is_home = fav.lower().startswith("at ")
                dog_is_home = dog.lower().startswith("at ")
                if fav_is_home and not dog_is_home:
                    home, away = fav_c, dog_c; spread_home = -ln_v if ln_v is not None else None
                elif dog_is_home and not fav_is_home:
                    home, away = dog_c, fav_c; spread_home = ln_v if ln_v is not None else None
                else:
                    home, away = dog_c, fav_c; spread_home = ln_v if ln_v is not None else None

                rows.append({"season":season,"week":week,"home":home,"away":away,
                             "spread_close":spread_home,"total_close":tot_v})
                i += 5
                continue

        i += 1

    df = pd.DataFrame(rows)
    if df.empty: return df
    for c in ["season","week"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in ["spread_close","total_close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["home"].notna() & df["away"].notna()]
    df = df.drop_duplicates(subset=["season","week","home","away"])
    return df

# ---------- multi-heading sweep ----------
def find_headings(lines):
    """Return list of (index, week, season)."""
    hits = []
    for i, l in enumerate(lines):
        for rx in HDRS:
            m = rx.search(l)
            if m:
                week = int(m.group(1))
                season = int(m.group(2))
                hits.append((i, week, season))
                break
    return hits

def parse_multi(text: str) -> pd.DataFrame:
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    idx = find_headings(lines)
    if not idx:
        return pd.DataFrame()

    # add sentinel end
    idx.append((len(lines), None, None))
    dfs = []
    for (start, week, season), (end, _, __) in zip(idx, idx[1:]):
        block = lines[start:end]
        # skip the heading line itself
        df = parse_block(block[1:], season, week)
        if not df.empty:
            dfs.append(df)

    if not dfs:
        return pd.DataFrame()
    out = pd.concat(dfs, ignore_index=True)
    out = out.drop_duplicates(subset=["season","week","home","away"]).sort_values(["season","week","home","away"])
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--txt", required=True, help="Path to legacy closing-lines .txt containing many weeks/years")
    args = ap.parse_args()

    txt = Path(args.txt).read_text(encoding="utf-8", errors="ignore")
    df = parse_multi(txt)
    if df.empty:
        print("[warn] no rows parsed"); sys.exit(0)

    dest = Path("exports/historical_odds_oddsshark.csv")
    if dest.exists():
        old = pd.read_csv(dest)
        df = pd.concat([old, df], ignore_index=True)

    df = df.drop_duplicates(subset=["season","week","home","away"]).sort_values(["season","week","home","away"])
    df.to_csv(dest, index=False)
    print(f"[write] {dest} rows={len(df)}")

if __name__ == "__main__":
    main()

