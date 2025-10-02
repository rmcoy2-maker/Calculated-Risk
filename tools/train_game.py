#!/usr/bin/env python
import argparse, json
from pathlib import Path
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--historical-odds", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.historical_odds)
    meta = {
        "rows": int(len(df)),
        "cols": list(df.columns),
        "note": "stub trainer — replace with real model training"
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    (out_dir / "version.txt").write_text("game_trainer_stub_v1\n")
    print(f"[ok] wrote stub artifacts to {out_dir} rows={len(df)}")

if __name__ == "__main__":
    main()

