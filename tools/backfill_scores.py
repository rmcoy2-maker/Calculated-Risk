from __future__ import annotations
import sys, csv
from pathlib import Path
import numpy as np
import pandas as pd

# ---------- config ----------
EXPORTS   = Path("exports")
SRC_PATH  = Path(sys.argv[1]) if len(sys.argv) > 1 else (EXPORTS / "scores_1966-2025.csv")
DEST_PATH = EXPORTS / "scores_standardized.csv"

# ---------- robust CSV reader ----------
def _smart_read_csv(path: Path) -> pd.DataFrame:
    encodings = ["utf-8-sig", "utf-8", "cp1252", "latin1", "utf-16"]
    last_err = None
    for enc in encodings:
        try:
            # 1) Try Python engine with auto sep; omit low_memory
            try:
                df = pd.read_csv(path, sep=None, engine="python", encoding=enc, on_bad_lines="skip")
                if len(df) > 0 and df.shape[1] > 1:
                    print(f"[backfill] Parsed '{path.name}' with enc={enc}, sep=auto (python), rows={len(df):,}, cols={df.shape[1]}")
                    return df
            except Exception as e:
                last_err = e

            # 2) Fallback to common separators with C engine
            for sep in [",", "\t", ";", "|"]:
                try:
                    df = pd.read_csv(path, sep=sep, engine="c", encoding=enc, low_memory=False)
                    if len(df) > 0 and df.shape[1] > 1:
                        print(f"[backfill] Parsed '{path.name}' with enc={enc}, sep='{sep}' (c), rows={len(df):,}, cols={df.shape[1]}")
                        return df
                except Exception as e2:
                    last_err = e2
                    continue
        except Exception as e3:
            last_err = e3
            continue
    raise RuntimeError(f"Failed to parse {path} — last error: {last_err}")

# ---------- helpers ----------
_ALIAS = {
    "REDSKINS":"COMMANDERS","WASHINGTON":"COMMANDERS","FOOTBALL":"COMMANDERS",
    "OAKLAND":"RAIDERS","LV":"RAIDERS","LAS":"RAIDERS","VEGAS":"RAIDERS",
    "SD":"CHARGERS","SAN":"CHARGERS","DIEGO":"CHARGERS","LA":"CHARGERS","LOS":"CHARGERS","ANGELES":"CHARGERS",
    "ST":"RAMS","LOUIS":"RAMS","NINERS":"49ERS","NO":"SAINTS","NOLA":"SAINTS","JAX":"JAGUARS",
}
def _clean_token(s):
    if s is None or (isinstance(s, float) and pd.isna(s)): return ""
    s = str(s).upper().replace(".", " ").replace("-", " ").strip()
    return " ".join(s.split())
def _nick_last(s):
    tok = _clean_token(s).split()[-1] if _clean_token(s) else ""
    return _ALIAS.get(tok, tok)

def _col(df, names, default=""):
    for n in names:
        if n in df.columns:
            return df[n]
    return pd.Series([default]*len(df), index=df.index)

def _as_dateiso(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce", utc=False)
    try:
        dt = dt.dt.tz_convert(None)
    except Exception:
        try:
            dt = dt.dt.tz_localize(None)
        except Exception:
            pass
    return dt.dt.strftime("%Y-%m-%d")

def _gid_norm(x: str) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)): return ""
    x = str(x).upper().strip()
    x = x.replace("_AT_", "@").replace(" AT ", "@").replace(" AT_", "@").replace("_AT ", "@")
    x = " ".join(x.split()).replace(" ", "_")
    return x

# ---------- run ----------
if not SRC_PATH.exists():
    raise SystemExit(f"[backfill] Source not found: {SRC_PATH}")

EXPORTS.mkdir(parents=True, exist_ok=True)

print(f"[backfill] Loading {SRC_PATH} …")
raw = _smart_read_csv(SRC_PATH)

# peek columns
print(f"[backfill] Columns detected: {list(raw.columns)[:20]} ...")

date = _col(raw, ["_date_iso","Date","date","game_date","CommenceTime","commence_time"])
home_team = _col(raw, ["_home_nick","home_team","HomeTeam","home","_home_team","home_name"])
away_team = _col(raw, ["_away_nick","away_team","AwayTeam","away","_away_team","away_name"])


home_score = pd.to_numeric(_col(raw, ["home_score","HomeScore","home_points","home_pts","score_home"]), errors="coerce")
away_score = pd.to_numeric(_col(raw, ["away_score","AwayScore","away_points","away_pts","score_away"]), errors="coerce")


# ---------- build standardized output ----------

# pull season/week (numeric if possible)
season = pd.to_numeric(_col(raw, ["season","Season"]), errors="coerce")
week   = pd.to_numeric(_col(raw, ["week","Week"]), errors="coerce")

out = pd.DataFrame({
    "_date_iso": _as_dateiso(_col(raw, ["_date_iso","_DateISO","Date","date","game_date","CommenceTime","commence_time"])),

    "_home_nick": _col(raw, ["_home_nick","home_team","HomeTeam","home","_home_team","home_name"]).astype(str).map(_nick_last),
    "_away_nick": _col(raw, ["_away_nick","away_team","AwayTeam","away","_away_team","away_name"]).astype(str).map(_nick_last),
    "HomeScore": pd.to_numeric(_col(raw, ["home_score","HomeScore","home_points","home_pts","score_home"]), errors="coerce"),
    "AwayScore": pd.to_numeric(_col(raw, ["away_score","AwayScore","away_points","away_pts","score_away"]), errors="coerce"),
    "season": season,
    "week": week,
})

# build gid_* only when we actually have a date
away_tok = out["_away_nick"].astype(str).map(_nick_last)
home_tok = out["_home_nick"].astype(str).map(_nick_last)
mask_has_date = out["_date_iso"].notna() & out["_date_iso"].ne("")

out["gid_norm"] = ""
out["gid_swap"] = ""
out.loc[mask_has_date, "gid_norm"] = (
    out.loc[mask_has_date, "_date_iso"].astype(str) + "_" + away_tok[mask_has_date] + "@" + home_tok[mask_has_date]
).map(_gid_norm)
out.loc[mask_has_date, "gid_swap"] = (
    out.loc[mask_has_date, "_date_iso"].astype(str) + "_" + home_tok[mask_has_date] + "@" + away_tok[mask_has_date]
).map(_gid_norm)

# DO NOT drop rows missing _date_iso — season/week fallback will use these
final = out[["_date_iso","season","week","_away_nick","_home_nick","gid_norm","gid_swap","HomeScore","AwayScore"]]

nonzero = int(((final["HomeScore"].fillna(0)!=0) | (final["AwayScore"].fillna(0)!=0)).sum())
print(f"[backfill] Rows: {len(final):,} | non-zero scores: {nonzero:,}")

final.to_csv(DEST_PATH, index=False, encoding="utf-8-sig")
print(f"[backfill] Wrote {DEST_PATH.resolve()}  ✓")

