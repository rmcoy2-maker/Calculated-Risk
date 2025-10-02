import os, re, sys, pandas as pd
from datetime import datetime

repo = r"C:\Projects\edge-finder"
exports = os.path.join(repo, "exports")
os.makedirs(exports, exist_ok=True)

srcA = r"C:\Projects\edge-finder\data\2017-2025_scores.csv"
srcB = r"C:\Projects\edge-finder\data\games 1966-2017.txt"
out  = os.path.join(exports, "scores.csv")

def read_any(path):
    if not os.path.exists(path): return pd.DataFrame()
    try:
        return pd.read_csv(path, engine="python")
    except Exception:
        # try tab or pipe
        for sep in ["\t","|",";"]:
            try: return pd.read_csv(path, sep=sep, engine="python")
            except Exception: pass
    return pd.DataFrame()

def lower_cols(df):
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def pick(df, names):
    for n in names:
        if n in df.columns:
            v = df[n]
            # treat empty strings as NA
            try: v = v.mask(v.astype(str).str.strip().eq(""), pd.NA)
            except Exception: pass
            if v.notna().any(): return v
    return pd.Series([pd.NA]*len(df))

def to_int(s):
    return pd.to_numeric(s.astype(str).str.replace(r"[^\d-]","", regex=True), errors="coerce").astype("Int64")

def parse_gid_date(x: str):
    if not isinstance(x,str): return pd.NaT
    m = re.match(r"^(\d{8})", x)
    if not m: return pd.NaT
    try: return pd.to_datetime(m.group(1), format="%Y%m%d")
    except Exception: return pd.NaT

def to_dt(s):
    # try natural parse, else yyyymmdd via GameID, else NaT
    try:
        dt = pd.to_datetime(s, errors="coerce", utc=False)
        return dt
    except Exception:
        pass
    return pd.to_datetime([parse_gid_date(str(v)) for v in s], errors="coerce")

def normalize(df):
    if df.empty: return df
    df = lower_cols(df)
    season = pick(df, ["season","year","yr","season_year"])
    week   = pick(df, ["week","wk"])
    home   = pick(df, ["home","home_team","home_abbrev","hometeam","team home abbrev","home team"])
    away   = pick(df, ["away","away_team","away_abbrev","awayteam","team away abbrev","away team"])
    hs     = pick(df, ["home_score","homesc","home_pts","team home score","home score","homescore"])
    ays    = pick(df, ["away_score","awaysc","away_pts","team away score","away score","awayscore"])
    kt     = pick(df, ["kickoff_ts","kickoff","game_date","start_time","gamedate","datetime","date","gameid","id"])

    out = pd.DataFrame({
        "season": to_int(season),
        "week":   to_int(week),
        "home":   home.astype(str).str.strip(),
        "away":   away.astype(str).str.strip(),
        "home_score": to_int(hs),
        "away_score": to_int(ays),
        "kickoff_ts": to_dt(kt)
    })
    # if kickoff_ts full NaT but gameid contains date, try that
    if out["kickoff_ts"].isna().all() and "gameid" in df.columns:
        out["kickoff_ts"] = to_dt(df["gameid"])
    # minimal validity
    out = out.dropna(subset=["season","week","home","away","home_score","away_score"], how="any")
    # stringify kickoff_ts ISO if present
    if "kickoff_ts" in out:
        try: out["kickoff_ts"] = pd.to_datetime(out["kickoff_ts"], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception: out["kickoff_ts"] = ""
    return out

A = normalize(read_any(srcA))
B = normalize(read_any(srcB))
merged = pd.concat([A, B], ignore_index=True)
if merged.empty:
    print("[error] No rows found in either source.", file=sys.stderr)
    merged = pd.DataFrame(columns=["season","week","home","away","home_score","away_score","kickoff_ts"])

# de-dup by season|week|home|away, keep the one with latest kickoff_ts
merged["key"] = merged["season"].astype(str)+"|"+merged["week"].astype(str)+"|"+merged["home"]+"|"+merged["away"]
merged["kt"] = pd.to_datetime(merged["kickoff_ts"], errors="coerce")
merged = (merged.sort_values(["key","kt"])
                .groupby("key", as_index=False)
                .tail(1)
                .drop(columns=["key","kt"]))
merged = merged.sort_values(["season","week","home","away"]).reset_index(drop=True)
merged.to_csv(out, index=False)
print(f"[ok] scores.csv rows={len(merged)} -> {out}")

