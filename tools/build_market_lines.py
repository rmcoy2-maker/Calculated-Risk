from pathlib import Path
import pandas as pd, numpy as np

ROOT = Path(r"C:\Projects\edge-finder")
DB   = ROOT / "db"
src  = DB / "odds_books.csv"
sch  = DB / "schedule_2025_template.csv"   # optional for week merge
out  = DB / "market_lines_2025.csv"

def norm_market(x:str):
    s = str(x).strip().lower()
    return {
        "h2h":"H2H","moneyline":"H2H","ml":"H2H","mline":"H2H",
        "spread":"SPREADS","spreads":"SPREADS","handicap":"SPREADS",
        "total":"TOTALS","totals":"TOTALS","o/u":"TOTALS","ou":"TOTALS",
    }.get(s, s.upper())

def american_to_prob(odds):
    try: o = float(str(odds).replace("+",""))
    except: return np.nan
    if o > 0:  return 100.0/(o+100.0)
    if o < 0:  return abs(o)/(abs(o)+100.0)
    return np.nan

def american_to_decimal(odds):
    try: o = float(str(odds).replace("+",""))
    except: return np.nan
    if o > 0:  return 1.0 + (o/100.0)
    if o < 0:  return 1.0 + (100.0/abs(o))
    return np.nan

if not src.exists() or src.stat().st_size <= 5:
    raise SystemExit(f"Missing or empty: {src}")

df = pd.read_csv(src)
df.rename(columns={c:c.strip().lower() for c in df.columns}, inplace=True)

if "odds" not in df.columns and "price" in df.columns:
    df.rename(columns={"price":"odds"}, inplace=True)
if "book" not in df.columns:
    for c in ["sportsbook","book_name","bookmaker","site"]:
        if c in df.columns: df.rename(columns={c:"book"}, inplace=True); break

if "market" in df.columns: df["market"] = df["market"].map(norm_market)
else: df["market"] = "H2H"

if "side" in df.columns:
    df["side"] = (df["side"].astype(str).str.upper()
                  .replace({"HOME":"HOME","H":"HOME","AWAY":"AWAY","A":"AWAY"}))

if "game_id" not in df.columns:
    ht = next((c for c in ["home_team","home","team_home"] if c in df.columns), None)
    at = next((c for c in ["away_team","away","team_away"] if c in df.columns), None)
    df["game_id"] = df[ht].astype(str) + " vs " + df[at].astype(str) if ht and at else df.index.astype(str)

time_col = next((c for c in ["event_time","start_time","ts","timestamp","kickoff","date","game_date"] if c in df.columns), None)
if time_col:
    df["event_time"] = pd.to_datetime(df[time_col], errors="coerce")
    df["season"] = df["event_time"].dt.year
else:
    df["season"] = 2025

# Merge week from schedule if available
if sch.exists() and sch.stat().st_size > 5:
    s = pd.read_csv(sch)
    s.columns = [c.strip().lower() for c in s.columns]
    if "game_id" not in s.columns:
        ht = next((c for c in ["home_team","home","team_home"] if c in s.columns), None)
        at = next((c for c in ["away_team","away","team_away"] if c in s.columns), None)
        if ht and at:
            s["game_id"] = s[ht].astype(str) + " vs " + s[at].astype(str)
    for c in ["season","year"]:
        if c in s.columns: s.rename(columns={c:"season"}, inplace=True)
    if "week" not in s.columns and "date" in s.columns:
        s["week"] = pd.to_datetime(s["date"], errors="coerce").dt.isocalendar().week
    s = s[["game_id","season","week"]].dropna(subset=["game_id"]).drop_duplicates()
    df = df.merge(s, on=["game_id","season"], how="left")
else:
    if "week" not in df.columns: df["week"] = 1

if "odds" in df.columns:
    df["dec_odds"] = df["odds"].apply(american_to_decimal)
    df["imp"]      = df["odds"].apply(american_to_prob)

keep = ["event_time","season","week","market","game_id","book","side","odds","dec_odds","imp"]
for c in ["home_team","away_team"]:
    if c in df.columns: keep.append(c)
keep = [c for c in keep if c in df.columns]
df = df[keep].dropna(subset=["market","game_id"])

out.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(out, index=False)
print(f"Wrote {out} with {len(df):,} rows; cols: {list(df.columns)}")




