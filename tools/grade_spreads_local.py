import os, re, numpy as np, pandas as pd
pd.options.mode.copy_on_write = True
repo = r"C:\Projects\edge-finder"; exports = os.path.join(repo,"exports")
edges_p  = os.path.join(exports, "edges.csv")
scores_p = os.path.join(exports, "scores.csv")
out_p    = os.path.join(exports, "edges_graded_wlp.csv")

if not (os.path.exists(edges_p) and os.path.exists(scores_p)):
    print("[warn] missing edges.csv or scores.csv; abort grading"); raise SystemExit(0)

E = pd.read_csv(edges_p, low_memory=False)
S = pd.read_csv(scores_p, low_memory=False)

def to_int(s):
    return pd.to_numeric(pd.Series(s).astype(str).str.replace(r"[^\d-]","", regex=True), errors="coerce").astype("Int64")

def norm_team(x):
    s = str(x).upper().strip()
    alias = {
        "JAX":"JAC","JAGS":"JAC","NWE":"NE","NEP":"NE","KAN":"KC","KCC":"KC","SFO":"SF","SFN":"SF",
        "TAM":"TB","TBB":"TB","NOR":"NO","NOS":"NO","GNB":"GB","STL":"LAR","RAM":"LAR",
        "SD":"LAC","SDG":"LAC","OAK":"LV","RAI":"LV","ARI":"ARZ","ARZ":"ARI",
        "WAS":"WSH","WFT":"WSH","WASHINGTON COMMANDERS":"WSH","LVR":"LV","CLV":"CLE"
    }
    return alias.get(s, s)

def parse_ref(ref):
    m = re.match(r"^\s*([A-Za-z]{2,4})@([A-Za-z]{2,4})\s*$", str(ref))
    if not m: return pd.NA, pd.NA
    away, home = norm_team(m.group(1)), norm_team(m.group(2))
    return away, home

def parse_side(side):
    m = re.match(r"^\s*([A-Za-z]{2,4})\s*([+-]?\d+(?:\.\d+)?)\s*$", str(side).strip())
    if not m: return pd.NA, pd.NA
    return norm_team(m.group(1)), float(m.group(2))

def american_profit(odds, stake=1.0):
    try: o = float(odds)
    except: return 0.0
    if np.isnan(o): return 0.0
    if o > 0:  return stake * (o/100.0)
    if o < 0:  return stake * (100.0/abs(o))
    return 0.0

# --- Prep edges
e = E.copy()
e["row_id"]  = e.index
e["seasonN"] = to_int(e.get("season"))
e["weekN"]   = to_int(e.get("week"))
ah           = e.get("ref","").map(parse_ref)
e["away_abbr"] = [a for a,_ in ah]
e["home_abbr"] = [h for _,h in ah]
pick         = e.get("side","").map(parse_side)
e["pick_team"] = [t for t,_ in pick]
e["pick_line"] = pd.to_numeric([ln for _,ln in pick], errors="coerce")
e["market_lc"] = e.get("market","").astype(str).str.lower()
e["oddsN"]     = pd.to_numeric(e.get("odds", np.nan), errors="coerce")
e["stakeN"]    = pd.to_numeric(e.get("stake", 1.0), errors="coerce").fillna(1.0)

