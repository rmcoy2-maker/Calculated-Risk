import os, re, pandas as pd

src = os.path.join("exports","scores.csv")
out = os.path.join("exports","scores_clean.csv")

df = pd.read_csv(src, low_memory=False)

# clean headers: strip/commas->underscores/lower
df.columns = [re.sub(r"[\s,]+","_", str(c)).strip("_").lower() for c in df.columns]

# rename to canonical
rename = {
    "team_home":"home_team","home_name":"home_team","home":"home_team",
    "team_away":"away_team","away_name":"away_team","away":"away_team",
    "home_pts":"home_score","final_home_pts":"home_score","home_points":"home_score",
    "away_pts":"away_score","final_away_pts":"away_score","away_points":"away_score",
    "wk":"week","game_week":"week","game_date":"date"
}
df = df.rename(columns=rename)

# coerce types
for c in ("season","week","home_score","away_score"):
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

# uppercase team names
for c in ("home_team","away_team"):
    if c in df.columns:
        df[c] = df[c].astype(str).str.strip().str.upper()

# keep useful columns
keep = [c for c in ("season","week","date","home_team","away_team","home_score","away_score","game_id") if c in df.columns]
if keep:
    df = df[keep]

df.to_csv(out, index=False, encoding="utf-8-sig")
print(f"[ok] wrote {out} rows={len(df)} cols={list(df.columns)}")

