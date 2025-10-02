import os, re, sys, pandas as pd
pd.options.mode.copy_on_write = True

repo    = r"C:\Projects\edge-finder"
exports = os.path.join(repo,"exports")
os.makedirs(exports, exist_ok=True)
out     = os.path.join(exports,"scores.csv")

def read_flex(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in [".xlsx", ".xls"]:
        try: return pd.read_excel(path, engine="openpyxl")
        except Exception: 
            try: return pd.read_excel(path)
            except Exception: return pd.DataFrame()
    # try multiple delimiters
    for kw in [dict(), dict(sep="\t"), dict(sep="|"), dict(sep=";")]:
        try:
            return pd.read_csv(path, low_memory=False, **kw)
        except Exception:
            pass
    return pd.DataFrame()

def lower_cols(df):
    df = df.copy(); df.columns = [c.strip().lower() for c in df.columns]; return df

def pick(df, names):
    for n in names:
        if n in df.columns: 
            s = df[n]
            try: s = s.mask(s.astype(str).str.strip().eq(""), pd.NA)
            except: pass
            return s
    return pd.Series([pd.NA]*len(df))

def to_int(s): 
    return pd.to_numeric(s.astype(str).str.replace(r"[^\d-]","", regex=True), errors="coerce").astype("Int64")

def norm_one(df):
    if df.empty: return df
    d = lower_cols(df)
    season = pick(d, ["season","year","yr"])
    week   = pick(d, ["week","wk"])
    home   = pick(d, ["home","home_team","home_abbrev","hometeam","team home abbrev","home team"])
    away   = pick(d, ["away","away_team","away_abbrev","awayteam","team away abbrev","away team"])
    hs     = pick(d, ["home_score","homesc","home_pts","team home score","home score","homescore"," team home score"])
    ays    = pick(d, ["away_score","awaysc","away_pts","team away score","away score","awayscore"," team away score"])
    kt     = pick(d, ["kickoff_ts","kickoff","game_date","start_time","gamedate","datetime","date","gameid","id"])
    out = pd.DataFrame({
        "season": to_int(season),
        "week":   to_int(week),
        "home":   home.astype(str).str.upper().str.strip(),
        "away":   away.astype(str).str.upper().str.strip(),
        "home_score": to_int(hs),
        "away_score": to_int(ays),
        "kickoff_ts": pd.to_datetime(kt, errors="coerce")
    }).dropna(subset=["season","week","home","away","home_score","away_score"], how="any")
    if "kickoff_ts" in out:
        out["kickoff_ts"] = out["kickoff_ts"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    return out

# collect candidates under repo
cands = []
for root,_,files in os.walk(repo):
    for f in files:
        fn = f.lower()
        if any(x in fn for x in ["score","game"]) and any(y in fn for y in ["2017","2018","2019","2020","2021","2022","2023","2024","2025"]):
            cands.append(os.path.join(root,f))
# also include your known historical file if already merged earlier
# but we mainly need >=2017 file
best = None; best_rows = -1; frames = []
for p in cands:
    df = read_flex(p)
    n  = norm_one(df)
    if n.empty: 
        continue
    modern = n[n["season"] >= 2017]
    if len(modern) > 0 and len(modern) > best_rows:
        best = p; best_rows = len(modern)
    frames.append(n)

# If we didn’t find any modern rows, still concatenate whatever we have (historical) so file isn’t empty
merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["season","week","home","away","home_score","away_score","kickoff_ts"])
if best:
    print(f"[ok] Detected modern scores file: {best} (modern rows >=2017: {best_rows})")
else:
    print("[warn] Could not find a modern (>=2017) scores file under repo; merged whatever was found.")

# de-dup by season|week|home|away, keep latest kickoff_ts
if not merged.empty:
    merged["key"] = merged["season"].astype(str)+"|"+merged["week"].astype(str)+"|"+merged["home"]+"|"+merged["away"]
    merged["kt"]  = pd.to_datetime(merged["kickoff_ts"], errors="coerce")
    merged = (merged.sort_values(["key","kt"])
                    .groupby("key", as_index=False)
                    .tail(1)
                    .drop(columns=["key","kt"]))
    merged = merged.sort_values(["season","week","home","away"])
merged.to_csv(out, index=False)
print(f"[ok] scores.csv rows={len(merged)} -> {out}")

