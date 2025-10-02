#!/usr/bin/env python
import argparse
import pandas as pd
import numpy as np
from pathlib import Path

# --- Team normalization ---
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
ALIAS_TO_TEAM = {alias: canon for canon, aliases in NFL_ALIASES.items() for alias in aliases}

def _teamify(x: str):
    t = (str(x) or "").strip().lower()
    if not t:
        return None
    hits = [ALIAS_TO_TEAM[a] for a in ALIAS_TO_TEAM if a in t]
    if len(set(hits)) == 1:
        return hits[0]
    words = set(t.replace("-", " ").replace(".", " ").split())
    for canon, aliases in NFL_ALIASES.items():
        for a in aliases:
            if a in words:
                return canon
    return None

def normalize_teams(df: pd.DataFrame, home_col="home", away_col="away"):
    df = df.copy()
    for c in [home_col, away_col]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
            guess = df[c].map(_teamify)
            df[c] = guess.combine_first(df[c])
    return df

# --- Era awareness ---
ERA_A_START, ERA_A_END = 1966, 2005   # ML only
ERA_B_START, ERA_B_END = 2006, 2019   # ML, ATS, Totals (closers present)
ERA_C_START               = 2020      # ML, ATS, Totals (mostly openers; closers if available)
PROPS_SINCE_DEFAULT       = 2017

def era_for_season(season: int) -> str:
    if pd.isna(season):
        return "unknown"
    s = int(season)
    if ERA_A_START <= s <= ERA_A_END: return "A"
    if ERA_B_START <= s <= ERA_B_END: return "B"
    if s >= ERA_C_START: return "C"
    return "unknown"

def annotate_availability(df: pd.DataFrame, props_since: int = PROPS_SINCE_DEFAULT):
    df = df.copy()
    df["era"] = df.get("season").apply(era_for_season)
    df["allow_ml"]     = df["era"].isin(["A","B","C"])
    df["allow_spread"] = df["era"].isin(["B","C"])
    df["allow_total"]  = df["era"].isin(["B","C"])
    df["allow_props"]  = df.get("season").fillna(0).astype("Int64").ge(props_since)
    return df

# --- Load odds/results ---
def load_odds():
    odds = pd.read_csv("exports/historical_odds.csv")
    odds = normalize_teams(odds, "home","away")

    merged_path = Path("exports/historical_odds_merged.csv")
    if merged_path.exists():
        merged = pd.read_csv(merged_path)
        keep = [c for c in ["season","week","home","away","line_source","spread_open","total_open","date"] if c in merged.columns]
        if keep:
            merged = normalize_teams(merged[keep], "home","away")
            odds = odds.merge(merged, on=["season","week","home","away"], how="left")
    else:
        odds["line_source"] = np.where(odds[["spread_close","total_close"]].notna().any(axis=1), "closing", "opening")

    if "date" in odds.columns:
        odds["date"] = pd.to_datetime(odds["date"], errors="coerce").dt.date
    return odds

def load_results(path):
    df = pd.read_csv(path)
    rename_map = {
        "HomeTeam":"home","AwayTeam":"away","Home":"home","Away":"away",
        "home_team":"home","away_team":"away",
        "HomeScore":"home_score","AwayScore":"away_score",
        "home_score":"home_score","away_score":"away_score",
        "Date":"date","GameDate":"date","game_date":"date","Kickoff":"date","kickoff":"date",
        "Season":"season","Year":"season","Week":"week","week_num":"week"
    }
    df = df.rename(columns={k:v for k,v in rename_map.items() if k in df.columns})
    df = normalize_teams(df, "home","away")
    if "season" in df.columns:
        df["season"] = pd.to_numeric(df["season"], errors="coerce").astype("Int64")
    if "week" in df.columns:
        df["week"] = pd.to_numeric(df["week"], errors="coerce").astype("Int64")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    if "game_id" not in df.columns:
        df["game_id"] = np.arange(len(df))
    if "line" in df.columns:
        df["line"] = pd.to_numeric(df["line"], errors="coerce")
    if "market" in df.columns:
        df["market"] = df["market"].astype(str).str.lower()
    return df

