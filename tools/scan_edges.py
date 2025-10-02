# tools/scan_edges.py
# Minimal “scanner” that turns your local odds snapshot into edges.csv.
# Replace/expand the builder logic as your pipeline matures.

from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parents[1]
db = root / "db" / "odds_books.csv"                # input snapshot (already in your repo per screenshot)
out = root / "exports" / "edges.csv"               # output consumed by Edge Scanner

out.parent.mkdir(parents=True, exist_ok=True)

if not db.exists():
    raise SystemExit(f"[err] snapshot not found: {db}")

df = pd.read_csv(db)

# --- Make sure the core columns exist ---
# Expect at least: game_id, market, side, book, odds
for req in ["game_id", "market", "side", "book", "odds"]:
    if req not in df.columns:
        df[req] = pd.NA

# Derive an implied win prob if p_win is missing (American odds → prob)
if "p_win" not in df.columns:
    def american_to_prob(x):
        try:
            o = float(x)
        except Exception:
            return pd.NA
        if o >= 100:
            return 100.0 / (o + 100.0)
        else:
            return abs(o) / (abs(o) + 100.0)
    df["p_win"] = pd.to_numeric(df["odds"], errors="coerce").map(american_to_prob)

# (Optional) keep only reasonable columns for the UI
keep = [c for c in ["game_id","market","side","book","odds","p_win","line","source","ts"] if c in df.columns]
if keep:
    df = df[keep]

df.to_csv(out, index=False)
print(f"[ok] wrote {out} rows={len(df)}")

