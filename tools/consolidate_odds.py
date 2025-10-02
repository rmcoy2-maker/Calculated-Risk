#!/usr/bin/env python
import pandas as pd
import numpy as np
from pathlib import Path

PIPE_COLS = ["season","week","home","away","spread_close","total_close","ml_home","ml_away"]

ALIASES = {
    "season": ["season","year"],
    "week":   ["week","wk","game_week"],
    "home":   ["home","home_team","team_home","home_name","homeclub","home_name_full"],
    "away":   ["away","away_team","team_away","visitor","road_name","awayclub","away_name_full"],

    "spread_close": [
        "spread_close","closing_spread","final_spread","spread_closing","close_spread",
        "spread","spread_home_close","home_spread_close","home_spread","spread_home",
        "line_close","closing_line","line","hcp_close","hcp_closing","handicap_close"
    ],
    "total_close": [
        "total_close","closing_total","final_total","total_closing","close_total",
        "ou_close","o_u_close","o/u_close","ou","o_u","o/u","total","points_total_close"
    ],

    # keep opening separate so we can fallback + flag
    "spread_open": ["spread_open","open_spread","opening_spread","line_open","opening_line","open"],
    "total_open":  ["total_open","opening_total","open_total"],

    "ml_home": ["ml_home","moneyline_home","home_ml","home_moneyline","ml_h","home_price","ml_home_close","ml_home_est"],
    "ml_away": ["ml_away","moneyline_away","away_ml","away_moneyline","ml_a","away_price","ml_away_close","ml_away_est"],
    "date":    ["date","game_date","start_date","kickoff","datetime"]
}

def _first_present(cands, cols):
    lower = {c.lower(): c for c in cols}
    for c in cands:
        if c.lower() in lower: return lower[c.lower()]
    return None

def normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = {}
    for std, alts in ALIASES.items():
        src = _first_present(alts, df.columns)
        if src is not None: out[std] = df[src]
    nd = pd.DataFrame(out)

    # ensure cols exist
    for c in set(PIPE_COLS + ["spread_open","total_open","date"]):
        if c not in nd.columns: nd[c] = np.nan

    # types
    for c in ["season","week"]:
        nd[c] = pd.to_numeric(nd[c], errors="coerce").astype("Int64")
    for c in ["spread_close","total_close","spread_open","total_open","ml_home","ml_away"]:
        nd[c] = pd.to_numeric(nd[c], errors="coerce")

    for c in ["home","away"]:
        if c in nd.columns:
            nd[c] = nd[c].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

    keep = list({*PIPE_COLS, "spread_open","total_open","date"})
    return nd[[c for c in keep if c in nd.columns]]

def read_csv(p: Path):
    if not p.exists(): return None
    try: return pd.read_csv(p)
    except Exception as e:
        print(f"[warn] failed reading {p.name}: {e}")
        return None

def first_non_null(s: pd.Series):
    s = s.dropna()
    return s.iloc[0] if len(s) else np.nan

def main():
    exports = Path("exports"); exports.mkdir(exist_ok=True)

    candidates = [
        exports / "historical_odds_oddsshark.csv",
        exports / "historical_odds_thelines.csv",
    ]
    for p in exports.glob("historical_odds_*.csv"):
        if p.name not in {"historical_odds.csv","historical_odds_merged.csv"} and p not in candidates:
            candidates.append(p)

    frames=[]
    for p in candidates:
        df = read_csv(p)
        if df is None or df.empty: continue
        nd = normalize(df)
        nd["source_file"] = p.name
        # tag row kind (closing > opening)
        has_close = nd["spread_close"].notna() | nd["total_close"].notna()
        has_open  = nd["spread_open"].notna()  | nd["total_open"].notna()
        nd["src_kind"]     = np.where(has_close, "closing", np.where(has_open, "opening", "unknown"))
        nd["src_priority"] = np.where(nd["src_kind"].eq("closing"), 1, np.where(nd["src_kind"].eq("opening"), 2, 9))
        frames.append(nd)

    if not frames: raise FileNotFoundError("No source odds CSVs found in ./exports")

    merged_all = pd.concat(frames, ignore_index=True)
    merged_all = merged_all[merged_all["home"].notna() & merged_all["away"].notna()]

    group_cols = ["season","week","home","away"]
    merged_all = merged_all.sort_values(group_cols + ["src_priority"])

    # aggregate by priority then first non-null
    agg_cols = [c for c in merged_all.columns if c not in group_cols]
    agg_map = {c: first_non_null for c in agg_cols}
    canon = merged_all.groupby(group_cols, dropna=False, as_index=False).agg(agg_map)

    # fallback + flag
    canon["used_opening_fallback"] = False
    if "spread_open" in canon.columns:
        need_sp = canon["spread_close"].isna() & canon["spread_open"].notna()
        canon.loc[need_sp, "spread_close"] = canon.loc[need_sp, "spread_open"]
        canon.loc[need_sp, "used_opening_fallback"] = True
    if "total_open" in canon.columns:
        need_to = canon["total_close"].isna() & canon["total_open"].notna()
        canon.loc[need_to, "total_close"] = canon.loc[need_to, "total_open"]
        canon.loc[need_to, "used_opening_fallback"] = True

    canon["line_source"] = np.where(canon["used_opening_fallback"], "opening", "closing")

    # ensure order
    for c in PIPE_COLS:
        if c not in canon.columns: canon[c] = np.nan
    cols_out = PIPE_COLS + [c for c in ["spread_open","total_open","line_source","used_opening_fallback","source_file","date"] if c in canon.columns]

    # write
    canon[cols_out].to_csv(exports / "historical_odds_merged.csv", index=False)
    canon[PIPE_COLS].to_csv(exports / "historical_odds.csv", index=False)

    # report
    def pct(col): return f"{(canon[col].notna().mean()*100):.1f}%"
    ml_pct = (canon[["ml_home","ml_away"]].notna().all(axis=1).mean()*100)
    print(f"[done] sources={len(frames)} rows_raw={len(merged_all)} rows_canon={len(canon)} | "
          f"spread_close avail: {pct('spread_close')} | total_close  avail: {pct('total_close')} | "
          f"moneyline    avail: {ml_pct:.1f}%")

if __name__ == "__main__":
    main()