# --- Line selection ---
def choose_lines(df, line_mode):
    df["spread_used"] = df["spread_close"]
    df["total_used"]  = df["total_close"]
    if line_mode in ("opening","mixed"):
        if "spread_open" in df.columns:
            need = df["spread_used"].isna() | (line_mode=="opening")
            df.loc[need, "spread_used"] = df.loc[need, "spread_open"]
        if "total_open" in df.columns:
            need = df["total_used"].isna() | (line_mode=="opening")
            df.loc[need, "total_used"] = df.loc[need, "total_open"]
    df["has_spread"] = df["spread_used"].notna()
    df["has_total"]  = df["total_used"].notna()
    df["has_ml"]     = df["ml_home"].notna() & df["ml_away"].notna()
    return df

def _line_distance(row_line, row_market, used_spread, used_total):
    if pd.isna(row_line):
        return np.nan
    m = str(row_market).lower()
    if "total" in m or "o/u" in m or "ou" in m:
        return abs((used_total if pd.notna(used_total) else np.nan) - row_line)
    if pd.isna(used_spread):
        return np.nan
    diff_direct   = abs(used_spread - row_line)
    diff_opposite = abs((-used_spread) - row_line)  # away perspective
    return min(diff_direct, diff_opposite)

def best_merge(odds, res, line_mode, tol=0.75):
    # 1) season+week+teams
    if {"season","week"}.issubset(odds.columns) and {"season","week"}.issubset(res.columns):
        merged = odds.merge(res, on=["season","week","home","away"], how="inner")
        return choose_lines(merged, line_mode), "season+week+teams"

    # 2) date+teams
    if "date" in odds.columns and "date" in res.columns:
        merged = odds.merge(res, on=["date","home","away"], how="inner")
        merged = choose_lines(merged, line_mode)
        if not merged.empty:
            return merged, "date+teams"

    # 3) teams only + closest line (both orientations)
    base = odds.merge(res, on=["home","away"], how="inner", suffixes=("",""))
    swapped = odds.rename(columns={"home":"away","away":"home"})
    swap_merge = swapped.merge(res, on=["home","away"], how="inner", suffixes=("",""))
    if not swap_merge.empty:
        swap_merge = swap_merge.rename(columns={"home":"away","away":"home"})
    many = pd.concat([base, swap_merge], ignore_index=True)
    if many.empty:
        return many, "no-join"

    many = choose_lines(many, line_mode)
    many["line_diff"] = many.apply(
        lambda r: _line_distance(r.get("line"), r.get("market"), r.get("spread_used"), r.get("total_used")),
        axis=1
    )
    tmp = many.assign(
        avail_score = many["has_spread"].astype(int) + many["has_total"].astype(int) + many["has_ml"].astype(int)
    ).sort_values(["game_id","line_diff","avail_score","season","week"], na_position="last")

    best_idx = []
    for gid, g in tmp.groupby("game_id", sort=False):
        if g["line_diff"].notna().any():
            best_idx.append(g["line_diff"].idxmin())
        else:
            best_idx.append(g.index[0])
    picked = tmp.loc[best_idx].copy()
    has_diff = picked["line_diff"].notna()
    ok = has_diff & (picked["line_diff"] <= tol)
    picked = pd.concat([picked[ok], picked[~has_diff]], ignore_index=True)
    return picked, f"teams+closest-line (tol={tol})"

# --- Metrics ---
def ats_metrics(df):
    sub = df.loc[df["has_spread"], ["margin_home","spread_used"]].dropna()
    if sub.empty: return {"rows":0}
    edge = sub["margin_home"] + sub["spread_used"]
    return {"rows": int(len(sub)), "cover_rate": float((edge > 0).mean()), "push_rate": float((edge == 0).mean())}

def total_metrics(df):
    sub = df.loc[df["has_total"], ["game_total","total_used"]].dropna()
    if sub.empty: return {"rows":0}
    diff = sub["game_total"] - sub["total_used"]
    return {"rows": int(len(sub)), "over_rate": float((diff > 0).mean()), "push_rate": float((diff == 0).mean())}

