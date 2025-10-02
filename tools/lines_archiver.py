# tools/lines_archiver.py
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tools.pathing import exports_dir

# ---------------- Aliases / Normalizers ----------------

_ALIAS = {
    "REDSKINS": "COMMANDERS", "WASHINGTON": "COMMANDERS", "FOOTBALL": "COMMANDERS",
    "OAKLAND": "RAIDERS", "LV": "RAIDERS", "LAS": "RAIDERS", "VEGAS": "RAIDERS",
    "SD": "CHARGERS", "STL": "RAMS",
}

def _nickify(s: pd.Series) -> pd.Series:
    s = s.astype("string").fillna("").str.upper()
    s = s.str.replace(r"[^A-Z0-9 ]+", "", regex=True).str.strip()
    s = s.replace(_ALIAS)
    return s.str.replace(r"\s+", "_", regex=True)

def _norm_market(m: str) -> str:
    m = (str(m) or "").strip().lower()
    if m in {"h2h", "ml", "moneyline", "money line"}:
        return "H2H"
    if m.startswith("spread") or m in {"spreads", "spread"}:
        return "SPREADS"
    if m.startswith("total") or m in {"totals", "total"}:
        return "TOTALS"
    return m.upper()

def _norm_ou(val: str) -> str:
    s = (str(val) or "").strip().upper().replace(" ", "")
    if s in {"OVER", "O", "O/U"}:
        return "OVER"
    if s in {"UNDER", "U"}:
        return "UNDER"
    return s

def _one_of(df: pd.DataFrame, names: list[str], default: str = "") -> pd.Series:
    for n in names:
        if n in df.columns:
            return df[n]
    return pd.Series([default] * len(df), index=df.index, dtype="string")

def _now_iso_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ---------------- Archive snapshot ----------------

def archive_lines(live_csv: Path | None = None) -> Path | None:
    """
    Copy exports/lines_live.csv to exports/lines_archive/<YYYY-MM-DD>/lines_<timestamp>.csv
    Adds 'asof_ts' if missing. Returns the written path or None if no live file.
    """
    exp = exports_dir()
    live = live_csv or (exp / "lines_live.csv")
    if not live.exists() or live.stat().st_size == 0:
        return None

    df = pd.read_csv(live, low_memory=False)
    if "asof_ts" not in df.columns:
        df["asof_ts"] = _now_iso_z()

    # choose a day partition (ET) from any reasonable date column
    date_cols = ["_date_iso", "event_date", "commence_time", "date", "game_date", "Date"]
    day = None
    for c in date_cols:
        if c in df.columns:
            dt = pd.to_datetime(df[c], errors="coerce", utc=True)
            if dt.notna().any():
                day = dt.dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d").mode().iloc[0]
                break
    if not day:
        day = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d")

    outdir = exp / "lines_archive" / day
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = outdir / f"lines_{stamp}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return out

# ---------------- Build opening/closing tables ----------------

