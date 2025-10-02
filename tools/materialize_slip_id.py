import pandas as pd, numpy as np

df = pd.read_csv(r"exports/edges.csv")
df.columns = [c.lower().strip() for c in df.columns]

ts = pd.to_datetime(df.get("ts", df.get("sort_ts")), errors="coerce")
df["_ts"] = ts.dt.floor("s")

season = pd.to_numeric(df.get("season"), errors="coerce")
week   = pd.to_numeric(df.get("week"), errors="coerce")

chunk = 6  # match MAX_LEGS_PER_SLIP in Backtest
key = pd.DataFrame({
    "ref": df.get("ref","").astype(str),
    "season": season.fillna(ts.dt.year).astype("Int64"),
    "week": week.fillna(ts.dt.isocalendar().week).astype("Int64"),
    "tss": df["_ts"],
})
df["_chunkidx"] = key.groupby(["ref","season","week","tss"]).cumcount() // chunk

# Build a deterministic slip_id
slip_str = (
    key["ref"].astype(str) + "|" +
    key["season"].astype(str) + "|" +
    key["week"].astype(str) + "|" +
    key["tss"].astype("int64").astype(str) + "|" +
    df["_chunkidx"].astype(str)
)
df["slip_id"] = pd.util.hash_pandas_object(slip_str, index=False).astype("int64").abs().astype(str).str[-12:]

df.drop(columns=["_ts","_chunkidx"], inplace=True, errors="ignore")
df.to_csv(r"exports/edges.csv", index=False)
print("Wrote exports/edges.csv with slip_id.")

