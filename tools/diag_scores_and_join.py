import os, sys, re, pandas as pd
pd.options.display.width = 200
repo    = r"C:\Projects\edge-finder"
exports = os.path.join(repo,"exports")
srcA    = r"2017-2025_scores.csv"
srcB    = r"games 1966-2017.txt"
edges_p = os.path.join(exports,"edges.csv")
scores_p= os.path.join(exports,"scores.csv")

def read_any(path):
    if not os.path.exists(path): return pd.DataFrame()
    for kw in [dict(), dict(sep="\t"), dict(sep="|"), dict(sep=";")]:
        try:
            return pd.read_csv(path, low_memory=False, **kw)
        except Exception:
            pass
    return pd.DataFrame()

def cols(df): return list(df.columns)

def quick(df, name):
    print(f"\n== {name} ==")
    print(f"rows={len(df)}")
    if len(df)==0: return
    print("columns:", cols(df))
    print(df.head(3).to_string(index=False))

A = read_any(srcA); B = read_any(srcB)
quick(A, f"Source A ({os.path.basename(srcA)})")
quick(B, f"Source B ({os.path.basename(srcB)})")

# save small samples so you can inspect in Excel
if len(A): A.head(100).to_csv(os.path.join(exports,"diag_srcA_sample.csv"), index=False)
if len(B): B.head(100).to_csv(os.path.join(exports,"diag_srcB_sample.csv"), index=False)

# check current scores.csv
S = read_any(scores_p)
quick(S, "Existing scores.csv (merged)")

# try to infer candidate columns for season/week/home/away/scores/date
def lower_cols(df):
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def present(df,*names):
    df = lower_cols(df)
    return [n for n in names if n in df.columns]

def find(df, candidates):
    df = lower_cols(df)
    for c in candidates:
        if c in df.columns:
            return c
    return None

if len(S)==0:
    for label, df in [("A",A),("B",B)]:
        if len(df)==0: 
            print(f"\n-- Heuristics for {label}: (no rows)"); 
            continue
        d = lower_cols(df)
        season = find(d, ["season","year","yr"])
        week   = find(d, ["week","wk"])
        home   = find(d, ["home","home_team","home_abbrev","hometeam","team home abbrev","home team"])
        away   = find(d, ["away","away_team","away_abbrev","awayteam","team away abbrev","away team"])
        hs     = find(d, ["home_score","homesc","home_pts","team home score","home score","homescore"])
        ays    = find(d, ["away_score","awaysc","away_pts","team away score","away score","awayscore"])
        datec  = find(d, ["kickoff_ts","kickoff","game_date","start_time","gamedate","datetime","date","gameid","id"])
        print(f"\n-- Heuristics for {label}:")
        print(" season:", season, " week:", week, " home:", home, " away:", away, " home_score:", hs, " away_score:", ays, " date:", datec)

# --------- EDGES vs SCORES JOIN DIAG ----------
E = read_any(edges_p)
quick(E, "edges.csv")
if len(E)==0:
    print("\n[warn] edges.csv has 0 rows — join diagnostics skipped.")
    sys.exit(0)

# Normalize team/keys
def norm_team(s):
    s = (str(s) if pd.notna(s) else "").upper().strip()
    # alias map (expand as needed)
    alias = {
        "JAX":"JAC","JAGS":"JAC",
        "NWE":"NE","NEP":"NE",
        "KAN":"KC","KCC":"KC",
        "SFO":"SF","SFN":"SF",
        "TAM":"TB","TBB":"TB",
        "NOR":"NO","NOS":"NO",
        "GNB":"GB",
        "RAM":"LAR","STL":"LAR","STL RAMS":"LAR",
        "SD":"LAC","SDG":"LAC",
        "OAK":"LV","RAI":"LV",
        "HOU TEXANS":"HOU","ARI":"ARZ","ARZ":"ARI",
        "WAS":"WSH","WSH FOOTBALL TEAM":"WSH","WFT":"WSH","WASHINGTON COMMANDERS":"WSH",
        "LA":"LAR",   # ambiguous; favors Rams historically
        "BAL RAVENS":"BAL","CLEV":"CLE","CLV":"CLE",
        "SAINTS":"NO","PACKERS":"GB","PATS":"NE","NINERS":"SF","BUCS":"TB","JETS":"NYJ","GIANTS":"NYG",
        "SEAHAWKS":"SEA","CHARGERS":"LAC","RAIDERS":"LV","REDSKINS":"WSH"
    }
    return alias.get(s, s)

def to_int_series(x):
    return pd.to_numeric(pd.Series(x).astype(str).str.replace(r"[^\d-]","", regex=True), errors="coerce").astype("Int64")

def pick1(df, *names):
    for n in names:
        if n in df.columns: return n
    return None

# Pick columns from edges
e = lower_cols(E)
e_season = pick1(e, "season","year")
e_week   = pick1(e, "week","wk")
e_home   = pick1(e, "_home_abbr_norm","home","home_team","home_abbr","homeabbr")
e_away   = pick1(e, "_away_abbr_norm","away","away_team","away_abbr","awayabbr")
if not all([e_season,e_week,e_home,e_away]):
    print("\n[warn] edges.csv missing one of required columns (season/week/home/away). Found:",
          e_season,e_week,e_home,e_away)

eN = pd.DataFrame({
    "season": to_int_series(e[e_season] if e_season else None),
    "week":   to_int_series(e[e_week] if e_week else None),
    "home":   e[e_home].astype(str).map(norm_team) if e_home else "",
    "away":   e[e_away].astype(str).map(norm_team) if e_away else "",
})
eN["ekey"] = eN["season"].astype(str)+"|"+eN["week"].astype(str)+"|"+eN["home"]+"|"+eN["away"]

# Prepare scores keys (if present)
if len(S)==0:
    print("\n[warn] scores.csv has 0 rows — cannot compute match rate yet.")
else:
    s = lower_cols(S)
    sN = pd.DataFrame({
        "season": to_int_series(s[pick1(s,"season","year")]),
        "week":   to_int_series(s[pick1(s,"week","wk")]),
        "home":   s[pick1(s,"home","home_team","home_abbrev")].astype(str).map(norm_team),
        "away":   s[pick1(s,"away","away_team","away_abbrev")].astype(str).map(norm_team),
    })
    sN["skey"] = sN["season"].astype(str)+"|"+sN["week"].astype(str)+"|"+sN["home"]+"|"+sN["away"]

    merged = eN.merge(sN, left_on="ekey", right_on="skey", how="left", indicator=True)
    match_rate = (merged["_merge"]=="both").mean()
    print(f"\n== JOIN DIAGNOSTIC ==")
    print(f"edges rows={len(eN)} | scores rows={len(sN)} | match rate={match_rate:.3%}")

    # Top reasons by season/week missingness
    miss = merged[merged["_merge"]!="both"].copy()
    miss["why"] = ""
    miss.loc[miss["season_x"].isna() | miss["week_x"].isna(), "why"] = "edges missing season/week"
    miss.loc[(miss["season_x"].notna()) & (miss["week_x"].notna()) & (miss["skey"].isna()), "why"] = "no key in scores"
    print(miss["why"].value_counts().head(5).to_string())

    # Save detailed unmatched for inspection
    out_unmatched = os.path.join(exports,"diag_unmatched_edges.csv")
    keep_cols = ["season_x","week_x","home","away","ekey"]
    miss[keep_cols].rename(columns={"season_x":"season","week_x":"week"}).to_csv(out_unmatched, index=False)
    print(f"[ok] wrote {out_unmatched}  (rows={len(miss)})")

