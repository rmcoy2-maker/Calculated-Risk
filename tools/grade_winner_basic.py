import os, re, numpy as np, pandas as pd
pd.options.mode.copy_on_write = True
repo = r"C:\Projects\edge-finder"; exports = os.path.join(repo,"exports")
edges_p  = os.path.join(exports, "edges.csv")
scores_p = os.path.join(exports, "scores.csv")
out_p    = os.path.join(exports, "edges_graded_wlp.csv")

if not (os.path.exists(edges_p) and os.path.exists(scores_p)):
    print("[warn] missing edges.csv or scores.csv; abort"); raise SystemExit(0)

E = pd.read_csv(edges_p, low_memory=False)
S = pd.read_csv(scores_p, low_memory=False)

def to_int(s):
    return pd.to_numeric(pd.Series(s).astype(str).str.replace(r"[^\d-]","", regex=True),
                         errors="coerce").astype("Int64")

# normalize team tokens to edges-style abbr
ALIAS = {
  "ARZ":"ARI","NWE":"NE","NEP":"NE","NOR":"NO","NOS":"NO","TAM":"TB","TBB":"TB",
  "KAN":"KC","KCC":"KC","SFO":"SF","SFN":"SF","GNB":"GB","STL":"LAR",
  "SD":"LAC","SDG":"LAC","OAK":"LV","RAI":"LV","WAS":"WSH","WFT":"WSH","LVR":"LV","JAX":"JAC","CLV":"CLE"
}
def norm_team(x):
    s = str(x).upper().strip()
    return ALIAS.get(s, s)

def parse_ref(ref):
    # 'AWAY@HOME'
    m = re.match(r"^\s*([A-Za-z]{2,4})@([A-Za-z]{2,4})\s*$", str(ref))
    if not m: return pd.NA, pd.NA
    return norm_team(m.group(1)), norm_team(m.group(2))

def parse_pick(side):
    # 'BUF +1.5', 'NYJ ML', 'GB'
    t = str(side).upper().strip()
    m = re.match(r"^([A-Z]{2,4})", t)
    return norm_team(m.group(1)) if m else pd.NA

def american_profit(odds, stake=1.0):
    try: o = float(odds)
    except: return 0.0
    if np.isnan(o): return 0.0
    return stake*(o/100.0) if o>0 else (stake*(100.0/abs(o)) if o<0 else 0.0)

# ---------- build winners lookup from scores ----------
s = S.copy()
s["seasonN"] = to_int(s.get("season"))
s["weekN"]   = to_int(s.get("week"))
s["home"]    = s.get("home","").astype(str).map(norm_team)
s["away"]    = s.get("away","").astype(str).map(norm_team)
s["hs"]      = pd.to_numeric(s.get("home_score", np.nan), errors="coerce")
s["as"]      = pd.to_numeric(s.get("away_score", np.nan), errors="coerce")
s = s.dropna(subset=["seasonN","home","away","hs","as"])

# winner (ties = NaN/push)
s["winner"]  = np.where(s["hs"]>s["as"], s["home"], np.where(s["as"]>s["hs"], s["away"], pd.NA))

# de-dup helpers
# exact season+week+teams key
s_sw = s.sort_values(["seasonN","weekN"]).drop_duplicates(["seasonN","weekN","home","away"], keep="last")
# season+teams key (keep latest week of that season)
s_s  = s.sort_values(["seasonN","weekN"]).drop_duplicates(["seasonN","home","away"], keep="last")

# ---------- prep edges ----------
e = E.copy()
e["row_id"]   = e.index
e["seasonN"]  = to_int(e.get("season"))
e["weekN"]    = to_int(e.get("week"))
aw, ho        = zip(*e.get("ref","").map(parse_ref))
e["away"]     = aw; e["home"] = ho
e["pick"]     = e.get("side","").map(parse_pick)
e["stakeN"]   = pd.to_numeric(e.get("stake", 1.0), errors="coerce").fillna(1.0)
e["oddsN"]    = pd.to_numeric(e.get("odds", np.nan), errors="coerce")

# derive season from ts if season missing
edge_year = pd.to_datetime(e.get("ts", pd.NaT), errors="coerce").dt.year
e["seasonN"] = e["seasonN"].fillna(edge_year)

# candidates: must know teams and pick
c = e[e["home"].notna() & e["away"].notna() & e["pick"].notna()].copy()

# A) try strict season+week+teams
j1 = c.merge(s_sw[["seasonN","weekN","home","away","winner","hs","as"]],
             on=["seasonN","weekN","home","away"], how="left", suffixes=("","_s"))
# B) fill misses using season+teams (latest week for that season)
miss = j1["winner"].isna()
if miss.any():
    j2 = j1[miss].drop(columns=["winner","hs","as"])
    j2 = j2.merge(s_s[["seasonN","home","away","winner","hs","as"]],
                  on=["seasonN","home","away"], how="left")
    j1.loc[miss, ["winner","hs","as"]] = j2[["winner","hs","as"]].values

# C) as last resort, try swapped home/away (in case of orientation mismatches)
miss2 = j1["winner"].isna()
if miss2.any():
    j3 = j1[miss2].drop(columns=["winner","hs","as"])
    s_swapped = s_s.rename(columns={"home":"away","away":"home"})
    j3 = j3.merge(s_swapped[["seasonN","home","away","winner","hs","as"]], on=["seasonN","home","away"], how="left")
    # winner is still correct (one of the two teams)
    j1.loc[miss2, ["winner","hs","as"]] = j3[["winner","hs","as"]].values

graded = j1.dropna(subset=["winner"]).copy()
if graded.empty:
    out = E.copy()
    if "result" not in out.columns: out["result"] = np.nan
    if "profit" not in out.columns: out["profit"] = np.nan
    out.to_csv(out_p, index=False)
    print(f"[ok] wrote graded (winner-basic): {out_p}  graded_rows=0  total_edges={len(out)}")
    raise SystemExit(0)

# compute W/L/Push
graded["result_new"] = np.where(graded["winner"].eq(graded["pick"]), "win",
                         np.where(graded["hs"].eq(graded["as"]), "push", "loss"))

# profit (American odds; default stake 1 if missing)
winp = american_profit(graded["oddsN"], graded["stakeN"])
graded["profit_new"] = np.where(graded["result_new"]=="win", winp,
                         np.where(graded["result_new"]=="loss", -graded["stakeN"], 0.0))

# write back by row index
out = E.copy()
if "result" not in out.columns: out["result"] = np.nan
if "profit" not in out.columns: out["profit"] = np.nan
g = graded.set_index("row_id")
out.loc[g.index, "result"] = g["result_new"].values
out.loc[g.index, "profit"] = g["profit_new"].values

out.to_csv(out_p, index=False)
print(f"[ok] wrote graded (winner-basic): {out_p}  graded_rows={len(g)}  total_edges={len(out)}")

