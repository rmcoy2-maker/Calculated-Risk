# tools/repair_snapshots.py
from __future__ import annotations
import os, csv, shutil
from pathlib import Path
import pandas as pd

EXPECTED = [
    "_snapshot_ts_utc","_snapshot_ts_est","_snapshot_date","_source",
    "_event_ts_utc","_event_ts_est","_date_iso",
    "_home_nick","_away_nick","book","_market_norm","side","line","price","decimal",
    "player_name","prop_type","_key","event_id","game_id"
]

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
    src = exp / "lines_snapshots.csv"
    if not src.exists():
        print("No snapshots to repair.")
        return

    bak = exp / "lines_snapshots.bak.csv"
    shutil.copy2(src, bak)

    rows = []
    with open(src, "r", newline="", encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            rows.append({k: r.get(k, None) for k in EXPECTED})

    df = pd.DataFrame(rows, columns=EXPECTED)
    tmp = exp / "lines_snapshots_clean.csv"
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(src)
    print(f"Rewrote snapshots with stable schema. Backup at: {bak}")

if __name__ == "__main__":
    main()

