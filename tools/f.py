# tools/compute_open_close.py
from __future__ import annotations
import os
from pathlib import Path
import pandas as pd
import numpy as np

def exports_dir() -> Path:
    env = os.environ.get("EDGE_EXPORTS_DIR", "").strip()
    if env:
        p = Path(env); p.mkdir(parents=True, exist_ok=True); return p
    here = Path(__file__).resolve()
    for up in [here.parent] + list(here.parents):
        if up.name.lower() == "edge-finder":
            p = up / "exports"; p.mkdir(parents=True, exist_ok=True); return p
    p = Path.cwd() / "exports"; p.mkdir(parents=True, exist_ok=True); return p

def main():
    exp = exports_dir()
    path = exp / "lines_snapshots.csv"
    if not path.exists():
        print("[openclose] no snapshots file found.")
        return

    df = pd.read_csv(path, low_memory=False, encoding="utf-8-sig")
    if df.empty:
        print("[openclose] snapshots empty.")
        return

    # Ensure columns exist
    need_cols = [
        "_key","_date_iso","_home_nick","_away_nick","book","_market_norm","side",
        "player_name","prop_type","line","price",
        "_snapshot_ts_est","_event_ts_est"
    ]
    for c in need_cols:
        if c not in df.columns:
            df[c] = pd.NA

    # Parse timestamps to **UTC** so comparisons never mix tz-naive/aware
    df["_snap_dt"]  = pd.to_datetime(df["_snapshot_ts_est"], errors="coerce", utc=True)
    df["_event_dt"] = pd.to_datetime(df["_event_ts_est"],  errors="coerce", utc=True)  # may be NaT

    # OPEN = earliest snapshot per key
    opens_idx = df.sort_values("_snap_dt").groupby("_key", as_index=False).head(1).index
    opens = df.loc[opens_idx, [
        "_key","_date_iso","_home_nick","_away_nick","book","_market_norm","side",
        "player_name","prop_type","line","price","_snap_dt"
    ]].copy()
    opens = opens.rename(columns={
        "line":"open_line","price":"open_price","_snap_dt":"open_ts_utc"
    })

    # CLOSE:
    # 1) last snapshot **before** kickoff if event time exists for that row
    pre = df[df["_event_dt"].notna() & (df["_snap_dt"] <= df["_event_dt"])]
    last_pre = (
        pre.sort_values("_snap_dt")
           .groupby("_key", as_index=False)
           .tail(1)
           .set_index("_key")
    )

    # 2) fallback = last snapshot overall for that key (handles missing kickoff)
    last_any = (
        df.sort_values("_snap_dt")
          .groupby("_key", as_index=False)
          .tail(1)
          .set_index("_key")
    )

    # Start from fallback, then override with pre-kick where available
    closes = last_any[["line","price","_snap_dt"]].rename(columns={
        "line":"close_line","price":"close_price","_snap_dt":"close_ts_utc"
    })
    if not last_pre.empty:
        closes.update(last_pre[["line","price","_snap_dt"]].rename(columns={
            "line":"close_line","price":"close_price","_snap_dt":"close_ts_utc"
        }))

    closes = closes.reset_index()

    # Merge opens + closes
    out = opens.merge(closes, on="_key", how="outer")

    # Deltas
    out["Δline_vs_open"]  = pd.to_numeric(out["close_line"], errors="coerce")  - pd.to_numeric(out["open_line"], errors="coerce")
    out["Δprice_vs_open"] = pd.to_numeric(out["close_price"], errors="coerce") - pd.to_numeric(out["open_price"], errors="coerce")

    # Order columns
    cols = [
        "_date_iso","_home_nick","_away_nick","book","_market_norm","side",
        "player_name","prop_type",
        "open_line","open_price","open_ts_utc",
        "close_line","close_price","close_ts_utc",
        "Δline_vs_open","Δprice_vs_open","_key"
    ]
    # Fill in descriptive columns from opens where missing after outer merge
    for c in ["_date_iso","_home_nick","_away_nick","book","_market_norm","side","player_name","prop_type"]:
        if c not in out.columns: out[c] = pd.NA
    # Reindex safely
    cols = [c for c in cols if c in out.columns]
    out = out.reindex(columns=cols)

    out_path = exp / "lines_open_close.csv"
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[openclose] wrote {len(out):,} rows -> {out_path}")

if __name__ == "__main__":
    main()

