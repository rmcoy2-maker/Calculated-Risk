import os, re, pandas as pd, sys
pd.options.mode.copy_on_write = True

repo    = r"C:\Projects\edge-finder"
exports = os.path.join(repo, "exports")
os.makedirs(exports, exist_ok=True)
srcA    = r"C:\Projects\edge-finder\datasets\nfl\scores\2017-2025_scores.csv"
srcB    = r"C:\Projects\edge-finder\games 1966-2017.txt"
out     = os.path.join(exports, "scores.csv")

def read_any(path):
    if not path or not os.path.exists(path): return pd.DataFrame()
    # try common delimiters
    for kw in [dict(), dict(sep="\t"), dict(sep="|"), dict(sep=";")]:
        try:
            df = pd.read_csv(path, low_memory=False, **kw)
            if df.shape[1] == 1:
                # try to split by whitespace if single fat column
                s = df.columns[0]
                if df[s].astype(str).str.contains(",").mean()>0.5:
                    df = pd.read_csv(path, low_memory=False)
            return df
        except Exception:
            pass
    return pd.DataFrame()

def lower_cols(df):
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def pick(df, names):
    for n in names:
        if n in df.columns: 
            v = df[n]
            try: v = v.mask(v.astype(str).str.strip().eq(""), pd.NA)
            except: pass
            return v
    return pd.Series([pd.NA]*len(df))

def to_int(s):
    return pd.to_numeric(s.astype(str).str.replace(r"[^\d-]","", regex=True), errors="coerce").astype("Int64")

def parse_gid_date(x):
    if not isinstance(x, str): return pd.NaT
    m = re.match(r"^(\d{8})", x)
    if not m: return pd.NaT
    try: return pd.to_datetime(m.group(1), format="%Y%m%d")
    except: return pd.NaT

def to_dt(s):
    try:
        return pd.to_datetime(s, errors="coerce", utc=False)
    except Exception:
        pass
    return pd.to_datetime([parse_gid_date(str(v)) for v in s], errors="coerce")

def normalize(df):
    if df.empty: return df
    d = lower_cols(df)
    season = pick(d, ["season","year","yr","season_year"])
    week   = pick(d, ["week","wk"])
    home   = pick(d, ["home","home_team","home_abbrev","hometeam","team home abbrev","home team"])
    away   = pick(d, ["away","away_team","away_abbrev","awayteam","team away abbrev","away team"])
    hs     = pick(d, ["home_score","homesc","home_pts","team home score","home score","homescore"," team home score"])
    ays    = pick(d, ["away_score","awaysc","away_pts","team away score","away score","awayscore"," team away score"])
    datec  = pick(d, ["kickoff_ts","kickoff","game_date","start_time","gamedate","datetime","date","gameid","id"])

    out = pd.DataFrame({
        "season": to_int(season),
        "week":   to_int(week),
        "home":   home.astype(str).str.strip().str.upper(),
        "away":   away.astype(str).str.strip().str.upper(),
        "home_score": to_int(hs),
        "away_score": to_int(ays),
        "kickoff_ts": to_dt(datec),
    })
    # minimal validity
    out = out.dropna(subset=["season","week","home","away","home_score","away_score"], how="any")
    # string ISO
    if "kickoff_ts" in out:
        out["kickoff_ts"] = pd.to_datetime(out["kickoff_ts"], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
    return out

A = normalize(read_any(srcA))
B = normalize(read_any(srcB))
merged = pd.concat([A,B], ignore_index=True)
if merged.empty:
    print("[error] No rows merged; check file paths & delimiters.", file=sys.stderr)
else:
    # de-dup by season|week|home|away, keep latest kickoff_ts
    merged["key"] = merged["season"].astype(str)+"|"+merged["week"].astype(str)+"|"+merged["home"]+"|"+merged["away"]
    merged["kt"]  = pd.to_datetime(merged["kickoff_ts"], errors="coerce")
    merged = (merged.sort_values(["key","kt"])
                    .groupby("key", as_index=False)
                    .tail(1)
                    .drop(columns=["key","kt"]))
    merged = merged.sort_values(["season","week","home","away"])
merged.to_csv(out, index=False)
print(f"[ok] scores.csv rows={len(merged)} -> {out}")

