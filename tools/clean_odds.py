#!/usr/bin/env python
import pandas as pd
from pathlib import Path

# Canonical NFL nicknames + common aliases
NFL_ALIASES = {
    "49ers": ["49ers","san francisco 49ers","san francisco","sf","sfo","niners"],
    "Bears": ["bears","chicago bears","chicago","chi"],
    "Bengals": ["bengals","cincinnati bengals","cincinnati","cin"],
    "Bills": ["bills","buffalo bills","buffalo","buf"],
    "Broncos": ["broncos","denver broncos","denver","den"],
    "Browns": ["browns","cleveland browns","cleveland","cle"],
    "Buccaneers": ["buccaneers","tampa bay buccaneers","tampa bay","tb","tampa","bucs"],
    "Cardinals": ["cardinals","arizona cardinals","arizona","ari","cards"],
    "Chargers": ["chargers","los angeles chargers","la chargers","lac","san diego chargers","san diego","sd"],
    "Chiefs": ["chiefs","kansas city chiefs","kansas city","kc"],
    "Colts": ["colts","indianapolis colts","indianapolis","ind"],
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
    "Patriots": ["patriots","new england patriots","new england","ne","nwe"],
    "Raiders": ["raiders","las vegas raiders","las vegas","lv","oakland raiders","oakland","oak"],
    "Rams": ["rams","los angeles rams","la rams","lar","st. louis rams","st louis rams"],
    "Ravens": ["ravens","baltimore ravens","baltimore","bal"],
    "Saints": ["saints","new orleans saints","new orleans","no","nor"],
    "Seahawks": ["seahawks","seattle seahawks","seattle","sea"],
    "Steelers": ["steelers","pittsburgh steelers","pittsburgh","pit"],
    "Texans": ["texans","houston texans","houston","hou"],
    "Titans": ["titans","tennessee titans","tennessee","ten"],
    "Vikings": ["vikings","minnesota vikings","minnesota","min"],
}
ALIAS_TO_TEAM = {a.lower(): t for t, aliases in NFL_ALIASES.items() for a in aliases}

def _teamify(x: str):
    t = (str(x) or "").strip().lower()
    if not t: return None
    # direct alias hit
    if t in ALIAS_TO_TEAM: return ALIAS_TO_TEAM[t]
    # substring fallback (handles things like "at San Francisco 49ers")
    hits = [ALIAS_TO_TEAM[a] for a in ALIAS_TO_TEAM if a in t]
    if len(set(hits)) == 1:
        return hits[0]
    # token fallback
    words = set(t.replace("-", " ").replace(".", " ").split())
    for canon, aliases in NFL_ALIASES.items():
        for a in aliases:
            if a in words:
                return canon
    return None

def main():
    exp = Path("exports")
    src = exp / "historical_odds.csv"
    if not src.exists():
        raise SystemExit("exports/historical_odds.csv not found. Run consolidate first.")

    df = pd.read_csv(src)

    # Normalize team names into canonical nicknames
    for c in ["home","away"]:
        if c in df.columns:
            df[c] = df[c].map(_teamify)

    # Keep only rows where both sides mapped successfully
    before = len(df)
    df = df.dropna(subset=["home","away"]).copy()
    after = len(df)

    # Save cleaned copy and also replace the working odds file
    out1 = exp / "historical_odds_clean.csv"
    df.to_csv(out1, index=False)
    df.to_csv(src, index=False)
    print(f"[clean] normalized + kept {after}/{before} -> wrote {out1.name} & replaced historical_odds.csv")

if __name__ == "__main__":
    main()

