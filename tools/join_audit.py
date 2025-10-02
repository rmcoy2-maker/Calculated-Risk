# tools/join_audit.py
from __future__ import annotations

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
import re

from join_keys import add_join_keys  # robust dispatcher

pd.set_option("display.width", 180)
pd.set_option("display.max_columns", 50)

# -------------------- helpers --------------------
def _col_str(df: pd.DataFrame, name: str) -> pd.Series:
    """Return a StringDtype Series for df[name] or a blank series if missing."""
    if name in df.columns:
        return df[name].astype("string").fillna("")
    return pd.Series([""] * len(df), index=df.index, dtype="string")


def _head(df: pd.DataFrame, n=10) -> pd.DataFrame:
    try:
        return df.head(n)
    except Exception:
        return df

def _safe_read_csv(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return pd.read_csv(p, low_memory=False)

def _fill_key_date_from_any_id(df: pd.DataFrame, candidates: list[str]) -> tuple[pd.DataFrame, int]:
    """
    If _key_date is blank, try to extract YYYY-MM-DD from any candidate column
    that contains patterns like 20240915, 2024-09-15, or 2024/09/15.
    Returns (df, n_filled).
    """
    d = df.copy()
    if "_key_date" not in d.columns:
        d["_key_date"] = ""
    if "_DateISO" not in d.columns:
        d["_DateISO"] = ""

    blank = d["_key_date"].fillna("").eq("")
    if not blank.any():
        return d, 0

    # Combine all candidate columns into one string series (best-effort)
    combo = pd.Series([""] * len(d), index=d.index, dtype="string")
    for c in candidates:
        if c in d.columns:
            v = pd.Series(d[c]).astype("string").fillna("")
            combo = combo.where(combo.ne(""), v)

    # Extract first date-like token
    # Accept: 20240915, 2024-09-15, 2024/09/15
    pat = re.compile(r"(20\d{2})[-/]?(\d{2})[-/]?(\d{2})")
    def _extract_date(txt):
        if not isinstance(txt, str):
            return ""
        m = pat.search(txt)
        if not m:
            return ""
        y, mo, da = m.groups()
        return f"{y}-{mo}-{da}"

    extracted = combo.map(_extract_date)
    to_fill = blank & extracted.ne("")
    d.loc[to_fill, "_key_date"] = extracted[to_fill]
    # keep _DateISO consistent if blank
    need_iso = d["_DateISO"].fillna("").eq("") & d["_key_date"].fillna("").ne("")
    d.loc[need_iso, "_DateISO"] = d.loc[need_iso, "_key_date"]
    return d, int(to_fill.sum())

def _rebuild_strict_odds_key(df: pd.DataFrame) -> pd.Series:
    return (
        _col_str(df, "_key_date") + "|" +
        _col_str(df, "_home_core") + "@" +
        _col_str(df, "_away_core") + "|" +
        _col_str(df, "market_norm") + "|" +
        _col_str(df, "side_norm")
    )

def _mk_sw_odds_key_home(d: pd.DataFrame) -> pd.Series:
    return _col_str(d, "_key_home_sw") + "|" + _col_str(d, "market_norm") + "|" + _col_str(d, "side_norm")

def _mk_sw_odds_key_away(d: pd.DataFrame) -> pd.Series:
    return _col_str(d, "_key_away_sw") + "|" + _col_str(d, "market_norm") + "|" + _col_str(d, "side_norm")


def _expand_odds_for_audit(o: pd.DataFrame) -> pd.DataFrame:
    """
    If odds rows lack side_norm, expand each row into two:
      - H2H/SPREADS -> HOME and AWAY
      - TOTALS      -> OVER and UNDER
    Copies through book/ts/date/team cores/market; keeps line/price if present.
    This is audit-only; it doesn't claim which price belongs to which side.
    """
    if len(o) == 0:
        return o
    if "side_norm" in o.columns and o["side_norm"].fillna("").ne("").any():
        return o  # already has sides somewhere; don't double-expand

    needed = ["_key_date","_home_core","_away_core","market_norm"]
    for c in needed:
        if c not in o.columns:
            o[c] = ""

    rows = []
    for _, r in o.iterrows():
        base = {
            "_key_date":   r.get("_key_date",  ""),
            "_home_core":  r.get("_home_core", ""),
            "_away_core":  r.get("_away_core", ""),
            "market_norm": r.get("market_norm",""),
            "book":        r.get("book",       ""),
            "ts":          r.get("ts",         pd.NaT),
            "line":        pd.to_numeric(r.get("line",  np.nan), errors="coerce"),
            "price":       pd.to_numeric(r.get("price", np.nan), errors="coerce"),
        }
        m = str(base["market_norm"])
        if m in ("H2H", "SPREADS"):
            a = dict(base); a["side_norm"] = "HOME"; rows.append(a)
            b = dict(base); b["side_norm"] = "AWAY"; rows.append(b)
        elif m == "TOTALS":
            a = dict(base); a["side_norm"] = "OVER"; rows.append(a)
            b = dict(base); b["side_norm"] = "UNDER"; rows.append(b)
        else:
            # unknown market -> skip expansion for this row
            pass
    out = pd.DataFrame(rows)
    if len(out) == 0:
        return o
    # Rebuild strict key
    out["__key_strict_odds"] = _rebuild_strict_odds_key(out)
    return out

# -------------------- main --------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", required=True)
    ap.add_argument("--scores", required=True)
    ap.add_argument("--odds", required=True)
    ap.add_argument("--season", default=None)
    ap.add_argument("--week", default=None)
    args = ap.parse_args()

    print(f"[load] edges={args.edges}", flush=True)
    print(f"[load] scores={args.scores}", flush=True)
    print(f"[load] odds={args.odds}", flush=True)

    e_raw = _safe_read_csv(args.edges)
    s_raw = _safe_read_csv(args.scores)
    o_raw = _safe_read_csv(args.odds)

    # Standardize keys/normalizations
    e = add_join_keys(e_raw, "edges")
    s = add_join_keys(s_raw, "scores")
    o = add_join_keys(o_raw, "odds")

    # ---------- Backfill missing _key_date from any id-like columns ----------
    edge_id_candidates = ["game_id","gid","GID","gameid","GameID","match_id","MatchID","id","ID","_id"]
    e, n_filled_e = _fill_key_date_from_any_id(e, edge_id_candidates)

    odds_id_candidates = ["game_id","gid","GID","event_id","EventID","id","ID","key","Key","ref","Ref","match_id","MatchID"]
    o, n_filled_o = _fill_key_date_from_any_id(o, odds_id_candidates)

    if n_filled_e or n_filled_o:
        print(f"[backfill] filled _key_date from ids: edges+={n_filled_e}, odds+={n_filled_o}", flush=True)

    # ---------- Backfill missing edge dates from scores via Season-Week ----------
    if "_key_date" in e.columns:
        blank_date = e["_key_date"].fillna("").eq("")
        if blank_date.any():
            s_keys = (
                s[["_key_home_sw","_key_away_sw","_key_date"]]
                .dropna(subset=["_key_home_sw","_key_away_sw"])
                .drop_duplicates()
            )
            e_fix = e.loc[blank_date, ["_key_home_sw","_key_away_sw"]].merge(
                s_keys.rename(columns={"_key_home_sw":"_key_home_sw_sc","_key_away_sw":"_key_away_sw_sc"}),
                left_on=["_key_home_sw","_key_away_sw"],
                right_on=["_key_home_sw_sc","_key_away_sw_sc"],
                how="left",
            )
            fill1 = e_fix["_key_date"]

            need_swap = fill1.fillna("").eq("")
            if need_swap.any():
                e_fix2 = e.loc[blank_date, ["_key_home_sw","_key_away_sw"]].merge(
                    s_keys.rename(columns={"_key_home_sw":"_key_away_sw_sc","_key_away_sw":"_key_home_sw_sc"}),
                    left_on=["_key_home_sw","_key_away_sw"],
                    right_on=["_key_home_sw_sc","_key_away_sw_sc"],
                    how="left",
                )
                fill_swapped = e_fix2["_key_date"]
                fill = fill1.where(~fill1.fillna("").eq(""), fill_swapped)
            else:
                fill = fill1

            e.loc[blank_date, "_key_date"] = e.loc[blank_date, "_key_date"].where(
                ~e.loc[blank_date, "_key_date"].fillna("").eq(""), fill
            )
            if "_DateISO" in e.columns:
                need_iso = e["_DateISO"].fillna("").eq("") & e["_key_date"].fillna("").ne("")
                e.loc[need_iso, "_DateISO"] = e.loc[need_iso, "_key_date"]

    # ---------- Optional filters ----------
    if args.season and str(args.season).strip().lower() not in ("", "all", "all seasons"):
        season_val = str(args.season)
        e = e[e["_season"].astype(str) == season_val]
        s = s[s["_season"].astype(str) == season_val]
        o = o[o["_season"].astype(str) == season_val]

    if args.week and str(args.week).strip().lower() not in ("", "all", "all weeks"):
        week_val = str(args.week)
        e = e[e["_week"].astype(str) == week_val]
        s = s[s["_week"].astype(str) == week_val]
        o = o[o["_week"].astype(str) == week_val]

    print(f"[rows] edges={len(e)}  scores={len(s)}  odds={len(o)}\n", flush=True)

    # ---------------- Distros ----------------
    print("[edges] market/side distribution (top 12):")
    if "market_norm" in e.columns and "side_norm" in e.columns:
        dist = (
            e.groupby(["market_norm", "side_norm"])
             .size().reset_index(name="n")
             .sort_values("n", ascending=False)
             .head(12)
        )
        print(dist.to_string(index=False))
    else:
        print("  (missing market_norm and/or side_norm on edges)")

    print("\n[odds] market/side distribution (top 12):")
    if "market_norm" in o.columns and "side_norm" in o.columns:
        dist_o = (
            o.groupby(["market_norm", "side_norm"])
             .size().reset_index(name="n")
             .sort_values("n", ascending=False)
        )
        if len(dist_o):
            print(dist_o.head(12).to_string(index=False))
        else:
            blank_m = int(o["market_norm"].isna().sum() + (o["market_norm"] == "").sum())
            blank_s = int(o["side_norm"].isna().sum() + (o["side_norm"] == "").sum())
            print(f"  (no non-empty combos yet; blank market_norm={blank_m}, blank side_norm={blank_s})")
    else:
        print("  (missing market_norm and/or side_norm on odds)")

    # ---------------- Scores join audit ----------------
    print("\n[scores] strict-date join coverage:")
    score_cols_all = ["home_score", "away_score", "HomeScore", "AwayScore"]
    score_cols = [c for c in score_cols_all if c in s.columns]
    if not score_cols:
        print("  No score columns found on scores (expected one of: home_score/away_score or HomeScore/AwayScore).")
        return

    e_sc = e.merge(
        s[["_key_strict_date"] + score_cols],
        on="_key_strict_date",
        how="left",
        suffixes=("", "_sc"),
    )
    joined_sc = pd.Series(False, index=e_sc.index)
    for c in score_cols:
        joined_sc = joined_sc | e_sc[c].notna()
    print(f"  matched: {int(joined_sc.sum())}/{len(e_sc)} ({joined_sc.mean():.1%})")

    print("[scores] season-week (home/away) fallback coverage:")
    sw_home = e.merge(s[["_key_home_sw", "home_score"]], on="_key_home_sw", how="left")
    sw_away = e.merge(s[["_key_away_sw", "away_score"]], on="_key_away_sw", how="left")
    sw_hit = sw_home["home_score"].notna() | sw_away["away_score"].notna()
    print(f"  potential matches: {int(sw_hit.sum())}/{len(e)} ({sw_hit.mean():.1%})")

    # ---------------- Odds join audit ----------------
    print("\n[odds] strict-date + market/side join coverage:")
    e_keys = e.copy()
    e_keys["__key_strict_odds"] = _rebuild_strict_odds_key(e_keys)

    # If odds still lack sides, expand to long for audit (HOME/AWAY or OVER/UNDER)
    o_expanded = _expand_odds_for_audit(o)
    o_keys = o_expanded.copy()
    if "__key_strict_odds" not in o_keys.columns:
        o_keys["__key_strict_odds"] = _rebuild_strict_odds_key(o_keys)

    strict = e_keys.merge(
        o_keys[["__key_strict_odds", "book", "price", "line"]],
        on="__key_strict_odds",
        how="left",
        suffixes=("", "_od"),
    )
    strict_hit = strict["book"].notna()
    print(f"  matched: {int(strict_hit.sum())}/{len(strict)} ({strict_hit.mean():.1%})")

    print("[odds] season-week fallback coverage (home/away variants):")
    e_keys["__key_sw_home"] = _mk_sw_odds_key_home(e_keys)
    e_keys["__key_sw_away"] = _mk_sw_odds_key_away(e_keys)
    o_keys["__key_sw_home"] = _mk_sw_odds_key_home(o_keys)
    o_keys["__key_sw_away"] = _mk_sw_odds_key_away(o_keys)

    sw_home_join = e_keys.merge(
        o_keys[["__key_sw_home", "book", "price", "line"]],
        on="__key_sw_home",
        how="left",
        suffixes=("", "_od"),
    )
    sw_away_join = e_keys.merge(
        o_keys[["__key_sw_away", "book", "price", "line"]],
        on="__key_sw_away",
        how="left",
        suffixes=("", "_od"),
    )
    sw_hit_any = sw_home_join["book"].notna() | sw_away_join["book"].notna()
    print(f"  potential matches: {int(sw_hit_any.sum())}/{len(e_keys)} ({sw_hit_any.mean():.1%})")

    # ---------------- Samples for misses ----------------
    print("\n[samples] first few missing odds (strict key):")
    miss = strict[~strict_hit].copy()
    cols = [
        "_DateISO","_home_nick","_away_nick","_home_core","_away_core",
        "market_norm","side_norm","__key_strict_odds"
    ]
    print(_head(miss[cols], 8).to_string(index=False))

    print("\nDone.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback, sys
        print("\n[fatal] join_audit crashed with an exception:")
        traceback.print_exc()
        sys.exit(1)

