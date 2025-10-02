#!/usr/bin/env python
# normalize_results.py — shape raw picks/graded results for backtest.py
import pandas as pd, numpy as np, os, re
from pathlib import Path

SRC = Path(r"exports/tmp/results_latest.csv")
DST = Path(r"exports/results.csv")

if not SRC.exists():
    raise SystemExit(f"[skip] missing {SRC}")

df = pd.read_csv(SRC)

# --- header aliases: add any you need later ---
ALIAS = {
    "season":    ["season","year"],
    "week":      ["week","wk"],
    "date":      ["date","game_date","kickoff_date"],
    "home":      ["home","home_team","team_home"],
    "away":      ["away","away_team","team_away"],
    "home_score":["home_score","home_pts","home_points","final_home"],
    "away_score":["away_score","away_pts","away_points","final_away"],
    "market":    ["market","bet_type","wager_type","prop_market","category"],
    "line":      ["line","spread","total","number"],
    "side":      ["side","selection","pick","team","team_bet","choice"],
    "result":    ["result","outcome","graded","winloss"],
    "parlay_id": ["parlay_id","slip_id","ticket_id","bet_id"],
    "event_id":  ["event_id","game_id","match_id","fixture_id"],
    "settled":   ["settled","graded_flag","is_settled"],
}

def pick(colname):
    for c in ALIAS[colname]:
        if c in df.columns: return c
    return None

def get(colname, default=np.nan):
    c = pick(colname)
    return df[c] if c else default

# build normalized frame
out = pd.DataFrame({
    "season":      pd.to_numeric(get("season"), errors="coerce"),
    "week":        pd.to_numeric(get("week"), errors="coerce"),
    "date":        pd.to_datetime(get("date"), errors="coerce").dt.date,
    "home":        get("home").astype(str).str.strip() if pick("home") else pd.NA,
    "away":        get("away").astype(str).str.strip() if pick("away") else pd.NA,
    "home_score":  pd.to_numeric(get("home_score"), errors="coerce"),
    "away_score":  pd.to_numeric(get("away_score"), errors="coerce"),
    "market":      get("market").astype(str).str.strip().str.lower() if pick("market") else pd.NA,
    "line":        pd.to_numeric(get("line"), errors="coerce"),
    "side":        get("side").astype(str).str.strip(),
    "result":      get("result"),
    "parlay_id":   get("parlay_id"),
    "event_id":    get("event_id"),
    "settled":     get("settled"),
})

# interpret result (W/L/1/0/True/False) -> win (0/1) when present
r = out["result"].astype(str).str.strip().str.lower()
out["win"] = np.where(r.isin(["w","win","1","true","t"]), 1.0,
               np.where(r.isin(["l","loss","0","false","f"]), 0.0, np.nan))

# team aliasing helper: keep it light (matches backtest style loosely)
NFL_ALIASES = {
    "49ers":["49ers","san francisco 49ers","san francisco","sf","sfo","niners"],
    "bears":["bears","chicago"],
    "bengals":["bengals","cincinnati","cin"],
    "bills":["bills","buffalo","buf"],
    "broncos":["broncos","denver","den"],
    "browns":["browns","cleveland","cle"],
    "buccaneers":["buccaneers","tampa bay","tb","bucs"],
    "cardinals":["cardinals","arizona","ari"],
    "chargers":["chargers","los angeles chargers","la chargers","lac","san diego","sd"],
    "chiefs":["chiefs","kansas city","kc"],
    "colts":["colts","indianapolis","ind"],
    "commanders":["commanders","washington","wsh","was","football team","redskins"],
    "cowboys":["cowboys","dallas","dal"],
    "dolphins":["dolphins","miami","mia"],
    "eagles":["eagles","philadelphia","phi"],
    "falcons":["falcons","atlanta","atl"],
    "giants":["giants","ny giants","new york giants","nyg"],
    "jaguars":["jaguars","jacksonville","jax","jags"],
    "jets":["jets","ny jets","new york jets","nyj"],
    "lions":["lions","detroit","det"],
    "packers":["packers","green bay","gb"],
    "panthers":["panthers","carolina","car"],
    "patriots":["patriots","new england","ne","nwe"],
    "raiders":["raiders","las vegas","lv","oakland","oak"],
    "rams":["rams","los angeles rams","la rams","lar","st. louis rams"],
    "ravens":["ravens","baltimore","bal"],
    "saints":["saints","new orleans","no","nor"],
    "seahawks":["seahawks","seattle","sea"],
    "steelers":["steelers","pittsburgh","pit"],
    "texans":["texans","houston","hou"],
    "titans":["titans","tennessee","ten"],
    "vikings":["vikings","minnesota","min"],
}
ALIAS_TO = {a.lower():canon for canon,als in NFL_ALIASES.items() for a in als}

def canon_team(s):
    s = (str(s) or "").strip().lower()
    if not s: return pd.NA
    # direct contains
    hits = [ALIAS_TO[a] for a in ALIAS_TO if a in s]
    if len(set(hits)) == 1: return hits[0].title()
    # word match
    words = re.sub(r"[\.\-]", " ", s).split()
    for k, als in NFL_ALIASES.items():
        for a in als:
            if a in words: return k.title()
    return s.title()

for c in ["home","away","side"]:
    if c in out.columns:
        out[c] = out[c].apply(canon_team)

# minimal validity: keep rows with either (home+away) OR (side) present
ok = (out["home"].notna() & out["away"].notna()) | (out["side"].notna())
out = out[ok].copy()

os.makedirs(DST.parent, exist_ok=True)
out.to_csv(DST, index=False)
print(f"[ok] normalized -> {DST} rows={len(out)}")

