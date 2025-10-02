import os, pandas as pd, numpy as np
pd.options.mode.copy_on_write = True
repo = r"C:\Projects\edge-finder"; exports = os.path.join(repo,"exports")
g = os.path.join(exports,"edges_graded_wlp.csv")
clean = os.path.join(exports,"edges_graded_wlp_clean.csv")
train = os.path.join(exports,"edges_graded_wlp_train.csv")
if not os.path.exists(g) or os.stat(g).st_size==0:
    print("[warn] graded file missing or empty"); raise SystemExit(0)
df = pd.read_csv(g, low_memory=False)

def s_or(df, col, default):
    return df[col] if col in df.columns else pd.Series(default, index=df.index)

res = s_or(df,"result", np.nan).astype(str).str.lower().str.strip().replace(
    {"lose":"loss","lost":"loss","w":"win","won":"win","l":"loss","pushes":"push"}
)
profit = pd.to_numeric(s_or(df,"profit", 0.0), errors="coerce").fillna(0.0)

ts = None
for c in ["sort_ts","kickoff_ts","kickoff","game_time","start_time","event_time","created_ts","ts","date"]:
    if c in df.columns:
        ts = pd.to_datetime(df[c], errors="coerce", utc=True).dt.tz_convert(None)
        if ts.notna().any(): break
if ts is None: ts = pd.Series(pd.NaT, index=df.index)
ts = ts.ffill().bfill().fillna(pd.Timestamp.utcnow())

dfc = df.copy()
dfc["result_norm"] = res
dfc["profit_norm"] = profit
dfc["sort_ts"]     = pd.to_datetime(ts).dt.strftime("%Y-%m-%dT%H:%M:%S")
dfc.to_csv(clean, index=False)

wl = dfc[dfc["result_norm"].isin(["win","loss"])].copy().sort_values("sort_ts")
wl["total_profit"] = wl["profit_norm"].cumsum().round(4)
wl.to_csv(train, index=False)
print(f"[ok] Cleaned -> {clean} (rows={len(dfc)})")
print(f"[ok] Trainable -> {train} (rows={len(wl)}, wins={(wl['result_norm']=='win').sum()}, losses={(wl['result_norm']=='loss').sum()})")

