# tools/lines_shop_io.py
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd

# paths
EXPORTS = Path("exports")
EXPORTS.mkdir(exist_ok=True)
LATEST = EXPORTS / "lines_shop_latest.parquet"  # preferred
SNAP_DIR = EXPORTS / "lines_snapshots"
SNAP_DIR.mkdir(exist_ok=True)

# flexible upstream → canonical schema
_COLMAP = {
    "timestamp": "ts", "ts": "ts", "time": "ts",
    "sportsbook": "book", "book": "book",
    "league": "league",
    "event_id": "game_id", "game_id": "game_id", "event": "game_id",
    "market": "market",
    "team": "ref", "participant": "ref", "selection": "ref", "ref": "ref",
    "side": "side", "pick": "side", "bet_side": "side",
    "price": "odds", "american_odds": "odds", "odds": "odds",
    "line": "line", "points": "line", "total": "line", "spread": "line",
}

def _coalesce(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["ts","book","league","game_id","market","ref","side","odds","line","market_key"])

    df = df.rename(columns={c: _COLMAP.get(c, c) for c in df.columns}).copy()

    # required columns
    for c in ["ts","book","league","game_id","market","ref","side","odds"]:
        if c not in df.columns:
            df[c] = np.nan if c in ("odds",) else ""

    # types
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)
    if not df["ts"].notna().any():
        df["ts"] = pd.Timestamp.now(tz=timezone.utc)

    df["odds"] = pd.to_numeric(df["odds"], errors="coerce")
    if "line" in df.columns:
        df["line"] = pd.to_numeric(df["line"], errors="coerce")

    # normalize market
    m = df["market"].astype(str).strip().str.lower()
    m = m.replace({
        "h2h": "H2H", "ml": "H2H", "moneyline": "H2H",
        "spread": "SPREADS", "spreads": "SPREADS", "point spread": "SPREADS",
        "total": "TOTALS", "totals": "TOTALS", "over/under": "TOTALS", "ou": "TOTALS",
    })
    df["market"] = np.where(m.isin(["H2H","SPREADS","TOTALS"]), m, m.str.upper())

    # stable key
    df["market_key"] = (
        df["market"].astype(str) + "|" +
        df["game_id"].astype(str) + "|" +
        df["ref"].astype(str) + "|" +
        df["side"].astype(str)
    )
    return df

def read_latest_shop() -> pd.DataFrame:
    """Read the current Line Shop file, preferring parquet; fallback to CSV if present."""
    try:
        if LATEST.exists():
            return _coalesce(pd.read_parquet(LATEST))
    except Exception:
        pass
    csv = LATEST.with_suffix(".csv")
    if csv.exists():
        try:
            return _coalesce(pd.read_csv(csv, low_memory=False, encoding="utf-8-sig"))
        except Exception:
            try:
                return _coalesce(pd.read_csv(csv, engine="python", low_memory=False))
            except Exception:
                return _coalesce(pd.DataFrame())
    return _coalesce(pd.DataFrame())

def write_latest_shop(df: pd.DataFrame) -> Path:
    """Normalize and write LATEST parquet."""
    out = _coalesce(df.copy())
    out.to_parquet(LATEST, index=False)
    return LATEST

def snapshot_shop(df: pd.DataFrame) -> Path:
    """Write a timestamped snapshot parquet under exports/lines_snapshots/."""
    out = _coalesce(df.copy())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = SNAP_DIR / f"lines_shop_{stamp}.parquet"
    out.to_parquet(path, index=False)
    return path

