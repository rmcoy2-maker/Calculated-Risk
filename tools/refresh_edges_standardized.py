# tools/refresh_edges_standardized.py
from __future__ import annotations
from pathlib import Path
import pandas as pd
from tools.pathing import exports_dir

def _first_existing(cands: list[Path]) -> Path | None:
    for p in cands:
        if p.exists() and p.stat().st_size > 0:
            return p
    return None

def main():
    exp = exports_dir()
    # Prefer the most enriched source you have in exports/
    candidates = [
        exp / "edges_graded_full_normalized_std.csv",
        exp / "edges_graded_full_normalized.csv",
        exp / "edges_graded_full.csv",
        exp / "edges_standardized.csv",  # fallback (no-op refresh)
    ]
    src = _first_existing(candidates)
    if not src:
        print("[edges] no source found in exports/")
        return

    df = pd.read_csv(src, low_memory=False)

    # Light standardization hooks (extend as needed)
    # Ensure _date_iso exists and is ET date
    if "_date_iso" not in df.columns or df["_date_iso"].isna().all():
        for c in ["_date_iso","date","game_date","_key_date","Date"]:
            if c in df.columns:
                s = pd.to_datetime(df[c], errors="coerce", utc=True)
                df["_date_iso"] = s.dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
                break

    out = exp / "edges_standardized.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[edges] refreshed {out} from {src}")

if __name__ == "__main__":
    main()

