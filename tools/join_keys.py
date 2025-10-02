# tools/join_keys.py
from __future__ import annotations

import numpy as np
import pandas as pd

# -------------------- helpers --------------------
# serving_ui/app/lib/join_keys.py
import pandas as pd

def _as_str(s): return s.astype("string").fillna("")

def add_join_keys(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    # robust keys used throughout your app
    for col in ["_home_nick","_away_nick","_date_iso","_market_norm","side_norm"]:
        if col not in df.columns: df[col] = ""
    d = df.copy()
    d["_key_date"] = _as_str(d["_date_iso"]).str.slice(0,10)
    d["_key_home"] = _as_str(d["_key_date"]) + "|" + _as_str(d["_home_nick"])
    d["_key_away"] = _as_str(d["_key_date"]) + "|" + _as_str(d["_away_nick"])
    d["_key_game"] = d["_key_home"] + "@"+ _as_str(d["_away_nick"])
    return d

import re

def _looks_like_header_cell(x: str) -> bool:
    u = str(x or "").upper()
    return ("DATE" in u and "TIME" in u) or ("FAVORITE" in u and "UNDERDOG" in u)

def _strip_datetime_prefix(u: str) -> str:
    """
    Remove leading '9/10 1:00 ET ' / '09/10 13:00 PT ' patterns, keep rest.
    """
    u = str(u or "")
    return re.sub(r"^\s*\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}\s*(ET|PT|CT|MT)?\s*", "", u, flags=re.IGNORECASE)

def _remove_betting_numbers(u: str) -> str:
    """
    Remove spread/total numbers around teams so we can isolate names.
    e.g., 'DENVER -3.5 AT ST. LOUIS 45.5' -> 'DENVER AT ST. LOUIS'
    """
    u = str(u or "")
    # remove +/-xx.x, totals, and stray digits
    u = re.sub(r"[-+]?(\d+(\.\d+)?)", " ", u)
    # compress spaces
    u = re.sub(r"\s+", " ", u).strip()
    return u

def _parse_compound_home_cell(home_cell: str) -> tuple[str, str]:
    """
    Handle rows like '9/10 1:00 ET Denver -3.5 At St. Louis 45.5'
    Return (home_nick, away_nick) normalized ('' if cannot parse).
    Logic: 'AWAY AT HOME' is how books format matchups.
    """
    raw = str(home_cell or "")
    if not raw:
        return "", ""
    u = _strip_datetime_prefix(raw).upper()
    u = _remove_betting_numbers(u)
    # now expect something like 'DENVER AT ST LOUIS'
    parts = re.split(r"\s+\bAT\b\s+", u)
    if len(parts) != 2:
        return "", ""
    away_raw, home_raw = parts[0].strip(), parts[1].strip()
    # nickify to our format
    away = _nickify(pd.Series([away_raw]))[0]
    home = _nickify(pd.Series([home_raw]))[0]
    return home, away  # return (home, away)

import re

def _parse_matchup_to_teams(txt: str) -> tuple[str, str]:
    """
    Parse a single matchup string into (home_nick, away_nick) in our normalized nickname form.
    Rules:
      - 'AWAY @ HOME' or 'AWAY AT HOME'  -> away, home (book-style)
      - 'HOME vs AWAY' or 'HOME v AWAY'  -> home, away
      - 'HOME - AWAY' (fallback)         -> home, away
    Returns ('','') if we can't parse.
    """
    t = str(txt or "").strip()
    if not t:
        return "", ""
    u = re.sub(r"\s+", " ", t.upper())
    # Try '@' / ' AT '
    m = re.split(r"\s*@\s*|\s+\bAT\b\s+", u, maxsplit=1)
    if len(m) == 2:
        away_raw, home_raw = m[0].strip(), m[1].strip()
        home = _nickify(pd.Series([home_raw]))[0]
        away = _nickify(pd.Series([away_raw]))[0]
        return home, away
    # Try ' VS ' / ' V '
    m = re.split(r"\s+\bVS\.?\b\s+|\s+\bV\b\s+", u, maxsplit=1)
    if len(m) == 2:
        home_raw, away_raw = m[0].strip(), m[1].strip()
        home = _nickify(pd.Series([home_raw]))[0]
        away = _nickify(pd.Series([away_raw]))[0]
        return home, away
    # Fallback ' - '
    m = re.split(r"\s*-\s*", u, maxsplit=1)
    if len(m) == 2:
        home_raw, away_raw = m[0].strip(), m[1].strip()
        home = _nickify(pd.Series([home_raw]))[0]
        away = _nickify(pd.Series([away_raw]))[0]
        return home, away
    return "", ""

def _try_fill_teams_from_text(d: pd.DataFrame) -> pd.DataFrame:
    """
    If _home/_away are blank, try to extract from any of these text columns:
    'matchup','event','game','fixture','participants','teams','label','name','desc'
    (case-insensitive variants supported).
    """
    cand_cols = ["matchup","event","game","fixture","participants","teams","label","name","desc"]
    have_cols = [c for c in d.columns if c.lower() in cand_cols]
    if not have_cols:
        return d

    d = d.copy()
    need_home = d.get("_home_nick", "").astype("string").fillna("") == ""
    need_away = d.get("_away_nick", "").astype("string").fillna("") == ""
    need_any  = need_home | need_away
    if not need_any.any():
        return d

    # Build a single source text column (first non-empty among the candidates)
    src = pd.Series([""] * len(d), index=d.index, dtype="string")
    for c in have_cols:
        v = d[c].astype("string").fillna("")
        src = src.where(src.ne(""), v)

    # Parse row-wise
    parsed = src.map(lambda s: _parse_matchup_to_teams(s))
    home_parsed = parsed.map(lambda x: x[0])
    away_parsed = parsed.map(lambda x: x[1])

    # Fill only where missing
    if "_home_nick" not in d.columns:
        d["_home_nick"] = ""
    if "_away_nick" not in d.columns:
        d["_away_nick"] = ""
    d.loc[need_home & (home_parsed != ""), "_home_nick"] = home_parsed[need_home & (home_parsed != "")]
    d.loc[need_away & (away_parsed != ""), "_away_nick"] = away_parsed[need_away & (away_parsed != "")]

    # Rebuild cores
    d["_home_core"] = _nick_core(d["_home_nick"])
    d["_away_core"] = _nick_core(d["_away_nick"])
    return d

def _ci_cols(d: pd.DataFrame) -> dict[str, str]:
    """Case-insensitive column name lookup: returns {lower: actual}."""
    return {c.lower(): c for c in d.columns}

def _expand_odds_side_pairs(d: pd.DataFrame) -> pd.DataFrame:
    """
    If side is blank for most rows, try to expand paired columns into long rows.
    Supported pairs (case-insensitive):
      - home_* vs away_*  (H2H/SPREADS)
      - over_* vs under_* (TOTALS)
    """
    if len(d) == 0:
        return d

    ci = _ci_cols(d)
    suffixes = ["odds","price","american","decimal","line","total","points","number"]

    def pick(colbase: str) -> str | None:
        return ci.get(colbase.lower())

    def find_pairs(prefix_a: str, prefix_b: str):
        pairs = []
        for suf in suffixes:
            a = pick(f"{prefix_a}_{suf}")
            b = pick(f"{prefix_b}_{suf}")
            if a or b:
                pairs.append((suf, a, b))
        return pairs

    ha_pairs = find_pairs("home","away")
    ou_pairs = find_pairs("over","under")
    if not ha_pairs and not ou_pairs:
        return d

    paired_actual_cols = set([a for _, a, _ in ha_pairs if a] + [b for _, _, b in ha_pairs if b] +
                             [a for _, a, _ in ou_pairs if a] + [b for _, _, b in ou_pairs if b])
    carry_cols = [c for c in d.columns if c not in paired_actual_cols]

    out_rows = []
    for _, row in d.iterrows():
        base = row[carry_cols].to_dict()

        if ha_pairs:
            r_home = dict(base); r_away = dict(base)
            r_home["side_norm"] = "HOME"; r_away["side_norm"] = "AWAY"
            for suf, a, b in ha_pairs:
                if a and pd.notna(row.get(a, np.nan)):
                    if suf in ("line","total","points","number"):
                        r_home.setdefault("line", pd.to_numeric(row.get(a), errors="coerce"))
                    else:
                        r_home.setdefault("price", pd.to_numeric(row.get(a), errors="coerce"))
                if b and pd.notna(row.get(b, np.nan)):
                    if suf in ("line","total","points","number"):
                        r_away.setdefault("line", pd.to_numeric(row.get(b), errors="coerce"))
                    else:
                        r_away.setdefault("price", pd.to_numeric(row.get(b), errors="coerce"))
            out_rows.append(r_home); out_rows.append(r_away)

        if ou_pairs:
            r_over = dict(base); r_under = dict(base)
            r_over["side_norm"] = "OVER"; r_under["side_norm"] = "UNDER"
            for suf, a, b in ou_pairs:
                if a and pd.notna(row.get(a, np.nan)):
                    if suf in ("line","total","points","number"):
                        r_over.setdefault("line", pd.to_numeric(row.get(a), errors="coerce"))
                    else:
                        r_over.setdefault("price", pd.to_numeric(row.get(a), errors="coerce"))
                if b and pd.notna(row.get(b, np.nan)):
                    if suf in ("line","total","points","number"):
                        r_under.setdefault("line", pd.to_numeric(row.get(b), errors="coerce"))
                    else:
                        r_under.setdefault("price", pd.to_numeric(row.get(b), errors="coerce"))
            out_rows.append(r_over); out_rows.append(r_under)

    out = pd.DataFrame(out_rows)
    for req in ["line","price","side_norm"]:
        if req not in out.columns:
            out[req] = np.nan
    return out

def _first_nonempty(d: pd.DataFrame, names: list[str], default=""):
    for n in names:
        if n in d.columns:
            return d[n]
    return default

def _clean_blank(s: pd.Series) -> pd.Series:
    return _s(s).replace({"NAN": "", "nan": "", "NULL": "", "None": "", "NONE": ""})

def _s(x) -> pd.Series:
    """Coerce to pandas StringDtype Series and fill empty with ''."""
    if isinstance(x, pd.Series):
        return x.astype("string").fillna("")
    return pd.Series([x], dtype="string")

ALIAS = {
    "REDSKINS": "COMMANDERS", "WASHINGTON": "COMMANDERS", "FOOTBALL": "COMMANDERS",
    "OAKLAND": "RAIDERS", "LV": "RAIDERS", "LAS": "RAIDERS", "VEGAS": "RAIDERS",
    "SD": "CHARGERS", "STL": "RAMS",
}

def _pick_col(df: pd.DataFrame, names: list[str]) -> str | None:
    for n in names:
        if n in df.columns:
            return n
    return None

def _as_datetime_utc(s: pd.Series | str) -> pd.Series:
    ser = pd.to_datetime(_s(s), errors="coerce", utc=True)
    if isinstance(ser, pd.Series) and ser.isna().all():
        ser = pd.to_datetime(_s(s), errors="coerce", utc=False)
        try:
            ser = ser.dt.tz_localize("UTC")
        except Exception:
            pass
    return ser

def _date_iso_from_ts(ts: pd.Series) -> pd.Series:
    return pd.to_datetime(ts, errors="coerce").dt.date.astype("string").fillna("")

def _nickify(series: pd.Series) -> pd.Series:
    s = _s(series).str.upper().str.replace(r"[^A-Z0-9 ]+", "", regex=True).str.strip().replace(ALIAS)
    return s.str.replace(r"\s+", "_", regex=True)

def _nick_core(series: pd.Series) -> pd.Series:
    return _s(series).str.split("_").str[-1]

def _market_norm(s: pd.Series | str) -> pd.Series:
    t = _clean_blank(_s(s)).str.upper().str.replace(r"\s+", "", regex=True)
    return t.replace({
        "MONEYLINE": "H2H", "ML": "H2H",
        "POINTSPREAD": "SPREADS", "SPREAD": "SPREADS", "ATS": "SPREADS",
        "TOTALSPOINTS": "TOTALS", "TOTALS": "TOTALS", "TOTAL": "TOTALS", "OU": "TOTALS", "O/U": "TOTALS",
        "": ""
    })

def _side_norm(side: pd.Series, home_nick: pd.Series, away_nick: pd.Series) -> pd.Series:
    """
    Canonicalize pick side to HOME/AWAY/OVER/UNDER.
    Accepts team phrases ("BUFFALO BILLS"), nicknames, or cores ("BILLS").
    """
    s = _s(side).str.upper().str.strip()
    s = s.replace({"H": "HOME", "A": "AWAY", "OVER": "OVER", "UNDER": "UNDER", "O": "OVER", "U": "UNDER"})

    home_u = _s(home_nick).str.upper()
    away_u = _s(away_nick).str.upper()
    s = s.where(~s.eq(home_u), "HOME")
    s = s.where(~s.eq(away_u), "AWAY")

    from_core = _nick_core(_nickify(s))
    home_core = _nick_core(home_u)
    away_core = _nick_core(away_u)
    s = s.where(~from_core.eq(home_core), "HOME")
    s = s.where(~from_core.eq(away_core), "AWAY")

    s = s.where(s.isin(["HOME","AWAY","OVER","UNDER"]), "")
    return s.astype("string")

def _ensure_team_cols(df: pd.DataFrame, home_names: list[str], away_names: list[str]) -> pd.DataFrame:
    d = df.copy()
    d["_home_nick"] = _nickify(d.get("_home_nick", d.get(_pick_col(d, home_names), "")))
    d["_away_nick"] = _nickify(d.get("_away_nick", d.get(_pick_col(d, away_names), "")))
    d["_home_core"] = _nick_core(d["_home_nick"])
    d["_away_core"] = _nick_core(d["_away_nick"])
    return d

def _ensure_date_cols(df: pd.DataFrame, date_names: list[str]) -> pd.DataFrame:
    d = df.copy()
    ts_col = _pick_col(d, date_names)
    if ts_col:
        ts = _as_datetime_utc(d[ts_col])
    else:
        ts = pd.Series(pd.NaT, index=d.index, dtype="datetime64[ns, UTC]")
    d["ts"] = ts
    d["_DateISO"] = _date_iso_from_ts(d["ts"])
    d["_key_date"] = d["_DateISO"]
    return d

def _ensure_sw_cols(df: pd.DataFrame, season_names: list[str], week_names: list[str]) -> pd.DataFrame:
    d = df.copy()
    season = _s(d.get("_season", d.get(_pick_col(d, season_names), "")))
    week   = _s(d.get("_week",   d.get(_pick_col(d, week_names),   "")))
    if (season == "").all() and ("_DateISO" in d.columns) and (d["_DateISO"] != "").any():
        season = d["_DateISO"].str.slice(0, 4)
    d["_season"] = season
    d["_week"]   = week
    d["_key_home_sw"] = _nick_core(d["_home_nick"]) + "|" + d["_season"] + "|" + d["_week"]
    d["_key_away_sw"] = _nick_core(d["_away_nick"]) + "|" + d["_season"] + "|" + d["_week"]
    return d

# -------------------- add keys for each type --------------------

def add_join_keys_edges(e: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize EDGES-like frames.
    Adds: _home/_away nick+core, ts/_DateISO/_key_date, _season/_week,
          _key_home_sw/_key_away_sw, _key_strict_date, market_norm, side_norm
    """
    d = e.copy()
    d = _ensure_team_cols(d,
        home_names=["home","home_team","HomeTeam","team_home","TeamHome"],
        away_names=["away","away_team","AwayTeam","team_away","TeamAway"],
    )
    d = _ensure_date_cols(d,
        date_names=["commence_time","start_time","game_time","Date","date","ts","timestamp","updated_at","last_updated","game_date"],
    )
    d = _ensure_sw_cols(d,
        season_names=["_season","season","Season","year","Year"],
        week_names=["_week","week","Week","game_week","GameWeek"],
    )
    d["_key_strict_date"] = _s(d["_key_date"]) + "|" + _s(d["_home_core"]) + "@" + _s(d["_away_core"])

    side_raw = d.get("side", d.get("Side", d.get("pick_side", d.get("PickSide", ""))))
    d["side_norm"] = _side_norm(side_raw, d["_home_nick"], d["_away_nick"])

    line_guess = pd.to_numeric(
        d.get("line", d.get("handicap", d.get("total", d.get("spread", d.get("Line", np.nan))))),
        errors="coerce"
    )

    provided_market = d.get("market", d.get("Market", d.get("bet_type", d.get("BetType", ""))))
    d["market_norm"] = _market_norm(provided_market)

    blank = (d["market_norm"] == "") | d["market_norm"].isna()
    if blank.any():
        infer_totals = blank & d["side_norm"].isin(["OVER","UNDER"])
        infer_spread = blank & ~infer_totals & line_guess.notna()
        infer_h2h    = blank & ~(infer_totals | infer_spread)
        d.loc[infer_totals, "market_norm"] = "TOTALS"
        d.loc[infer_spread, "market_norm"] = "SPREADS"
        d.loc[infer_h2h,    "market_norm"] = "H2H"
    return d

def add_join_keys_scores(sc: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize SCORES-like frames.
    Adds: team/date/SW keys, _key_strict_date, and canonical home_score/away_score.
    """
    d = sc.copy()
    d = _ensure_team_cols(d,
        home_names=["home","home_team","HomeTeam","HOME","TeamHome"],
        away_names=["away","away_team","AwayTeam","AWAY","TeamAway"],
    )
    d = _ensure_date_cols(d,
        date_names=["Date","date","game_date","commence_time","start_time","ts","timestamp"],
    )
    d = _ensure_sw_cols(d,
        season_names=["_season","season","Season","year","Year"],
        week_names=["_week","week","Week","game_week","GameWeek"],
    )
    d["_key_strict_date"] = _s(d["_key_date"]) + "|" + _s(d["_home_core"]) + "@" + _s(d["_away_core"])

    d["home_score"] = pd.to_numeric(
        d.get("home_score", d.get("HomeScore", d.get("HOME_SCORE", np.nan))),
        errors="coerce"
    )
    d["away_score"] = pd.to_numeric(
        d.get("away_score", d.get("AwayScore", d.get("AWAY_SCORE", np.nan))),
        errors="coerce"
    )
    return d

def add_join_keys_odds(o: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize ODDS/lines-like frames.
    Fixes:
      - Drop header rows accidentally ingested.
      - Parse compound 'home' strings like '9/10 1:00 ET Denver -3.5 At St. Louis 45.5'.
      - If side not present, expand to long (HOME/AWAY or OVER/UNDER).
      - Infer market when blank.
      - Default -110 for SPREADS/TOTALS price if missing (audit-friendly).
    """
    d = o.copy()

    # 0) Drop header-as-row junk
    #   e.g., away == 'Date & Time Favorite Line Underdog Total' or home contains it
    if "home" in d.columns and "away" in d.columns:
        mask_header = _s(d["home"]).map(_looks_like_header_cell) | _s(d["away"]).map(_looks_like_header_cell)
        d = d.loc[~mask_header].copy()

    # 1) Teams: handle normal and weird compound home cell
    d = _ensure_team_cols(d,
        home_names=["home","home_team","HomeTeam","HOME","team_home","TeamHome","home_name","Home","participant_home"],
        away_names=["away","away_team","AwayTeam","AWAY","team_away","TeamAway","away_name","Away","participant_away"],
    )

    # Parse compound home cells where cores are still blank or look suspicious
    need_parse = (d["_home_nick"] == "") | (d["_away_nick"] == "")
    if need_parse.any() and "home" in d.columns:
        for idx in d.index[need_parse]:
            home_txt = d.at[idx, "home"]
            home_nick, away_nick = _parse_compound_home_cell(home_txt)
            if home_nick and away_nick:
                d.at[idx, "_home_nick"] = home_nick
                d.at[idx, "_away_nick"] = away_nick
        # rebuild cores after any fills
        d["_home_core"] = _nick_core(d["_home_nick"])
        d["_away_core"] = _nick_core(d["_away_nick"])

    # 2) Date keys
    d = _ensure_date_cols(d,
        date_names=["asof_ts","commence_time","start_time","game_time","event_time","Date","date","ts","timestamp","updated_at","last_updated","EventDate","GameDate"],
    )
    d = _ensure_sw_cols(d,
        season_names=["_season","season","Season","year","Year","season"],
        week_names=["_week","week","Week","game_week","GameWeek","week"],
    )

    # 3) Market & side
    market_src = _first_nonempty(d, ["market","Market","bet_type","BetType","wager_type","WagerType","category","Category","label","Label"], "")
    d["market_norm"] = _market_norm(market_src)

    # side from columns if present (rare here)
    side_src = _first_nonempty(d, [
        "side","Side","selection","Selection","pick","Pick","outcome","Outcome",
        "runner","Runner","participant","Participant","team","Team","name","Name"
    ], "")
    d["side_norm"] = _side_norm(side_src, d["_home_nick"], d["_away_nick"])

    # 4) If sides are still blank, expand to long
    need_expand = d["side_norm"].fillna("").eq("").all()
    if need_expand:
        # try paired columns first
        d = _expand_odds_side_pairs(d)
        # If still no side_norm (no paired cols), synthesize HOME/AWAY rows for H2H;
        # and OVER/UNDER rows for TOTALS when we have a total_close value.
        if "side_norm" not in d.columns or d["side_norm"].fillna("").eq("").all():
            base_cols = [c for c in d.columns if c not in ("side_norm","line","price")]
            rows = []
            for _, r in d.iterrows():
                base = {k: r.get(k, None) for k in base_cols}
                mkt = str(r.get("market_norm",""))
                # totals line if present
                tot = pd.to_numeric(r.get("total_close", np.nan), errors="coerce")
                spr = pd.to_numeric(r.get("spread_close", np.nan), errors="coerce")
                # H2H HOME/AWAY
                if mkt in ("", "H2H", "SPREADS", "TOTALS"):
                    a = dict(base); a["side_norm"] = "HOME"; a["market_norm"] = "H2H"; a["line"] = np.nan; a["price"] = np.nan; rows.append(a)
                    b = dict(base); b["side_norm"] = "AWAY"; b["market_norm"] = "H2H"; b["line"] = np.nan; b["price"] = np.nan; rows.append(b)
                # SPREADS (if we have a spread_close; use -110 by default)
                if not np.isnan(spr):
                    h = dict(base); h["side_norm"] = "HOME"; h["market_norm"] = "SPREADS"; h["line"] = float(spr);  h["price"] = -110; rows.append(h)
                    aw = dict(base); aw["side_norm"] = "AWAY"; aw["market_norm"] = "SPREADS"; aw["line"] = -float(spr); aw["price"] = -110; rows.append(aw)
                # TOTALS (if we have total_close; use -110 by default)
                if not np.isnan(tot):
                    ov = dict(base); ov["side_norm"] = "OVER";  ov["market_norm"] = "TOTALS"; ov["line"] = float(tot); ov["price"] = -110; rows.append(ov)
                    un = dict(base); un["side_norm"] = "UNDER"; un["market_norm"] = "TOTALS"; un["line"] = float(tot); un["price"] = -110; rows.append(un)
            d = pd.DataFrame(rows) if rows else d

        # Rebuild cores/keys after expansion/synthesis
        if "_home_nick" not in d.columns: d["_home_nick"] = ""
        if "_away_nick" not in d.columns: d["_away_nick"] = ""
        d["_home_core"] = _nick_core(d["_home_nick"])
        d["_away_core"] = _nick_core(d["_away_nick"])
        if "_DateISO" not in d.columns and "ts" in d.columns:
            d["_DateISO"] = _date_iso_from_ts(d["ts"])
        if "_key_date" not in d.columns:
            d["_key_date"] = d.get("_DateISO", "")

    # 5) Infer market if still blank (based on side/line)
    blank = (d.get("market_norm","") == "") | d.get("market_norm","").isna()
    if blank.any():
        infer_totals = blank & d["side_norm"].isin(["OVER","UNDER"])
        infer_spread = blank & ~infer_totals & d.get("line", pd.Series(dtype=float)).notna()
        infer_h2h    = blank & ~(infer_totals | infer_spread)
        d.loc[infer_totals, "market_norm"] = "TOTALS"
        d.loc[infer_spread, "market_norm"] = "SPREADS"
        d.loc[infer_h2h,    "market_norm"] = "H2H"

    # 6) Final strict key
    d["_key_strict_date"] = _s(d.get("_key_date","")) + "|" + _s(d.get("_home_core","")) + "@" + _s(d.get("_away_core",""))
    return d

# -------------------- dispatcher (back-compat) --------------------

def add_join_keys(df: pd.DataFrame, kind: str | None = None) -> pd.DataFrame:
    """
    Backward-compatible dispatcher:
      - If kind is provided ("edges" | "scores" | "odds"), use that.
      - Otherwise, infer based on columns.
    """
    if kind:
        k = str(kind).strip().lower()
        if k in ("edge", "edges"):
            return add_join_keys_edges(df)
        if k in ("score", "scores"):
            return add_join_keys_scores(df)
        if k in ("odd", "odds", "line", "lines"):
            return add_join_keys_odds(df)
        # fall through to heuristic if unrecognized

    cols = set(df.columns)
    if {"book","odds","price","handicap","total","spread"}.intersection(cols):
        return add_join_keys_odds(df)
    if {"home_score","away_score","HomeScore","AwayScore"}.intersection(cols):
        return add_join_keys_scores(df)
    return add_join_keys_edges(df)