# Parse edge ts -> UTC then drop tz (prevents tz-aware vs tz-naive errors)
e["edge_dt"] = pd.to_datetime(e.get("ts", pd.NaT), errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()

# --- Prep scores
s = S.copy()
s["seasonN"]   = to_int(s.get("season"))
s["weekN"]     = to_int(s.get("week"))
s["home_abbr"] = s.get("home","").astype(str).map(norm_team)
s["away_abbr"] = s.get("away","").astype(str).map(norm_team)
s["score_dt"]  = pd.to_datetime(s.get("kickoff_ts", pd.NaT), errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()

# --- Candidates
cand = e[
    e["market_lc"].str.contains("spread", na=False) &
    e["pick_team"].notna() & e["pick_line"].notna() &
    e["home_abbr"].notna() & e["away_abbr"].notna()
].copy()

def grade_join(df):
    df = df.copy()
    df["t_score"] = np.where(df["pick_team"].eq(df["home_abbr"]), df["home_score"],
                     np.where(df["pick_team"].eq(df["away_abbr"]), df["away_score"], np.nan))
    df["o_score"] = np.where(df["pick_team"].eq(df["home_abbr"]), df["away_score"],
                     np.where(df["pick_team"].eq(df["away_abbr"]), df["home_score"], np.nan))
    df = df.dropna(subset=["t_score","o_score"])
    if df.empty: return pd.DataFrame()
    df["edge_spread"] = df["t_score"] + df["pick_line"] - df["o_score"]
    df["result_new"]  = np.where(df["edge_spread"]>0,"win",np.where(df["edge_spread"]<0,"loss","push"))
    winp = american_profit(df["oddsN"], df["stakeN"])
    df["profit_new"] = np.where(df["result_new"]=="win", winp, np.where(df["result_new"]=="loss", -df["stakeN"], 0.0))
    return df[["row_id","result_new","profit_new"]]

out = E.copy()
if "result" not in out.columns: out["result"] = np.nan
if "profit" not in out.columns: out["profit"] = np.nan
graded = pd.Index([])

# A) Date proximity (same season & teams), pick nearest within 10 days
if not cand.empty:
    j = cand.merge(
        s[["seasonN","home_abbr","away_abbr","home_score","away_score","score_dt"]],
        on=["seasonN","home_abbr","away_abbr"], how="left"
    )
    j = j.dropna(subset=["home_score","away_score","score_dt","edge_dt"]).copy()
    if not j.empty:
        j["day_diff"] = (j["edge_dt"] - j["score_dt"]).abs().dt.days
        j = j.sort_values(["row_id","day_diff"]).drop_duplicates("row_id", keep="first")
        j10 = j[j["day_diff"] <= 10]
        g = grade_join(j10)
        if not g.empty:
            g = g.set_index("row_id")
            out.loc[g.index, "result"] = g["result_new"].values
            out.loc[g.index, "profit"] = g["profit_new"].values
            graded = graded.union(pd.Index(g.index))

# B) Fallback: strict season+week+teams for rows still ungraded
rem = cand[~cand["row_id"].isin(graded)].copy()
if not rem.empty:
    j2 = rem.merge(
        s[["seasonN","weekN","home_abbr","away_abbr","home_score","away_score"]],
        on=["seasonN","weekN","home_abbr","away_abbr"], how="left"
    ).dropna(subset=["home_score","away_score"])
    g2 = grade_join(j2)
    if not g2.empty:
        g2 = g2.set_index("row_id")
        out.loc[g2.index, "result"] = g2["result_new"].values
        out.loc[g2.index, "profit"] = g2["profit_new"].values
        graded = graded.union(pd.Index(g2.index))

# C) Last-resort: same season & teams, pick absolute nearest (no 10d cap)
rem2 = cand[~cand["row_id"].isin(graded)].copy()
if not rem2.empty:
    j3 = rem2.merge(
        s[["seasonN","home_abbr","away_abbr","home_score","away_score","score_dt"]],
        on=["seasonN","home_abbr","away_abbr"], how="left"
    ).dropna(subset=["home_score","away_score","score_dt","edge_dt"])
    if not j3.empty:
        j3["day_diff"] = (j3["edge_dt"] - j3["score_dt"]).abs().dt.days
        j3 = j3.sort_values(["row_id","day_diff"]).drop_duplicates("row_id", keep="first")
        g3 = grade_join(j3)
        if not g3.empty:
            g3 = g3.set_index("row_id")
            out.loc[g3.index, "result"] = g3["result_new"].values
            out.loc[g3.index, "profit"] = g3["profit_new"].values
            graded = graded.union(pd.Index(g3.index))

out.to_csv(out_p, index=False)
print(f"[ok] wrote graded edges: {out_p}  graded_rows={len(graded)}  total_edges={len(out)}")

