# tools_make_edges_master.py
import pandas as pd, numpy as np
from pathlib import Path

exp = Path(r"C:\Projects\edge-finder\exports")
src = exp / "edges_clean.csv"
out = exp / "edges_master.csv"

def title_team(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip().str.title()
    return s.str.replace("49Ers","49ers", regex=False)

def norm_market(m: str) -> str:
    if not isinstance(m, str): return ""
    m = m.strip().lower()
    if m in ("h2h","ml","moneyline","money line"): return "H2H"
    if m in ("spread","spreads","point spread"):    return "SPREADS"
    if m in ("total","totals","over/under","ou"):   return "TOTALS"
    return m.upper()

df0 = pd.read_csv(src, low_memory=False)

df = pd.DataFrame()
df["Season"]   = pd.to_numeric(df0.get("season"), errors="coerce").astype("Int64")
df["Week"]     = pd.to_numeric(df0.get("week"), errors="coerce").astype("Int64")
df["HomeTeam"] = title_team(df0.get("home_team").astype(str))
df["AwayTeam"] = title_team(df0.get("away_team").astype(str))
df["market"]   = df0.get("market","").astype(str).map(norm_market)

# 👉 FIX: use .str.lower() on Series
df["side"]     = df0.get("side","").astype(str).str.lower().str.strip()

df["line"]     = pd.to_numeric(df0.get("line"), errors="coerce")
df["odds"]     = pd.to_numeric(df0.get("price", df0.get("odds")), errors="coerce")
df["stake"]    = pd.to_numeric(df0.get("stake"), errors="coerce").fillna(1.0)
df["date"]     = pd.to_datetime(df0.get("game_date"), errors="coerce").dt.date.astype(str)
df["game_id"]  = df0.get("game_id")

# selection team for H2H/SPREADS
sel = np.where(df["side"].isin(["home","away"]),
               np.where(df["side"].eq("home"), df["HomeTeam"], df["AwayTeam"]),
               np.nan)
df["team"] = sel

# If side matches an actual team name, use it as the selection
def lower(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().str.strip()

home_match = df["team"].isna() & (lower(df["side"]) == lower(df["HomeTeam"]))
away_match = df["team"].isna() & (lower(df["side"]) == lower(df["AwayTeam"]))
df.loc[home_match, "team"] = df.loc[home_match, "HomeTeam"]
df.loc[away_match, "team"] = df.loc[away_match, "AwayTeam"]

# Keep only usable rows
df = df.dropna(subset=["Season","HomeTeam","AwayTeam","market"]).reset_index(drop=True)
df.to_csv(out, index=False, encoding="utf-8-sig")
print(f"Wrote {out} rows: {len(df)}")

