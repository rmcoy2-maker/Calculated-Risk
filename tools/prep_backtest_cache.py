import os, numpy as np, pandas as pd

srcs = ["exports/edges_graded_plus.csv","exports/edges_graded.csv","exports/edges.csv"]
src = next((p for p in srcs if os.path.exists(p)), None)
if not src:
    raise SystemExit("No edges file found in exports/")

df = pd.read_csv(src, low_memory=False)

def ensure_lower(s):
    if s is None: 
        return pd.Series([""]*len(df))
    return s.astype(str).str.strip().str.lower()

# market_norm
if "market" in df.columns:
    df["market_norm"] = ensure_lower(df["market"])
else:
    df["market_norm"] = ensure_lower(df.get("bet_type", pd.Series([""]*len(df))))

# result_norm
res = df.get("result")
df["result_norm"] = ensure_lower(res).replace({"w":"win","l":"loss"}) if res is not None else np.nan

# settled_bool
settled_col = next((c for c in ["settled","is_settled","graded","is_graded","finalized"] if c in df.columns), None)
if settled_col:
    v = df[settled_col]
    if v.dtype == bool:
        df["settled_bool"] = v
    else:
        df["settled_bool"] = ensure_lower(v).isin(["1","true","t","yes","y","final","finalized"])
else:
    df["settled_bool"] = ensure_lower(df.get("result_norm", pd.Series([""]*len(df)))).isin(["win","loss","push","void"])

# sport
if "sport" not in df.columns:
    cand = df.get("league", None)
    df["sport"] = cand.astype(str) if cand is not None else "nfl"

# robust sort_ts
def parse_ts(df):
    for cols in [("sort_ts",),("event_ts",),("event_datetime",),("game_time",),("game_datetime",),
                 ("event_date","event_time"),("game_date","game_time"),("date","time")]:
        if len(cols)==1 and cols[0] in df.columns:
            ts = pd.to_datetime(df[cols[0]], errors="coerce", utc=True)
            if ts.notna().any(): return ts
        elif len(cols)==2 and all(c in df.columns for c in cols):
            ts = pd.to_datetime(df[cols[0]].astype(str)+" "+df[cols[1]].astype(str), errors="coerce", utc=True)
            if ts.notna().any(): return ts
    if "season" in df.columns and "week" in df.columns:
        y = pd.to_numeric(df["season"], errors="coerce")
        w = pd.to_numeric(df["week"], errors="coerce")
        def iso_monday(row):
            try:
                yy, ww = int(row.y), int(row.w)
                return pd.Timestamp.fromisocalendar(yy, ww, 1).tz_localize("UTC")
            except Exception:
                return pd.NaT
        ts = pd.DataFrame({"y":y,"w":w}).apply(iso_monday, axis=1)
        if ts.notna().any(): return ts
    return pd.to_datetime(range(len(df)), unit="s", origin="unix", utc=True)

df["sort_ts"] = parse_ts(df)

# efficient dtypes + index for fast sort
df = df.convert_dtypes(dtype_backend="pyarrow")
df = df.sort_values("sort_ts").reset_index(drop=True)
df["sort_idx"] = np.arange(len(df), dtype=np.int64)

# write fast formats
out_feather = "exports/edges_backtest.feather"
out_parquet = "exports/edges_backtest.parquet"
df.to_feather(out_feather)
df.to_parquet(out_parquet, index=False)
print(f"[ok] wrote {out_feather} and {out_parquet} rows={len(df)} cols={len(df.columns)}")

