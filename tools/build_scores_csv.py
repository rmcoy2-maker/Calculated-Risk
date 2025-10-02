# tools/build_scores_csv.py
from pathlib import Path
import pandas as pd

SRC = Path("data/scores")      # put your per-season files here
OUT = Path("exports/scores.csv")
SRC.mkdir(parents=True, exist_ok=True)
OUT.parent.mkdir(parents=True, exist_ok=True)

parts = []
for p in sorted(SRC.glob("*.csv")):
    try:
        df = pd.read_csv(p)
        # Normalize minimal cols used by Backtest:
        for c in ("season","week"):
            if c not in df.columns: df[c] = None
        parts.append(df)
    except Exception as e:
        print(f"[warn] {p}: {e}")

out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
out.to_csv(OUT, index=False, encoding="utf-8-sig")
print(f"Wrote {OUT} ({OUT.stat().st_size if OUT.exists() else 0} bytes) with {len(out)} rows")

