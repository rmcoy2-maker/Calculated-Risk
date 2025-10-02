#!/usr/bin/env python
import pandas as pd, numpy as np
from pathlib import Path
import re

# --- Team aliases (same style as backtest.py) ---
NFL_ALIASES = {
    "49ers":["49ers","san francisco 49ers","san francisco","sf","sfo","niners"],
    "Bears":["bears","chicago bears","chicago","chi"],
    "Bengals":["bengals","cincinnati bengals","cincinnati","cin"],
    "Bills":["bills","buffalo bills","buffalo","buf"],
    "Broncos":["broncos","denver broncos","denver","den"],
    "Browns":["browns","cleveland browns","cleveland","cle"],
    "Buccaneers":["buccaneers","tampa bay buccaneers","tampa bay","tb","tampa","bucs"],
    "Cardinals":["cardinals","arizona cardinals","arizona","ari","cards"],
    "Chargers":["chargers","los angeles chargers","la chargers","lac","san diego chargers","san diego","sd"],
    "Chiefs":["chiefs","kansas city chiefs","kansas city","kc"],
    "Colts":["colts","indianapolis colts","indianapolis","ind"],
    "Commanders":["commanders","washington commanders","washington","wsh","was","redskins","football team"],
    "Cowboys":["cowboys","dallas cowboys","dallas","dal"],
    "Dolphins":["dolphins","miami dolphins","miami","mia"],
    "Eagles":["eagles","philadelphia eagles","philadelphia","phi"],
    "Falcons":["falcons","atlanta falcons","atlanta","atl"],
    "Giants":["giants","new york giants","ny giants","nyg"],
    "Jaguars":["jaguars","jacksonville jaguars","jacksonville","jax","jags"],
    "Jets":["jets","new york jets","ny jets","nyj"],
    "Lions":["lions","detroit lions","detroit","det"],
    "Packers":["packers","green bay packers","green bay","gb"],
    "Panthers":["panthers","carolina panthers","carolina","car"],
    "Patriots":["patriots","new england patriots","new england","ne","nwe"],
    "Raiders":["raiders","las vegas raiders","las vegas","lv","oakland raiders","oakland","oak"],
    "Rams":["rams","los angeles rams","la rams","lar","st. louis rams","st louis rams"],
    "Ravens":["ravens","baltimore ravens","baltimore","bal"],
    "Saints":["saints","new orleans saints","new orleans","no","nor"],
    "Seahawks":["seahawks","seattle seahawks","seattle","sea"],
    "Steelers":["steelers","pittsburgh steelers","pittsburgh","pit"],
    "Texans":["texans","houston texans","houston","hou"],
    "Titans":["titans","tennessee titans","tennessee","ten"],
    "Vikings":["vikings","minnesota vikings","minnesota","min"],
}
ALIAS_TO_TEAM = {a:canon for canon,als in NFL_ALIASES.items() for a in als}

def teamify(x: str):
    t = (str(x) or "").strip().lower()
    if not t: return None
    hits = [ALIAS_TO_TEAM[a] for a in ALIAS_TO_TEAM if a in t]
    if len(set(hits)) == 1:
        return hits[0]
    # word-boundary fallback
    words = set(re.sub(r"[\.\-]", " ", t).split())
    for canon, als in NFL_ALIASES.items():
        for a in als:
            if a in words:
                return canon
    return None

def normalize_teams(df, cols):
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
            df[c+"_canon"] = df[c].map(teamify)
            df[c] = df[c+"_canon"].combine_first(df[c])
            df.drop(columns=[c+"_canon"], inplace=True)
    return df

