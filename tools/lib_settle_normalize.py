import re, os
import pandas as pd
import numpy as np

EXPORTS = "exports"

def _as_str(s):
    return s.map(lambda x: "" if pd.isna(x) else str(x)) if isinstance(s, pd.Series) else pd.Series(dtype="object")

def to_nick(s: str) -> str:
    """Team nickname from full name (keeps digits for '49ers')."""
    if not isinstance(s, str): return ""
    parts = re.findall(r"[A-Za-z0-9]+", s.title())
    return parts[-1] if parts else ""

def _norm_date_naive(series) -> pd.Series:
    dtv = pd.to_datetime(series, errors="coerce", utc=True)
    return dtv.dt.tz_convert(None).dt.normalize()

def build_gid_from_cols(date_col, away_col, home_col) -> pd.Series:
    d = _as_str(date_col).str[:10].str.replace("-", "", regex=False)
    a = _as_str(away_col).map(to_nick).str.upper().str.replace(r"[^A-Z0-9]","", regex=True)
    h = _as_str(home_col).map(to_nick).str.upper().str.replace(r"[^A-Z0-9]","", regex=True)
    return (d + "_" + a.str[:12] + "_AT_" + h.str[:12]).str.strip()

def normalize_edges_for_settlement(edges: pd.DataFrame, lines_live: pd.DataFrame | None = None) -> pd.DataFrame:
    df = edges.copy()

    # ----- 1) DATE: best available source -----
    # Try common columns
    for c in ["_DateISO","Date","commence_time","start_time"]:
        if c in df.columns:
            cand = _norm_date_naive(df[c])
            if cand.notna().any():
                df["_date"] = cand
                break

    # Try extract from game_id (YYYYMMDD)
    if "_date" not in df.columns or df["_date"].isna().all():
        if "game_id" in df.columns:
            gid_ymd = df["game_id"].astype(str).str.extract(r"(?P<ymd>\d{8})")["ymd"]
            df["_date"] = pd.to_datetime(gid_ymd, format="%Y%m%d", errors="coerce")
            df["_date"] = df["_date"].dt.normalize()

    # Backfill from lines_live if still missing
    if ("_date" not in df.columns or df["_date"].isna().all()) and lines_live is not None and not lines_live.empty:
        L = lines_live.copy()
        L["_date"] = _norm_date_naive(L.get("commence_time"))
        L["home_nick"] = _as_str(L.get("home")).map(to_nick).str.upper()
        L["away_nick"] = _as_str(L.get("away")).map(to_nick).str.upper()
        # pick one row per (home,away,date)
        L_key = (L.dropna(subset=["_date"])
                  .drop_duplicates(subset=["home_nick","away_nick","_date"])[["home_nick","away_nick","_date"]])

    # ----- 2) TEAMS: fill _home_team/_away_team -----
    if "_home_team" not in df.columns:
        for c in ["home_team","home","team_home","HomeTeam","_home"]:
            if c in df.columns:
                df["_home_team"] = df[c]; break
    if "_away_team" not in df.columns:
        for c in ["away_team","away","team_away","AwayTeam","_away"]:
            if c in df.columns:
                df["_away_team"] = df[c]; break

    # If still missing teams, try to infer from H2H side and opponent columns (optional)
    # (Skip here unless you need it; primary fix is date.)

    df["_home_team"] = df.get("_home_team", "").fillna("")
    df["_away_team"] = df.get("_away_team", "").fillna("")

    df["_home_nick"] = _as_str(df["_home_team"]).map(to_nick).str.upper()
    df["_away_nick"] = _as_str(df["_away_team"]).map(to_nick).str.upper()

    # If we loaded L_key, we can backfill _date where teams are known
    if ("_date" not in df.columns or df["_date"].isna().any()) and lines_live is not None and not lines_live.empty:
        if "_date" not in df.columns:
            df["_date"] = pd.NaT
        # join on nicknames to get date
        df = df.merge(L_key, left_on=["_home_nick","_away_nick"], right_on=["home_nick","away_nick"], how="left", suffixes=("","_L"))
        df["_date"] = df["_date"].fillna(df["_date_L"])
        df.drop(columns=[c for c in ["home_nick","away_nick","_date_L"] if c in df.columns], inplace=True)

    # ----- 3) Keys used by your settle/join logic -----
    # Key format looks like NICK@YYYY-MM-DD in your screenshot
    date_str = df["_date"].dt.strftime("%Y-%m-%d")
    df["key_home"] = df["_home_nick"].str.upper() + "@" + date_str
    df["key_away"] = df["_away_nick"].str.upper() + "@" + date_str

    # Flags for diagnostics
    df["_has_date"]  = df["_date"].notna()
    df["_has_teams"] = df["_home_nick"].ne("") & df["_away_nick"].ne("")

    return df

