#!/usr/bin/env python
import pandas as pd
from pathlib import Path

src = Path("exports/results.csv")
df = pd.read_csv(src)

# keep if we have dates
if "date" not in df.columns:
    raise SystemExit("results.csv has no 'date' column; cannot infer weeks.")

df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["season"] = pd.to_numeric(df.get("season"), errors="coerce").astype("Int64")

# Only fill where week is missing
mask_missing = df.get("week").isna() if "week" in df.columns else pd.Series(True, index=df.index)

# Compute a stable within-season week index based on the actual calendar week
tmp = df.loc[mask_missing, ["season","date"]].copy()
iso = tmp["date"].dt.isocalendar()
tmp["iso_year"] = iso.year
tmp["iso_week"] = iso.week

# Dense-rank (iso_year, iso_week) within each season to produce 1..N
tmp["week_inferred"] = (
    tmp.groupby("season", dropna=False)[["iso_year","iso_week"]]
       .apply(lambda g: pd.factorize(list(zip(g["iso_year"], g["iso_week"])), sort=True)[0] + 1)
       .reset_index(level=0, drop=True)
)

# Write back
if "week" not in df.columns:
    df["week"] = pd.NA

df.loc[mask_missing, "week"] = pd.to_numeric(tmp["week_inferred"], errors="coerce").astype("Int64")

out = Path("exports/results_with_weeks.csv")
df.to_csv(out, index=False)
print(f"[write] {out} rows={len(df)} with inferred weeks for {int(mask_missing.sum())} rows")