def main():
    src_results = Path("exports/results.csv")  # your raw bets file
    src_scores  = Path("exports/nfl_scores_master.csv")  # master schedule/scores (you provide)
    if not src_results.exists():
        raise SystemExit(f"Missing {src_results}")
    if not src_scores.exists():
        raise SystemExit(f"Missing {src_scores} — please export your scores since 1966 here with columns: season,week,home,away,home_score,away_score,date")

    bets = pd.read_csv(src_results)
    bets.columns = [c.strip() for c in bets.columns]
    # normalize basics
    for c in ["home","away","side","market"]:
        if c in bets.columns:
            bets[c] = bets[c].astype(str).str.strip()
    # try numeric line
    if "line" in bets.columns:
        bets["line"] = pd.to_numeric(bets["line"], errors="coerce")

    # Canonicalize teams we do have
    bets = normalize_teams(bets, ["home","away","side"])

    # If home/away missing but side present (typical Moneyline entry), keep 'team_bet'
    if "side" in bets.columns:
        bets["team_bet"] = bets["side"].map(teamify)

    # Load master schedule/scores
    sco = pd.read_csv(src_scores)
    sco = normalize_teams(sco, ["home","away"])
    # Coerce ints
    for c in ["season","week","home_score","away_score"]:
        if c in sco.columns:
            sco[c] = pd.to_numeric(sco[c], errors="coerce")
    # Parse date if present
    if "date" in sco.columns:
        sco["date"] = pd.to_datetime(sco["date"], errors="coerce").dt.date

    # Strategy:
    # 1) If bets already provide season/week/home/away -> keep as-is and just ensure canonical names.
    base_keys = {"season","week","home","away"}
    have_base = base_keys.issubset(set(bets.columns))
    prepared = pd.DataFrame()

    if have_base:
        prepared = bets.copy()
    else:
        # 2) Recover opponent using scores: for each (season/week/team_bet) find the row where team_bet is either home or away
        # If your results.csv lacks season/week/date, this step needs at least one of them. If not, we can only prep team+market rows.
        # Try to pull season/week if present in results
        bets["season"] = pd.to_numeric(bets.get("season"), errors="coerce")
        bets["week"]   = pd.to_numeric(bets.get("week"),   errors="coerce")

        # try season+week+team_bet join
        swt = bets.dropna(subset=["team_bet","season","week"]).copy()
        if not swt.empty:
            # join where team_bet == home OR away
            jh = swt.merge(sco, left_on=["season","week","team_bet"], right_on=["season","week","home"], how="left")
            ja = swt.merge(sco, left_on=["season","week","team_bet"], right_on=["season","week","away"], how="left")
            jh["role"] = "home"; ja["role"] = "away"
            cand = pd.concat([jh, ja], ignore_index=True)
            # choose first non-null match
            mask = cand[["home","away","home_score","away_score"]].notna().all(axis=1)
            prepared = cand[mask].copy()

        # 3) If still empty, try date+team_bet
        if prepared.empty and "date" in bets.columns and "date" in sco.columns:
            bets["date"] = pd.to_datetime(bets["date"], errors="coerce").dt.date
            dt = bets.dropna(subset=["team_bet","date"]).copy()
            if not dt.empty:
                jh = dt.merge(sco, on=["date"], how="left")
                # keep rows where team_bet appears as either home or away that day
                jh = jh[(jh["home"]==jh["team_bet"]) | (jh["away"]==jh["team_bet"])]
                prepared = jh.copy()

        # 4) If nothing matched, we can only keep team_bet-level ML rows without opponent (not useful for backtest join).
        if prepared.empty:
            keep = ["team_bet","market","line","side"]
            keep = [k for k in keep if k in bets.columns]
            prepared = bets[keep].copy()
            prepared["__note"] = "no schedule match; needs season/week or date"

        # unify schema to (season,week,home,away,home_score,away_score,date,market,line,side)
        cols = {
            "season":"season","week":"week","home":"home","away":"away",
            "home_score":"home_score","away_score":"away_score","date":"date",
            "market":"market","line":"line","side":"side"
        }
        # pull from both bets and schedule columns present
        for k in list(cols):
            if k not in prepared.columns and k in bets.columns:
                prepared[k] = bets[k]

    # Final clean & output
    prepared["season"] = pd.to_numeric(prepared.get("season"), errors="coerce").astype("Int64")
    prepared["week"]   = pd.to_numeric(prepared.get("week"), errors="coerce").astype("Int64")
    if "date" in prepared.columns:
        prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce").dt.date
    for c in ["home","away"]:
        if c in prepared.columns:
            prepared[c] = prepared[c].astype(str).str.strip()

    out = Path("exports/results_prepared.csv")
    prepared.to_csv(out, index=False)
    print(f"[write] {out} rows={len(prepared)}")

if __name__ == "__main__":
    main()

