import pandas as pd, numpy as np

edges = pd.read_csv("exports/edges.csv")
edges.columns = [c.lower().strip() for c in edges.columns]
odds  = pd.read_csv("exports/historical_odds.csv")

# try to merge on game_id if present, else (date, home, away)
if "game_id" in edges.columns and "game_id_unified" in odds.columns:
    m = edges.merge(odds, left_on="game_id", right_on="game_id_unified", how="left")
else:
    # build a temp gid from edges if possible
    def _gid(r):
        from hashlib import md5
        def norm(x):
            fix={"St. Louis Rams":"Los Angeles Rams","LA Rams":"Los Angeles Rams",
                 "San Diego Chargers":"Los Angeles Chargers","LA Chargers":"Los Angeles Chargers",
                 "Washington Redskins":"Washington Commanders","Washington Football Team":"Washington Commanders",
                 "Oakland Raiders":"Las Vegas Raiders","Phoenix Cardinals":"Arizona Cardinals","Tennessee Oilers":"Tennessee Titans"}
            s=str(x).strip(); return fix.get(s,s)
        d=str(pd.to_datetime(r.get("date", np.nan), errors="coerce").date()) if pd.notna(r.get("date", np.nan)) else ""
        h=norm(r.get("home","")); a=norm(r.get("away",""))
        return md5(f"{d}|{h}|{a}|NFL".encode()).hexdigest()[:12]
    if "game_id" not in edges.columns:
        edges["game_id"] = edges.apply(_gid, axis=1)
    m = edges.merge(odds, left_on="game_id", right_on="game_id_unified", how="left")

def american_from_decimal(dec):
    if pd.isna(dec) or dec<=1: return np.nan
    edge = dec - 1.0
    return -100* (1/edge) if dec<2 else 100*edge

def pick_ml(row):
    side = str(row.get("side","")).lower()
    home = str(row.get("home","")).lower()
    sel  = str(row.get("selection","")).lower()
    # try to infer if selection is home/away
    if side in ("home","h") or (sel and sel==home):
        return row.get("ml_home")
    return row.get("ml_away")

m["odds"] = pd.to_numeric(m.get("odds"), errors="coerce")

# Moneyline fill
is_ml = m.get("market","").astype(str).str.lower().str.contains("moneyline|ml|money line", regex=True)
m.loc[is_ml & m["odds"].isna(), "odds"] = m[is_ml & m["odds"].isna()].apply(pick_ml, axis=1)

# Spread/Total fallback to -110 when no explicit price
is_spread = m.get("market","").astype(str).str.lower().str.contains("spread|ats", regex=True)
is_total  = m.get("market","").astype(str).str.lower().str.contains("total|over/under|ou|o/u", regex=True)
m.loc[(is_spread | is_total) & m["odds"].isna(), "odds"] = -110

# If still missing and we have p_win, synthesize fair odds from p_win
have_p = pd.to_numeric(m.get("p_win"), errors="coerce")
dec = 1.0 / have_p
m.loc[m["odds"].isna() & have_p.notna(), "odds"] = dec.apply(american_from_decimal)

m.to_csv("exports/edges.csv", index=False)
print("Filled odds where possible and rewrote exports/edges.csv")

