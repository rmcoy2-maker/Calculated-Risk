from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

import nflreadpy as nfl  # pip install nflreadpy

def load_schedule(year: int) -> pd.DataFrame:
    # Polars -> pandas
    sch = nfl.load_schedules([year]).to_pandas()
    # keep the essentials, normalize names to your app
    out = sch.rename(columns={
        "season": "season",
        "week": "week",
        "gameday": "ts",         # kickoff date
        "game_id": "game_id",
        "home_team": "home_team",
        "away_team": "away_team",
    })[["season","week","ts","game_id","home_team","away_team"]]
    out["ts"] = pd.to_datetime(out["ts"], errors="coerce")
    return out

def load_odds_csv(path: Path) -> pd.DataFrame:
    # Example expects Kaggle-like columns; adjust mappings as needed.
    # Kaggle set: "NFL scores and betting data" (odds since ~1979).  âŸ¶ https://kaggle.com/... (download manually)
    df = pd.read_csv(path)
    # Try to guess/standardize
    # Must end with: market, side, odds (american), dec_odds (optional), book (optional), game_id linker columns
    # Example: if odds file has home/away moneyline/spread/total in columns:
    ren = {c: c.lower() for c in df.columns}
    df = df.rename(columns=ren)

    # Youâ€™ll need a reliable join key. Best is nflverse `game_id`.
    # If odds file doesnâ€™t have it, synthesize a key matching schedule:
    # attempt: team abbreviations align with nflverse (e.g., "LAC","LV").
    for need in ["season","week","home_team","away_team"]:
        if need not in df.columns:
            df[need] = None

    # Build H2H rows (home & away) if moneylines exist:
    rows = []
    def am_to_dec(a):
        try:
            a = float(a)
        except:
            return None
        return 1 + (a/100.0) if a>0 else 1 + (100.0/abs(a)) if a<0 else None

    for _,r in df.iterrows():
        season = int(r.get("season") or 0)
        week   = int(r.get("week") or 0)
        ht     = str(r.get("home_team") or "").strip().upper()
        at     = str(r.get("away_team") or "").strip().upper()

        # Example column names you might see; tweak as needed:
        hm_ml = r.get("home_moneyline")
        aw_ml = r.get("away_moneyline")
        book  = r.get("book") or r.get("source") or None

        if hm_ml not in (None,"") and ht:
            rows.append({"season":season,"week":week,"market":"H2H","side":ht,"odds":hm_ml,"book":book,
                         "home_team":ht,"away_team":at})
        if aw_ml not in (None,"") and at:
            rows.append({"season":season,"week":week,"market":"H2H","side":at,"odds":aw_ml,"book":book,
                         "home_team":ht,"away_team":at})

        # Likewise you can expand SPREADS/TOTALS here if present in your file
        # (e.g., r["spread_home"], r["total"], r["spread_home_odds"], ...)

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    out["odds"] = pd.to_numeric(out["odds"], errors="coerce")
    out["dec_odds"] = out["odds"].apply(lambda a: None if pd.isna(a) else (1+a/100 if a>0 else 1+100/abs(a)))
    out["imp"] = out["dec_odds"].apply(lambda d: (1.0/float(d)) if (d and d>0) else None)
    return out

def normalize_and_join(year: int, odds_df: pd.DataFrame, sch: pd.DataFrame) -> pd.DataFrame:
    if odds_df.empty or sch.empty:
        return pd.DataFrame()

    # join on (season, week, home_team, away_team)
    # ensure shared case
    sch = sch.copy()
    sch["home_team"] = sch["home_team"].str.upper()
    sch["away_team"] = sch["away_team"].str.upper()

    odds = odds_df.copy()
    odds["home_team"] = odds["home_team"].str.upper()
    odds["away_team"] = odds["away_team"].str.upper()

    merged = odds.merge(
        sch[["season","week","game_id","ts","home_team","away_team"]],
        on=["season","week","home_team","away_team"],
        how="left",
        validate="m:1",
    )
    merged["ref"] = (
        merged["market"].astype(str).str.upper().fillna("?")
        + "|"
        + merged["side"].astype(str).str.upper().fillna("?")
        + "|"
        + merged["game_id"].astype(str).fillna("?")
    )
    merged["league"] = "NFL"
    return merged[[
        "season","week","ts","league","market","ref","side","odds","dec_odds","imp","game_id","book"
    ]]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--odds_csv", type=Path, required=True, help="Historical odds CSV for this season (Kaggle or your own)")
    ap.add_argument("--out", type=Path, required=True, help="Where to write lines_<season>.csv")
    args = ap.parse_args()

    sch = load_schedule(args.season)
    odds = load_odds_csv(args.odds_csv)
    out  = normalize_and_join(args.season, odds, sch)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    print(f"[seed-builder] {args.season}: wrote {len(out):,} rows -> {args.out}")

if __name__ == "__main__":
    main()


