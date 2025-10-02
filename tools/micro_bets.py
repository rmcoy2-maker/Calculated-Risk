# tools/micro_bets.py
import argparse, pandas as pd
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--locks-min-p", type=float, default=0.65)
ap.add_argument("--moonshot-min-odds", type=int, default=1500)
ap.add_argument("--moonshot-legs", type=int, default=4)
ap.add_argument("--max-per-section", type=int, default=5)
ap.add_argument("--out", type=Path, required=True)
ap.add_argument("--log", action="store_true")
ap.add_argument("--in", dest="infile")
ap.add_argument("--tag", default="micro")
ap.add_argument("--log-path", type=Path, default=Path("exports/bets_log.csv"))
args = ap.parse_args()

rows = [
    {"section":"locks","market":"ML","ref":"Sample A","side":"home","line":"", "odds":-120, "p_win":max(args.locks_min_p, .66), "ev":0.02, "stake":0.5},
    {"section":"moonshots","legs":args.moonshot_legs,"american":args.moonshot_min_odds+50,"p_combo":0.04,"ev_est":0.10,"stake":0.5,"legs_json":"[]"},
]
df = pd.DataFrame(rows)
args.out.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(args.out, index=False)

if args.log and args.infile:
    inp = pd.read_csv(args.infile)
    args.log_path.parent.mkdir(parents=True, exist_ok=True)
    try: old = pd.read_csv(args.log_path)
    except Exception: old = pd.DataFrame()
    pd.concat([old, inp], ignore_index=True).to_csv(args.log_path, index=False)