def build_open_close(for_date: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build opening/closing price tables for a given date (YYYY-MM-DD) or the latest
    archived date. Robust to different vendor schemas:

      side from: side / selection / bet_side / runner / name / team / participant
      book from: book / sportsbook / source / operator
      home/away: _home_nick / home / home_team / HomeTeam / home_name
      market   : _market_norm / market / bet_type

    Writes:
      exports/lines_open_<DATE>.csv
      exports/lines_close_<DATE>.csv

    Returns (opening_df, closing_df).
    """
    exp = exports_dir()
    root = exp / "lines_archive"
    if not root.exists():
        return pd.DataFrame(), pd.DataFrame()

    # Pick day folder to process
    if for_date:
        day_dir = root / for_date
        if not day_dir.exists():
            return pd.DataFrame(), pd.DataFrame()
    else:
        subdirs = sorted([d for d in root.iterdir() if d.is_dir()])
        if not subdirs:
            return pd.DataFrame(), pd.DataFrame()
        day_dir = subdirs[-1]

    # Concatenate all snapshots for that day
    frames = []
    for f in sorted(day_dir.glob("*.csv")):
        d = pd.read_csv(f, low_memory=False)
        if "asof_ts" not in d.columns:
            ts = time.gmtime(f.stat().st_mtime)
            d["asof_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", ts)
        frames.append(d)
    if not frames:
        return pd.DataFrame(), pd.DataFrame()
    all_df = pd.concat(frames, ignore_index=True)

    # -------- Normalize key columns --------
    # teams
    all_df["_home_nick"] = _nickify(_one_of(all_df, ["_home_nick", "home", "home_team", "HomeTeam", "home_name"]))
    all_df["_away_nick"] = _nickify(_one_of(all_df, ["_away_nick", "away", "away_team", "AwayTeam", "away_name"]))
    # market
    all_df["_market_norm"] = _one_of(all_df, ["_market_norm", "market", "bet_type"]).astype("string").map(_norm_market)
    # book
    all_df["book"] = _one_of(all_df, ["book", "sportsbook", "source", "operator"], default="UNKNOWN").astype("string")
    # side (robust)
    side_raw = _one_of(all_df, ["side", "selection", "bet_side", "runner", "name", "team", "participant"]).astype("string")
    side_norm = side_raw.map(_norm_ou).replace({
        "H": "HOME", "HOST": "HOME",
        "A": "AWAY", "VISITOR": "AWAY", "VISITORS": "AWAY", "ROAD": "AWAY",
    })

    def _resolve_team_side(row):
        s = row["__side_norm"]
        if s in {"HOME", "AWAY", "OVER", "UNDER"}:
            return s
        if s == row["_home_nick"]:
            return "HOME"
        if s == row["_away_nick"]:
            return "AWAY"
        return s

    all_df["__side_norm"] = side_norm
    all_df["__side_norm"] = all_df.apply(_resolve_team_side, axis=1)
    all_df["side"] = all_df["__side_norm"].fillna("")

    # ensure strings
    for c in ["side", "book", "_home_nick", "_away_nick", "_market_norm"]:
        all_df[c] = all_df[c].astype("string")

    # drop rows missing essential keys
    essential_ok = (
        (all_df["_home_nick"] != "") &
        (all_df["_away_nick"] != "") &
        (all_df["_market_norm"] != "") &
        (all_df["side"] != "") &
        (all_df["book"] != "")
    )
    safe = all_df[essential_ok].copy()
    if len(safe) == 0:
        # write empty outputs so downstream code doesn't break
        (exp / f"lines_open_{day_dir.name}.csv").write_text("", encoding="utf-8")
        (exp / f"lines_close_{day_dir.name}.csv").write_text("", encoding="utf-8")
        return pd.DataFrame(), pd.DataFrame()

    # -------- Select opening/closing by earliest/latest asof_ts per key --------
    asof_safe = pd.to_datetime(safe["asof_ts"], errors="coerce", utc=True)
    key_cols = ["_home_nick", "_away_nick", "_market_norm", "side", "book"]

    open_idx  = asof_safe.groupby([safe[c] for c in key_cols]).idxmin()
    close_idx = asof_safe.groupby([safe[c] for c in key_cols]).idxmax()

    opening = safe.loc[open_idx].copy()
    closing = safe.loc[close_idx].copy()

    # write outputs
    opening.to_csv(exp / f"lines_open_{day_dir.name}.csv",  index=False, encoding="utf-8-sig")
    closing.to_csv(exp / f"lines_close_{day_dir.name}.csv", index=False, encoding="utf-8-sig")

    # clean temp column
    for c in ["__side_norm"]:
        if c in opening.columns:
            opening.drop(columns=[c], inplace=True, errors="ignore")
        if c in closing.columns:
            closing.drop(columns=[c], inplace=True, errors="ignore")

    return opening, closing

# ---------------- CLI ----------------

if __name__ == "__main__":
    # Simple manual testing:
    # 1) archive current live lines
    wrote = archive_lines()
    print(f"[archive] wrote: {wrote}")

    # 2) build open/close for latest day
    open_df, close_df = build_open_close()
    print(f"[open]  {open_df.shape}")
    print(f"[close] {close_df.shape}")

