#!/usr/bin/env python
import argparse, re
from pathlib import Path
import pandas as pd

# ---- Team aliases ----
NFL_ALIASES = {
    "49ers":["49ers","san francisco","sf","sfo","niners"],
    "Bears":["bears","chicago","chi"],
    "Bengals":["bengals","cincinnati","cin"],
    "Bills":["bills","buffalo","buf"],
    "Broncos":["broncos","denver","den"],
    "Browns":["browns","cleveland","cle"],
    "Buccaneers":["buccaneers","bucs","tampa bay","tb","tampa"],
    "Cardinals":["cardinals","arizona","ari","cards"],
    "Chargers":["chargers","los angeles chargers","la chargers","lac","san diego chargers","sd"],
    "Chiefs":["chiefs","kansas city","kc"],
    "Colts":["colts","indianapolis","ind"],
    "Commanders":["commanders","washington","wsh","was","redskins"],
    "Cowboys":["cowboys","dallas","dal"],
    "Dolphins":["dolphins","miami","mia"],
    "Eagles":["eagles","philadelphia","phi"],
    "Falcons":["falcons","atlanta","atl"],
    "Giants":["giants","new york giants","nyg"],
    "Jaguars":["jaguars","jags","jacksonville","jax"],
    "Jets":["jets","new york jets","nyj"],
    "Lions":["lions","detroit","det"],
    "Packers":["packers","green bay","gb"],
    "Panthers":["panthers","carolina","car"],
    "Patriots":["patriots","new england","ne","nwe"],
    "Raiders":["raiders","las vegas","lv","oakland","oak"],
    "Rams":["rams","los angeles rams","la rams","lar","st. louis rams","st louis rams"],
    "Ravens":["ravens","baltimore","bal"],
    "Saints":["saints","new orleans","no","nor"],
    "Seahawks":["seahawks","seattle","sea"],
    "Steelers":["steelers","pittsburgh","pit"],
    "Texans":["texans","houston","hou"],
    "Titans":["titans","tennessee","ten"],
    "Vikings":["vikings","minnesota","min"],
}
ALIAS_TO_TEAM = {a:canon for canon,aliases in NFL_ALIASES.items() for a in aliases}

def _teamify(text:str):
    t = (text or "").strip().lower()
    if not t: return None
    hits = [ALIAS_TO_TEAM[a] for a in ALIAS_TO_TEAM if a in t]
    if len(set(hits)) == 1:
        return hits[0]
    # boundary fallback
    import re as _re
    for canon, aliases in NFL_ALIASES.items():
        for a in aliases:
            if _re.search(rf"\b{_re.escape(a)}\b", t):
                return canon
    return None

# ---- Patterns for "YYYY week X" opening lines ----
HDR_OPENING = re.compile(r"(20\d{2})\s*week\s*(\d{1,2})", re.IGNORECASE)
ROW_OPENING = re.compile(
    r"(?P<away>[A-Za-z' \.]+)\s+\((?P<aspread>[+-]?\d+(?:\.\d+)?)\)\s+at\s+"
    r"(?P<home>[A-Za-z' \.]+)\s+\((?P<hspread>[+-]?\d+(?:\.\d+)?)\)\s+"
    r"(?P<total>\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)

def parse_opening_text(txt: str) -> pd.DataFrame:
    rows = []
    season = week = None
    for raw in txt.splitlines():
        line = raw.strip().replace("\u00a0"," ")
        m_hdr = HDR_OPENING.search(line)
        if m_hdr:
            season = int(m_hdr.group(1)); week = int(m_hdr.group(2))
            continue

        # Strip leading date/time up to "ET" if present (e.g., "... ET  Team (+3) at Team (-3) 44.5")
        candidate = line
        if " ET" in candidate:
            candidate = candidate.split("ET", 1)[1].strip()

        m = ROW_OPENING.search(candidate)
        if not m: 
            continue

        away = _teamify(m.group("away"))
        home = _teamify(m.group("home"))
        if not home or not away:
            continue

        aspread = float(m.group("aspread"))
        hspread = float(m.group("hspread"))
        total   = float(m.group("total"))

        # Convert to home perspective: negative = home favored
        # Prefer the home-side sign when consistent, else infer from away sign.
        spread_home = -abs(hspread) if hspread < 0 else abs(hspread)
        if (hspread >= 0 and aspread <= 0) or (hspread <= 0 and aspread >= 0):
            spread_home = -abs(aspread) if aspread > 0 else abs(aspread)

        rows.append({
            "season": season, "week": week,
            "home": home, "away": away,
            "spread_open": spread_home,
            "total_open": total,
        })

    df = pd.DataFrame(rows)
    if df.empty: return df
    for c in ("season","week"): df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    df["key_swha"] = (
        df["season"].astype("Int64").astype(str) + "|" +
        df["week"].astype("Int64").astype(str) + "|" +
        df["home"] + "|" + df["away"]
    )
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--txt", nargs="+", required=True, help="One or more opening-odds TXT files (2020+)")
    args = ap.parse_args()

    frames = []
    for fp in args.txt:
        txt = Path(fp).read_text(encoding="utf-8", errors="ignore")
        df = parse_opening_text(txt)
        print(f"[ok] {fp} rows={len(df)}")
        if not df.empty:
            frames.append(df)

    if not frames:
        print("[warn] No rows parsed.")
        return

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["season","week","home","away"]).drop_duplicates(subset=["key_swha"])

    exports = Path("exports"); exports.mkdir(parents=True, exist_ok=True)
    dest = exports / "historical_odds_thelines.csv"
    if dest.exists():
        old = pd.read_csv(dest)
        out = pd.concat([old, out], ignore_index=True)
        out = out.sort_values(["season","week","home","away"]).drop_duplicates(subset=["key_swha"])
    out.to_csv(dest, index=False)
    print(f"[write] {dest} rows={len(out)}")

if __name__ == "__main__":
    main()