def ml_roi(df, unit=100):
    sub = df.loc[df["has_ml"], ["margin_home","ml_home"]].dropna()
    if sub.empty: return {"rows":0}
    def profit(ml): return unit*(abs(ml)/100) if ml>0 else unit*(100/abs(ml))
    pnl = np.where(sub["margin_home"] > 0, [profit(x) for x in sub["ml_home"]], -unit)
    return {"rows": int(len(sub)), "roi_home_only": float(np.mean(pnl)/unit)}

def ml_winrate(df):
    if "market" not in df.columns: return {"rows":0}
    m = df["market"].astype(str).str.lower()
    is_ml = m.str.contains("moneyline") | m.str.fullmatch("ml")
    if "side" in df.columns:
        s = df.loc[is_ml, ["margin_home","side","home","away"]].dropna()
        if s.empty: return {"rows":0}
        side = s["side"].astype(str).str.lower()
        took_home = side.eq("home") | side.eq("h") | side.eq(s["home"].str.lower())
        wins = np.where(took_home, s["margin_home"] > 0, s["margin_home"] < 0)
        return {"rows": int(len(s)), "win_rate": float(np.mean(wins))}
    return {"rows":0}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="CSV with: game_id, home, away, home_score, away_score, market, line")
    ap.add_argument("--line-mode", choices=["closing","opening","mixed"], default="mixed")
    ap.add_argument("--tol", type=float, default=0.75, help="Max |diff| to accept when matching lines without dates")
    ap.add_argument("--era-aware", action="store_true", default=True, help="Mask markets not available by season/era")
    ap.add_argument("--props-since", type=int, default=PROPS_SINCE_DEFAULT, help="Season from which player props exist")
    args = ap.parse_args()

    odds = load_odds()
    res  = load_results(args.results)

    df, how = best_merge(odds, res, args.line_mode, tol=args.tol)
    if df.empty:
        # write a small unmatched sample for debugging
        pd.DataFrame({
            "odds_home_sample": sorted(pd.unique(odds["home"]))[:20],
            "res_home_sample":  sorted(pd.unique(res["home"]))[:20]
        }).to_csv("exports/backtest_unmatched_sample.csv", index=False)
        raise SystemExit(f"No rows joined. Merge method: {how}. Check team names / tolerance / results columns.")

    # Era awareness: annotate + mask
    df = annotate_availability(df, props_since=args.props_since)
    mkt = df.get("market", pd.Series(index=df.index, dtype=object)).astype(str).str.lower()
    if args.era_aware:
        mask_spread = (mkt.str.contains("spread") | mkt.str.contains("ats"))
        mask_total  = (mkt.str.contains("total")  | mkt.str.contains("o/u") | mkt.str.contains("ou"))
        mask_props  = mkt.str.contains("prop") | mkt.str.contains("passing") | mkt.str.contains("rushing") | mkt.str.contains("receiving")

        # drop rows where props are not allowed (avoid dtype warnings)
        df = df[~((~df["allow_props"]) & mask_props)]

        df.loc[~df["allow_spread"] & mask_spread, ["spread_close","spread_open"]] = np.nan
        df.loc[~df["allow_total"]  & mask_total,  ["total_close","total_open"]]   = np.nan
        df.loc[~df["allow_ml"]     & ~mask_spread & ~mask_total, ["ml_home","ml_away"]] = np.nan
        df = df.dropna(how="all")

    # outcomes
    df["home_score"] = pd.to_numeric(df["home_score"], errors="coerce")
    df["away_score"] = pd.to_numeric(df["away_score"], errors="coerce")
    df["margin_home"] = df["home_score"] - df["away_score"]
    df["game_total"]  = df["home_score"] + df["away_score"]

    rep = {
        "merge_method": how,
        "rows_joined": int(len(df)),
        "rows_with_spread_used": int(df["has_spread"].sum()),
        "rows_with_total_used": int(df["has_total"].sum()),
        "rows_with_ml": int(df["has_ml"].sum()),
        "line_mode": args.line_mode,
        "ats": ats_metrics(df),
        "totals": total_metrics(df),
        "ml": ml_roi(df),
        "ml_winrate": ml_winrate(df),
    }

    out_path = Path("exports/backtest_joined.csv")
    df.to_csv(out_path, index=False)
    print(f"[write] {out_path} rows={len(df)}")
    print(rep)

if __name__ == "__main__":
    main()



