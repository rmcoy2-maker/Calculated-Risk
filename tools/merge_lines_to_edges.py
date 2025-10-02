# tools/merge_lines_to_edges.py
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import numpy as np

# -------- repo + paths --------
def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for up in [here] + list(here.parents):
        if (up / "exports").exists():
            return up
    return Path.cwd()

REPO     = find_repo_root()
EXPORTS  = REPO / "exports"
LINESCSV = EXPORTS / "lines_live.csv"
OUTCSV   = EXPORTS / "edges.csv"

EXPORTS.mkdir(parents=True, exist_ok=True)

# -------- helpers --------
def implied_prob_from_american(o) -> float:
    try:
        o = float(o)
    except Exception:
        return np.nan
    if o > 0:   # +120
        return 100.0 / (o + 100.0)
    if o < 0:   # -120
        return abs(o) / (abs(o) + 100.0)
    return np.nan

def norm_market(m: str) -> str:
    if not isinstance(m, str): return ""
    m = m.strip().lower()
    if m in ("h2h","ml","moneyline","money line"): return "H2H"
    if m in ("spread","spreads","point spread"):    return "SPREADS"
    if m in ("total","totals","over/under","ou"):   return "TOTALS"
    return m.upper()


def ensure_game_id(row) -> str:
    gid = str(row.get("game_id", "") or "").strip()
    if gid:
        return gid
    # fallback: "Away@Home_ISO"
    away = str(row.get("away", "") or row.get("away_team", "")).strip()
    home = str(row.get("home", "") or row.get("home_team", "")).strip()
    ct   = row.get("commence_time")
    try:
        ts = pd.to_datetime(ct, utc=True).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        ts = ""
    if away and home and ts:
        return f"{away}@{home}_{ts}"
    return f"{away}@{home}_{ts}" if (away or home or ts) else ""

# -------- load --------
if not LINESCSV.exists() or LINESCSV.stat().st_size == 0:
    raise SystemExit(f"ERROR: {LINESCSV} not found or empty. Run your odds pull first.")

raw = pd.read_csv(LINESCSV, low_memory=False)
raw.columns = [c.strip().lower() for c in raw.columns]

# required columns (as produced by your Line Shop pull)
need = {"pulled_ts","game_id","commence_time","home","away","book","market","selection","price_american","point"}
missing = [c for c in need if c not in raw.columns]
if missing:
    raise SystemExit(f"ERROR: {LINESCSV} is missing columns: {missing}")

# -------- normalize --------
df = raw.copy()

# game_id (or derive one)
df["game_id"] = df.apply(ensure_game_id, axis=1)

# market + side
df["market"] = df["market"].apply(norm_market).replace({"h2h":"moneyline"})  # extra safety
df["side"]   = df["selection"].astype(str)

# odds + p_win
df["odds"]  = pd.to_numeric(df["price_american"], errors="coerce")
df["p_win"] = df["odds"].map(implied_prob_from_american)

# line (spread/total point), keep numeric where possible
df["line"] = pd.to_numeric(df["point"], errors="coerce")

# timestamp/source
try:
    ts = pd.to_datetime(df["pulled_ts"], utc=True)
except Exception:
    ts = pd.Timestamp.now(tz=timezone.utc)
df["ts"]     = ts
df["source"] = "lines_live"

# keep only usable rows
keep_cols = ["game_id","market","side","book","odds","p_win","line","source","ts"]
out = df[keep_cols].dropna(subset=["game_id","market","side","book","odds"]).copy()

# optional: drop exact duplicates from same pull
out = out.drop_duplicates(subset=["game_id","market","side","book","odds","line"])

# write
out.to_csv(OUTCSV, index=False)
print(f"[ok] wrote {OUTCSV} rows={len(out):,}")

