# tools/fix_edges_for_settlement.py
import re, pandas as pd
from pathlib import Path

INFILE  = Path("exports/edges_graded_full.csv")
OUTFILE = Path("exports/edges_graded_full_normalized.csv")

NFL_NICKS = {
    "49ERS","BEARS","BENGALS","BILLS","BRONCOS","BROWNS","BUCCANEERS","CARDINALS","CHARGERS",
    "CHIEFS","COLTS","COMMANDERS","COWBOYS","DOLPHINS","EAGLES","FALCONS","GIANTS","JAGUARS",
    "JETS","LIONS","PACKERS","PANTHERS","PATRIOTS","RAIDERS","RAMS","RAVENS","SAINTS","SEAHAWKS",
    "STEELERS","TEXANS","TITANS","VIKINGS"
}
ALT = {"NINERS":"49ERS"}

def _clean_str(x):
    if not isinstance(x, str): return ""
    return re.sub(r"\s+", " ", x).strip()

def last_word_nick(s):
    w = _clean_str(s).upper().split()
    if not w: return ""
    nick = ALT.get(w[-1], w[-1])
    return nick if nick in NFL_NICKS else ""

def norm_market(m):
    m = _clean_str(m).lower()
    if m in {"h2h","ml","moneyline","money line"}: return "H2H"
    if m in {"spread","spreads","point spread"}:    return "SPREADS"
    if m in {"total","totals","over/under","ou"}:   return "TOTALS"
    return m.upper()

def best_datetime_series(df: pd.DataFrame) -> pd.Series:
    """Prefer _DateISO if present; else pick best date-like column; else parse from game_id."""
    idx = df.index
    out = pd.Series([""] * len(df), index=idx, dtype="string")

    # 0) Preferred explicit ISO column
    if "_DateISO" in df.columns:
        s = pd.to_datetime(df["_DateISO"], errors="coerce", utc=True, format="%Y-%m-%d")
        ok = s.notna()
        out.loc[ok] = s.loc[ok].dt.date.astype("string")
        print(f"[date] chosen='_DateISO' valid_rows={int((out!='').sum()):,}")
        return out

    # 1) Heuristic scan (kept for other files)
    preferred = [
        "date","Date","event_date","eventDate","commence_time","commenceTime",
        "game_date","GameDate","kickoff","start_time","StartTime","start","Start",
        "timestamp","ts","last_update","lastUpdate","created_at","updated_at"
    ]
    ordered = preferred + [c for c in df.columns if c not in preferred]
    best_name, best_valid = None, -1
    for c in ordered:
        if c not in df.columns:
            continue
        s = df[c]
        try:
            if pd.api.types.is_numeric_dtype(s):
                s2 = pd.to_numeric(s, errors="coerce")
                dt = pd.to_datetime(s2.where(s2.between(1e8, 2e10)), unit="s", errors="coerce", utc=True)
                ms_mask = dt.isna()
                if ms_mask.any():
                    dt2 = pd.to_datetime(s2.where(s2.between(1e11, 2e13)), unit="ms", errors="coerce", utc=True)
                    dt = dt.fillna(dt2)
            else:
                dt = pd.to_datetime(s.astype(str), errors="coerce", utc=True)
        except Exception:
            continue
        ok = dt.notna() & dt.dt.year.between(2010, 2035)
        valid = int(ok.sum())
        if valid > best_valid:
            best_valid, best_name = valid, c
            out = pd.Series([""] * len(df), index=idx, dtype="string")
            out.loc[ok] = dt.loc[ok].dt.date.astype("string")

    # 2) Fallback from game_id like 20250928_...
    need = out.eq("")
    if need.any() and "game_id" in df.columns:
        g = df.loc[need, "game_id"].astype(str)
        ymd = g.str.extract(r"^(?P<d>\d{8})_")["d"]
        dt2 = pd.to_datetime(ymd, format="%Y%m%d", errors="coerce", utc=True)
        ok2 = dt2.notna()
        out.loc[need[need].index[ok2]] = dt2.loc[ok2].dt.date.astype("string")
        if best_name is None and ok2.any():
            best_name = "game_id (YYYYMMDD)"

    print(f"[date] chosen='{best_name}' valid_rows={int((out!='').sum()):,}")
    return out

