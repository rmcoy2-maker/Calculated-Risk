# tools/capture_lines.py — minimal & robust for your live CSV schema
# live header: pulled_ts,game_id,commence_time,home,away,book,market,selection,price_american,point
from __future__ import annotations
import os, sys
from pathlib import Path
import pandas as pd
import numpy as np

TZ = "America/New_York"

_ALIAS = {
    "REDSKINS":"COMMANDERS","WASHINGTON":"COMMANDERS","FOOTBALL":"COMMANDERS",
    "OAKLAND":"RAIDERS","LV":"RAIDERS","LAS":"RAIDERS","VEGAS":"RAIDERS",
    "SD":"CHARGERS","STL":"RAMS",
}

def exports_dir() -> Path:
    env = os.environ.get("EDGE_EXPORTS_DIR", "").strip()
    if env:
        p = Path(env); p.mkdir(parents=True, exist_ok=True); return p
    here = Path(__file__).resolve()
    for up in [here.parent] + list(here.parents):
        if up.name.lower() == "edge-finder":
            p = up / "exports"; p.mkdir(parents=True, exist_ok=True); return p
    p = Path.cwd() / "exports"; p.mkdir(parents=True, exist_ok=True); return p

def nickify(s: pd.Series) -> pd.Series:
    s = s.astype("string").fillna("").str.upper().str.replace(r"[^A-Z0-9 ]+", "", regex=True).str.strip()
    s = s.replace(_ALIAS)
    return s.str.replace(r"\s+", "_", regex=True)

def norm_market(x: pd.Series) -> pd.Series:
    s = x.astype("string").str.lower().str.strip()
    s = s.replace({"ml":"h2h","moneyline":"h2h","money line":"h2h","spreads":"spread","totals":"total"})
    out = []
    for v in s:
        if v in {"h2h"}: out.append("H2H")
        elif v.startswith("spread"): out.append("SPREADS")
        elif v.startswith("total"): out.append("TOTALS")
        else: out.append((v or "").upper())
    return pd.Series(out, index=s.index, dtype="string")

def american_to_decimal(american: pd.Series) -> pd.Series:
    a = pd.to_numeric(american, errors="coerce")
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(a > 0, 1 + a/100.0,
                        np.where(a < 0, 1 + 100.0/np.abs(a), np.nan))

def main():
    exp = exports_dir()
    live_path = exp / "lines_live.csv"
    if not live_path.exists():
        print(f"[capture] {live_path} not found; nothing to snapshot."); sys.exit(0)

    df = pd.read_csv(live_path, low_memory=False, encoding="utf-8-sig")
    if df.empty:
        print("[capture] lines_live.csv is empty; nothing to snapshot."); sys.exit(0)

    # Expect columns; create safe defaults if any is missing
    for col in ["home","away","book","market","selection","price_american","point","commence_time","game_id"]:
        if col not in df.columns:
            df[col] = pd.NA

    # Normalize fields
    df["_home_nick"]   = nickify(df["home"])
    df["_away_nick"]   = nickify(df["away"])
    df["_market_norm"] = norm_market(df["market"])
    df["side"]         = df["selection"].astype("string")
    df["line"]         = pd.to_numeric(df["point"], errors="coerce")

    # Robust clean for price_american before casting
    df["price"] = pd.to_numeric(
        df["price_american"].astype("string").str.replace(r"[^\-\+\d]", "", regex=True),
        errors="coerce"
    )
    df["decimal"]      = american_to_decimal(df["price"])
    df["book"]         = df["book"].astype("string")
    df["event_id"]     = pd.NA
    df["game_id"]      = df["game_id"].astype("string")

    # Event time / date
    event_dt_utc = pd.to_datetime(df["commence_time"], errors="coerce", utc=True)
    df["_event_ts_utc"] = event_dt_utc.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    df["_event_ts_est"] = event_dt_utc.dt.tz_convert(TZ).dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    df["_date_iso"]     = event_dt_utc.dt.tz_convert(TZ).dt.strftime("%Y-%m-%d")

    # Snapshot timestamps
    snap_utc = pd.Timestamp.now(tz="UTC")
    snap_est = snap_utc.tz_convert(TZ)
    df["_snapshot_ts_utc"] = snap_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    df["_snapshot_ts_est"] = snap_est.strftime("%Y-%m-%dT%H:%M:%S%z")
    df["_snapshot_date"]   = snap_est.strftime("%Y-%m-%d")
    df["_source"]          = "line_shop"

    # Build durable key (no props in this schema)
    df["player_name"] = pd.NA
    df["prop_type"]   = pd.NA
    df["_key"] = (
        df["_date_iso"].astype("string") + "|" +
        df["_home_nick"].astype("string") + "|" +
        df["_away_nick"].astype("string") + "|" +
        df["_market_norm"].astype("string") + "|" +
        df["side"].astype("string") + "|" +
        df["book"].astype("string") + "||"
    )

    # Thin snapshot schema
    keep = [
        "_snapshot_ts_utc","_snapshot_ts_est","_snapshot_date","_source",
        "_event_ts_utc","_event_ts_est","_date_iso",
        "_home_nick","_away_nick","book","_market_norm","side","line","price","decimal",
        "player_name","prop_type","_key","event_id","game_id"
    ]
    snap = df.reindex(columns=keep)

    # Append
    snaps_path = exp / "lines_snapshots.csv"
    header = not snaps_path.exists()
    snap.to_csv(snaps_path, mode="a", header=header, index=False, encoding="utf-8-sig")
    print(f"[capture] appended {len(snap):,} rows -> {snaps_path}")

if __name__ == "__main__":
    main()

