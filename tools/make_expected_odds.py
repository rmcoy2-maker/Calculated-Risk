import pandas as pd, numpy as np, sys

src = r"exports/historical_odds.csv"
dst = r"exports/historical_odds_expected.csv"

odds = pd.read_csv(src, dtype=str, low_memory=False)
for c in ("market","side"):
    if c in odds.columns: odds[c] = odds[c].str.lower()
odds["line"]  = pd.to_numeric(odds.get("line"), errors="coerce")
odds["price"] = pd.to_numeric(odds.get("price"), errors="coerce")

# Build columns backtest.py expects
odds["ml_home"] = np.where((odds["market"]=="moneyline") & (odds["side"]=="home"), odds["price"], np.nan)
odds["ml_away"] = np.where((odds["market"]=="moneyline") & (odds["side"]=="away"), odds["price"], np.nan)
odds["spread_close"] = np.where(odds["market"]=="spread",
                                np.where(odds["side"]=="home", odds["line"], -odds["line"]),
                                np.nan)
odds["total_close"] = np.where(odds["market"]=="total", odds["line"], np.nan)

# Keys to group by (prefer game_id if present)
keys = [k for k in ("game_id","season","week","home_team","away_team","game_date") if k in odds.columns]
if not keys: 
    print("[error] no keys to group by"); sys.exit(1)

agg = { "ml_home":"max","ml_away":"max","spread_close":"max","total_close":"max" }
for k in keys: agg[k] = "first"
merged = odds.groupby(keys, dropna=False).agg(agg).reset_index()

merged.to_csv(dst, index=False)
print(f"[ok] wrote {dst} rows={len(merged)}")

