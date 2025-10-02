import os, re, numpy as np, pandas as pd
pd.options.mode.copy_on_write = True
repo = r"C:\Projects\edge-finder"; exports = os.path.join(repo,"exports")
edges_p  = os.path.join(exports,"edges.csv")
scores_p = os.path.join(exports,"scores.csv")
out_p    = os.path.join(exports,"edges_graded_wlp.csv")

if not (os.path.exists(edges_p) and os.path.exists(scores_p)):
    print("[warn] missing edges.csv or scores.csv; abort"); raise SystemExit(0)

E = pd.read_csv(edges_p, low_memory=False)
S = pd.read_csv(scores_p, low_memory=False)

# --- normalization helpers
def to_int(s):
    return pd.to_numeric(pd.Series(s).astype(str).str.replace(r"[^\d-]","", regex=True), errors="coerce").astype("Int64")

ALIAS = {
  "ARZ":"ARI","NWE":"NE","NEP":"NE","NOR":"NO","NOS":"NO","TAM":"TB","TBB":"TB",
  "KAN":"KC","KCC":"KC","SFO":"SF","SFN":"SF","GNB":"GB","STL":"LAR",
  "SD":"LAC","SDG":"LAC","OAK":"LV","RAI":"LV","WAS":"WSH","WFT":"WSH","LVR":"LV","JAX":"JAC","CLV":"CLE"
}
def norm_team(x):
    s = str(x).upper().strip()
    return ALIAS.get(s, s)

def parse_ref(ref):
    m = re.match(r"^\s*([A-Za-z]{2,4})@([A-Za-z]{2,4})\s*$", str(ref))
    if not m: return pd.NA, pd.NA
    return norm_team(m.group(1)), norm_team(m.group(2))  # away, home

def parse_side(side):
    # "BUF +1.5" / "GB -3.5" / "BUF" / "NYG ML"
    t = str(side).strip().upper()
    m = re.match(r"^\s*([A-Z]{2,4})", t)
    if not m: return pd.NA
    return norm_team(m.group(1))

def american_profit(odds, stake=1.0):
    try: o = float(odds)
    except: return 0.0
    if np.isnan(o): return 0.0
    if o > 0:  return stake * (o/100.0)
    if o < 0:  return stake * (100.0/abs(o))
    return 0.0

# --- build winners table from scores
s = S.copy()
s["home_abbr"] = s.get("home","").astype(str).map(norm_team)
s["away_abbr"] = s.get("away","").astype(str).map(norm_team)
s["home_score"] = pd.to_numeric(s.get("home_score", np.nan), errors="coerce")
s["away_score"] = pd.to_numeric(s.get("away_score", np.nan), errors="coerce")
s["score_dt"]   = pd.to_datetime(s.get("kickoff_ts", pd.NaT), errors="coerce", utc=True).dt.tz_convert(None)

s = s.dropna(subset=["home_abbr","away_abbr","home_score","away_score"])
s["winner_abbr"] = np.where(s["home_score"]>s["away_score"], s["home_abbr"],
                      np.where(s["away_score"]>s["home_score"], s["away_abbr"], pd.NA))
s["margin"] = (s["home_score"] - s["away_score"]).abs()

# --- prep edges, parse pick + matchup
e = E.copy()
e["row_id"]   = e.index
e["pick_team"] = e.get("side","").map(parse_side)
aw, ho = zip(*e.get("ref","").map(parse_ref))
e["away_abbr"] = aw; e["home_abbr"] = ho
e["edge_dt"]   = pd.to_datetime(e.get("ts", pd.NaT), errors="coerce", utc=True).dt.tz_convert(None)

# we only grade rows where we know the teams (from ref) AND we can parse a pick team
cand = e[e["home_abbr"].notna() & e["away_abbr"].notna() & e["pick_team"].notna()].copy()
if cand.empty:
    # nothing to grade, just write back original with result/profit if present
    out = E.copy()
    if "result" not in out.columns: out["result"] = np.nan
    if "profit" not in out.columns: out["profit"] = np.nan
    out.to_csv(out_p, index=False)
    print(f"[ok] wrote graded (none graded): {out_p}  graded_rows=0 total_edges={len(out)}")
    raise SystemExit(0)

# join on matchup, then pick nearest by date (fallback: latest game if edge_dt missing)
j = cand.merge(s[["home_abbr","away_abbr","winner_abbr","score_dt","home_score","away_score"]],
               on=["home_abbr","away_abbr"], how="left")
# handle missing dates
ref_date = j["edge_dt"].copy()
ref_date = ref_date.fillna(pd.Timestamp("2100-01-01"))  # pick the latest score if no edge ts
j["day_diff"] = (ref_date - j["score_dt"]).abs().dt.days
j = j.dropna(subset=["score_dt"])  # keep rows that had a game

# keep single nearest score per edge row
j = j.sort_values(["row_id","day_diff"]).drop_duplicates("row_id", keep="first").copy()

# grade by winner only
j["result_new"] = np.where(j["winner_abbr"].eq(j["pick_team"]), "win",
                    np.where(j["home_score"].eq(j["away_score"]), "push", "loss"))

# profit (1u stake default unless provided)
stake = pd.to_numeric(E.get("stake", 1.0), errors="coerce").fillna(1.0)
odds  = pd.to_numeric(E.get("odds", np.nan), errors="coerce")
winp  = american_profit(odds, stake)
profit_new = np.where(j["result_new"]=="win", winp,
               np.where(j["result_new"]=="loss", -stake.reindex(j["row_id"]).values, 0.0))

# write back to edges
out = E.copy()
if "result" not in out.columns: out["result"] = np.nan
if "profit" not in out.columns: out["profit"] = np.nan
out.loc[j["row_id"], "result"] = j["result_new"].values
out.loc[j["row_id"], "profit"] = profit_new

out.to_csv(out_p, index=False)
print(f"[ok] wrote graded (winner-only): {out_p}  graded_rows={len(j)}  total_edges={len(out)}")