def detect_team_columns(df: pd.DataFrame):
    cols = set(df.columns)
    for h,a in [("_home_team","_away_team"),("home_team","away_team"),("HomeTeam","AwayTeam"),
                ("home","away"),("homeName","awayName"),("team_home","team_away")]:
        if {h,a} <= cols:
            return df[h].astype(str), df[a].astype(str), f"{h}/{a}"
    for t,o in [("team","opponent"),("Team","Opponent"),("_pick_team","_opp"),
                ("pick_team","opp"),("team","opp")]:
        if {t,o} <= cols:
            return df[t].astype(str), df[o].astype(str), f"{t}/{o}"
    for c in ["matchup","Matchup","event_name","name","event","Game","Title"]:
        if c in cols:
            s = df[c].astype(str)
            m = s.str.replace(r"\s+at\s+", "@", regex=True)\
                 .str.replace(r"\s+vs\.?\s+", "@", regex=True)\
                 .str.replace(r"\s+v\.?\s+", "@", regex=True)
            parts = m.str.split("@", n=1, expand=True)
            if isinstance(parts, pd.DataFrame) and parts.shape[1] == 2:
                return parts[0].fillna(""), parts[1].fillna(""), f"{c} (split)"
    # heuristic over text columns
    text_cols = [c for c in df.columns if df[c].dtype == "object"]
    if text_cols:
        c1 = "_home_team" if "_home_team" in df.columns else text_cols[0]
        c2 = "_away_team" if "_away_team" in df.columns else (text_cols[1] if len(text_cols) > 1 else None)
        if c2:
            return df[c1].astype(str), df[c2].astype(str), f"heuristic:{c1}/{c2}"
        return df[c1].astype(str), pd.Series([""]*len(df)), f"heuristic:{c1}/(none)"
    return pd.Series([""]*len(df)), pd.Series([""]*len(df)), "(not found)"

def main():
    df = pd.read_csv(INFILE, low_memory=False)
    print(f"[load] rows={len(df):,} cols={len(df.columns)}")
    print("[headers]", ", ".join(df.columns.astype(str)))

    # dates
    df["_date"] = best_datetime_series(df)

    # teams
    home_raw, away_raw, src = detect_team_columns(df)
    df["_home_raw"]  = home_raw
    df["_away_raw"]  = away_raw
    df["_home_nick"] = home_raw.map(last_word_nick)
    df["_away_nick"] = away_raw.map(last_word_nick)
    nickable = ((df["_home_nick"] != "") & (df["_away_nick"] != "")).sum()
    print(f"[teams] source={src} nickable_rows={int(nickable):,}")

    # market
    df["market_norm"] = df["market"].map(norm_market) if "market" in df.columns else ""

    # keys
    ok_mask = df["_date"].ne("") & df["_home_nick"].ne("") & df["_away_nick"].ne("")
    df["key_home"] = ""
    df["key_away"] = ""
    df.loc[ok_mask, "key_home"] = df.loc[ok_mask, "_home_nick"] + "@" + df.loc[ok_mask, "_date"]
    df.loc[ok_mask, "key_away"] = df.loc[ok_mask, "_away_nick"] + "@" + df.loc[ok_mask, "_date"]

    with_dates = int((df["_date"] != "").sum())
    with_teams = int(((df["_home_nick"] != "") & (df["_away_nick"] != "")).sum())
    ready      = int(ok_mask.sum())
    print(f"[summary] total_edges={len(df):,} · with_dates={with_dates:,} · with_teams={with_teams:,} · ready={ready:,}")

    OUTFILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTFILE, index=False, encoding="utf-8-sig")
    print(f"[save] → {OUTFILE}")

if __name__ == "__main__":
    main()

