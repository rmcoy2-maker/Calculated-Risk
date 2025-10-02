import csv
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

# ---------- Nickname canonicalization ----------
_ALIAS = {
    "REDSKINS": "COMMANDERS", "WASHINGTON": "COMMANDERS", "FOOTBALL": "COMMANDERS",
    "OAKLAND": "RAIDERS", "LV": "RAIDERS", "LAS": "RAIDERS", "VEGAS": "RAIDERS",
    "SD": "CHARGERS", "LA": "RAMS", "STL": "RAMS",
}

def _s(x) -> pd.Series:
    if isinstance(x, pd.Series):
        return x.astype("string").fillna("")
    return pd.Series([x], dtype="string")

def _one_of(df: pd.DataFrame, names: Iterable[str], default: str = "") -> pd.Series:
    for n in names:
        if n in df.columns:
            return _s(df[n])
    return pd.Series([default] * len(df), dtype="string")

def _nickify(series: pd.Series) -> pd.Series:
    s = _s(series).str.upper().str.replace(r"[^A-Z0-9 ]+", "", regex=True).str.strip()
    s = s.replace(_ALIAS)
    return s.str.replace(r"\s+", "_", regex=True)

def _int_str(series: pd.Series) -> pd.Series:
    si = pd.to_numeric(series, errors="coerce").astype("Int64")
    return si.astype("string").fillna("")

def normalize_scores(sc: pd.DataFrame) -> pd.DataFrame:
    s = sc.copy()

    date_raw = _one_of(s, ["Date", "date", "_Date", "_date"])
    s["_DateISO"] = pd.to_datetime(date_raw, errors="coerce").dt.date.astype("string").fillna("")

    s["_season"] = _int_str(_one_of(s, ["season", "Season"]))
    s["_week"]   = _int_str(_one_of(s, ["week", "Week"]))

    home = _nickify(_one_of(s, ["home_team", "HomeTeam", "_home_nick", "_home_team"]))
    away = _nickify(_one_of(s, ["away_team", "AwayTeam", "_away_nick", "_away_team"]))
    s["_home_nick"] = home
    s["_away_nick"] = away

    # Scores as numeric
    def _numcol(df, prefer, out):
        for c in prefer:
            if c in df.columns:
                s[out] = pd.to_numeric(df[c], errors="coerce")
                return
        s[out] = pd.NA

    _numcol(s, ["HomeScore", "home_score"], "home_score")
    _numcol(s, ["AwayScore", "away_score"], "away_score")

    ymd = pd.to_datetime(s["_DateISO"], errors="coerce").dt.strftime("%Y%m%d").fillna("")
    s["_key_date"] = (ymd + "_" + s["_away_nick"] + "_AT_" + s["_home_nick"]).str.strip("_")
    s["_key_home_sw"] = (s["_home_nick"] + "|" + s["_season"] + "|" + s["_week"])
    s["_key_away_sw"] = (s["_away_nick"] + "|" + s["_season"] + "|" + s["_week"])

    for c in ["_DateISO","_home_nick","_away_nick","_key_date","_key_home_sw","_key_away_sw"]:
        s[c] = s[c].astype("string")
    return s

def normalize_edges(e: pd.DataFrame) -> pd.DataFrame:
    df = e.copy()
    df["_season"] = _int_str(_one_of(df, ["Season","season"]))
    df["_week"]   = _int_str(_one_of(df, ["Week","week"]))

    home = _nickify(_one_of(df, ["_home_nick","_home_team","home_team","HomeTeam"]))
    away = _nickify(_one_of(df, ["_away_nick","_away_team","away_team","AwayTeam"]))
    df["_home_nick"] = home
    df["_away_nick"] = away

    date_raw = _one_of(df, ["Date","date","_Date"])
    df["_DateISO"] = pd.to_datetime(date_raw, errors="coerce").dt.date.astype("string").fillna("")

    ymd = pd.to_datetime(df["_DateISO"], errors="coerce").dt.strftime("%Y%m%d").fillna("")
    df["_key_date"] = (ymd + "_" + df["_away_nick"] + "_AT_" + df["_home_nick"]).str.strip("_")
    df["_key_home_sw"] = (df["_home_nick"] + "|" + df["_season"] + "|" + df["_week"])
    df["_key_away_sw"] = (df["_away_nick"] + "|" + df["_season"] + "|" + df["_week"])

    for c in ["_DateISO","_home_nick","_away_nick","_key_date","_key_home_sw","_key_away_sw"]:
        df[c] = df[c].astype("string")
    return df

def attach_scores(edges: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    e  = edges.copy()
    sc = scores[["_key_date","_key_home_sw","_key_away_sw","home_score","away_score"]].copy()

    merged = e.merge(sc[["_key_date","home_score","away_score"]],
                     on="_key_date", how="left")

    missing = merged["home_score"].isna() | merged["away_score"].isna()
    if missing.any():
        fallback = e.loc[missing, ["_key_home_sw","_key_away_sw"]].merge(
            sc[["_key_home_sw","_key_away_sw","home_score","away_score"]],
            on=["_key_home_sw","_key_away_sw"], how="left"
        )
        for c in ("home_score","away_score"):
            merged.loc[missing, c] = fallback[c].values

    merged["_joined_with_scores"] = (~merged["home_score"].isna()) & (~merged["away_score"].isna())
    return merged

def main():
    root = Path(__file__).resolve().parents[1]  # project root
    exp = root / "exports"

    scores_path = exp / "scores_1966-2025.csv"
    edges_path  = exp / "edges_graded_full_normalized_std_maxaligned.csv"

    print(f"[load] {scores_path}")
    scores = pd.read_csv(scores_path, low_memory=False)
    print(f"[load] {edges_path}")
    edges = pd.read_csv(edges_path, low_memory=False)

    print("[normalize] scores …")
    scores_n = normalize_scores(scores)
    print("[normalize] edges …")
    edges_n  = normalize_edges(edges)

    print("[merge] attach scores …")
    joined = attach_scores(edges_n, scores_n)

    out_path = exp / "edges_joined.csv"
    joined.to_csv(out_path, index=False, quoting=csv.QUOTE_NONNUMERIC, encoding="utf-8-sig")

    date_joined = int((joined["_key_date"].ne("") & joined["_joined_with_scores"]).sum())
    total_joined = int(joined["_joined_with_scores"].sum())

    print(f"[done] wrote: {out_path}")
    print(f"[stats] joined by date: {date_joined:,} | fallback (S/W): {total_joined - date_joined:,} | total: {total_joined:,}")


