# tools/repair_snapshots_rebuild_keys.py
from __future__ import annotations
import csv, shutil
from pathlib import Path
import pandas as pd

TZ = "America/New_York"

EXPECTED = [
    "_snapshot_ts_utc","_snapshot_ts_est","_snapshot_date","_source",
    "_event_ts_utc","_event_ts_est","_date_iso",
    "_home_nick","_away_nick","book","_market_norm","side","line","price","decimal",
    "player_name","prop_type","_key","event_id","game_id"
]

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

def _nickify(s: pd.Series) -> pd.Series:
    s = s.astype("string").fillna("").str.upper().str.replace(r"[^A-Z0-9 ]+", "", regex=True).str.strip()
    s = s.replace(_ALIAS)
    return s.str.replace(r"\s+", "_", regex=True)

def _norm_market(s: pd.Series) -> pd.Series:
    x = s.astype("string").str.lower().str.strip()
    x = x.replace({"ml":"h2h","moneyline":"h2h","money line":"h2h","spreads":"spread","totals":"total"})
    out = []
    for v in x:
        if v in {"h2h"}: out.append("H2H")
        elif v.startswith("spread"): out.append("SPREADS")
        elif v.startswith("total"): out.append("TOTALS")
        else: out.append((v or "").upper())
    return pd.Series(out, index=x.index, dtype="string")

def read_flex(path: Path) -> pd.DataFrame:
    rows = []
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            rows.append(r)
    return pd.DataFrame(rows)

def main():
    exp = exports_dir()
    src = exp / "lines_snapshots.csv"
    if not src.exists():
        print("No snapshots to repair.")
        return

    bak = exp / "lines_snapshots.bak.rebuild.csv"
    shutil.copy2(src, bak)

    df = read_flex(src)
    if df.empty:
        print("Snapshots file is empty.")
        return

    for c in EXPECTED:
        if c not in df.columns: df[c] = pd.NA

    if df["_home_nick"].isna().any():
        df["_home_nick"] = df["_home_nick"].fillna(df.get("home_team"))
    if df["_away_nick"].isna().any():
        df["_away_nick"] = df["_away_nick"].fillna(df.get("away_team"))
    if df["_market_norm"].isna().any():
        df["_market_norm"] = df["_market_norm"].fillna(df.get("market"))
    if df["player_name"].isna().any() and "player" in df.columns:
        df["player_name"] = df["player_name"].fillna(df["player"])
    if df["prop_type"].isna().any() and "market_detail" in df.columns:
        df["prop_type"] = df["prop_type"].fillna(df["market_detail"])
    if df["book"].isna().any():
        df["book"] = df["book"].fillna("UNKNOWN")
    if df["side"].isna().any():
        df["side"] = df["side"].fillna("")

    df["_home_nick"]   = _nickify(df["_home_nick"])
    df["_away_nick"]   = _nickify(df["_away_nick"])
    df["_market_norm"] = _norm_market(df["_market_norm"])

    evt = pd.to_datetime(df["_event_ts_est"], errors="coerce", utc=True)
    if evt.isna().all():
        evt = pd.to_datetime(df["_event_ts_utc"], errors="coerce", utc=True)
    snap = pd.to_datetime(df["_snapshot_ts_est"], errors="coerce", utc=True)

    need_date = df["_date_iso"].isna() | (df["_date_iso"].astype("string") == "")
    if need_date.any():
        date_evt = evt.dt.tz_convert(TZ).dt.strftime("%Y-%m-%d")
        date_snap = snap.dt.tz_convert(TZ).dt.strftime("%Y-%m-%d")
        df.loc[need_date, "_date_iso"] = date_evt[need_date].fillna(date_snap[need_date])

    for c in ("line","price","decimal"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    key_missing = df["_key"].isna() | (df["_key"].astype("string") == "")
    if key_missing.any():
        player_key = _nickify(df["player_name"].astype("string").fillna(""))
        rebuilt = (
            df["_date_iso"].astype("string") + "|" +
            df["_home_nick"].astype("string") + "|" +
            df["_away_nick"].astype("string") + "|" +
            df["_market_norm"].astype("string") + "|" +
            df["side"].astype("string") + "|" +
            df["book"].astype("string") + "|" +
            player_key.astype("string") + "|" +
            df["prop_type"].astype("string")
        )
        df.loc[key_missing, "_key"] = rebuilt[key_missing]

    tmp = exp / "lines_snapshots_clean.csv"
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(src)
    print(f"Rebuilt keys & normalized snapshots. Backup at: {bak}")

if __name__ == "__main__":
    main()

