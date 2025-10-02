# tools/backfill_edge_dates.py
import re, pandas as pd
from pathlib import Path

EDGES = Path("exports/edges_graded_full_normalized.csv")

ALT = {"NINERS":"49ERS"}
def nickify(x: str) -> str:
    if not isinstance(x, str): return ""
    x = re.sub(r"\s+", " ", x).strip().upper()
    if not x: return ""
    last = x.split()[-1]
    return ALT.get(last, last)

def main():
    e = pd.read_csv(EDGES, low_memory=False)

    # Ensure required cols exist
    for c in ["_date","_home_nick","_away_nick"]:
        if c not in e.columns:
            e[c] = ""
    if e["_home_nick"].eq("").any() and "_home_team" in e.columns:
        e["_home_nick"] = e["_home_nick"].mask(e["_home_nick"].eq(""),
                                               e["_home_team"].astype(str).map(nickify))
    if e["_away_nick"].eq("").any() and "_away_team" in e.columns:
        e["_away_nick"] = e["_away_nick"].mask(e["_away_nick"].eq(""),
                                               e["_away_team"].astype(str).map(nickify))

    # Season/Week columns (either case)
    s_col = "Season" if "Season" in e.columns else ("season" if "season" in e.columns else None)
    w_col = "Week"   if "Week"   in e.columns else ("week"   if "week"   in e.columns else None)
    if not s_col or not w_col:
        # Nothing to do without Season/Week grouping; just rebuild keys & save.
        pass
    else:
        # Build a group-level first-known date table, then merge to fill empties.
        key_cols = [s_col, w_col, "_home_nick", "_away_nick"]
        for c in key_cols:
            e[c] = e[c].astype(str)

        before = int((e["_date"] != "").sum())

        # rows that already have dates
        dated = e.loc[e["_date"].ne(""), key_cols + ["_date"]].copy()
        # keep the first date per group (if duplicates)
        dated = dated.sort_values("_date").drop_duplicates(key_cols, keep="first")
        dated = dated.rename(columns={"_date": "_date_grp"})

        # merge to bring a group date to all members
        e = e.merge(dated, on=key_cols, how="left")
        # fill missing _date from _date_grp
        e["_date"] = e["_date"].mask(e["_date"].eq(""), e["_date_grp"].fillna("")).astype(str)
        e = e.drop(columns=[c for c in ["_date_grp"] if c in e.columns])

        after = int((e["_date"] != "").sum())
        print(f"dates filled (within-edge groups): {after - before:,}")

    # Rebuild keys
    ok = e["_date"].ne("") & e["_home_nick"].ne("") & e["_away_nick"].ne("")
    e["key_home"] = ""
    e["key_away"] = ""
    e.loc[ok, "key_home"] = e.loc[ok, "_home_nick"] + "@" + e.loc[ok, "_date"]
    e.loc[ok, "key_away"] = e.loc[ok, "_away_nick"] + "@" + e.loc[ok, "_date"]

    out = EDGES.with_name(EDGES.stem + "_dated.csv")
    e.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"Saved → {out}")
    print(f"ready rows: {int(ok.sum()):,} / {len(e):,}")

if __name__ == "__main__":
    main()

