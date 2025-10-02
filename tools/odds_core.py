# tools/odds_core.py
from __future__ import annotations

import numpy as np
import pandas as pd

# -------------------- helpers --------------------
def _first_nonempty(d: pd.DataFrame, names: list[str], default=""):
    for n in names:
        if n in d.columns:
            return d[n]
    return default

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

def _nickify(series: pd.Series) -> pd.Series:
    s = _s(series).str.upper().str.replace(r"[^A-Z0-9 ]+", "", regex=True).str.strip().replace(ALIAS)
    return s.str.replace(r"\s+", "_", regex=True)

def _nick_core(series: pd.Series) -> pd.Series:
    return _s(series).str.split("_").str[-1]

def _market_norm(s: pd.Series | str) -> pd.Series:
    t = _s(s).str.upper().str.replace(r"\s+", "", regex=True)
    return t.replace({
        "MONEYLINE": "H2H", "ML": "H2H",
        "POINTSPREAD": "SPREADS", "SPREAD": "SPREADS", "ATS": "SPREADS",
        "TOTALSPOINTS": "TOTALS", "TOTALS": "TOTALS", "TOTAL": "TOTALS", "OU": "TOTALS", "O/U": "TOTALS",
        "": ""
    })

def _pick_col(df: pd.DataFrame, names: list[str]) -> str | None:
    for n in names:
        if n in df.columns:
            return n
    return None

def _as_datetime_utc(s: pd.Series | str) -> pd.Series:
    ser = pd.to_datetime(_s(s), errors="coerce", utc=True)
    # If all-NaT with utc=True, try naive parse (sometimes input timestamps are naive)
    if isinstance(ser, pd.Series) and ser.isna().all():
        ser = pd.to_datetime(_s(s), errors="coerce", utc=False)
        try:
            ser = ser.dt.tz_localize("UTC")
        except Exception:
            # Already tz-aware or still NaT; coerce to UTC if possible
            with pd.option_context("display.max_colwidth", None):
                pass
    return ser

def _date_iso_from_ts(ts: pd.Series) -> pd.Series:
    return pd.to_datetime(ts, errors="coerce").dt.date.astype("string").fillna("")

def _side_to_homeaway(side: pd.Series, home_nick: pd.Series, away_nick: pd.Series) -> pd.Series:
    """
    Normalize side to HOME/AWAY/OVER/UNDER, accepting team phrases like 'BUFFALO BILLS'.
    """
    side = _s(side).str.upper()
    home_u = _s(home_nick).str.upper()
    away_u = _s(away_nick).str.upper()

    # direct team name match
    is_home = side == home_u
    is_away = side == away_u
    side = side.where(~is_home, "HOME")
    side = side.where(~is_away, "AWAY")

    # core token match (BUFFALO BILLS -> BILLS etc.)
    from_core = _nick_core(_nickify(side))
    home_core = _nick_core(home_u)
    away_core = _nick_core(away_u)
    side = side.where(~from_core.eq(home_core), "HOME")
    side = side.where(~from_core.eq(away_core), "AWAY")

    # OU variants
    side = side.mask(side.str.fullmatch(r"O|OVER",  na=False), "OVER")
    side = side.mask(side.str.fullmatch(r"U|UNDER", na=False), "UNDER")
    return side.astype("string")

def _ensure_edge_team_cols(e: pd.DataFrame) -> pd.DataFrame:
    e = e.copy()
    # Home/Away team names
    e["_home_nick"] = _nickify(
        e.get("_home_nick", e.get("home", e.get("home_team", e.get("HomeTeam", ""))))
    )
    e["_away_nick"] = _nickify(
        e.get("_away_nick", e.get("away", e.get("away_team", e.get("AwayTeam", ""))))
    )
    e["_home_core"] = _nick_core(e["_home_nick"])
    e["_away_core"] = _nick_core(e["_away_nick"])
    return e

def _ensure_edge_date_cols(e: pd.DataFrame) -> pd.DataFrame:
    e = e.copy()
    # Prefer explicit game start if present
    ts_col = _pick_col(e, [
        "commence_time","start_time","game_time",
        "ts","timestamp","updated_at","last_updated",
        "Date","date","game_date"
    ])
    if ts_col:
        ts = _as_datetime_utc(e[ts_col])
    else:
        ts = pd.Series(pd.NaT, index=e.index, dtype="datetime64[ns, UTC]")
    e["ts"] = ts
    e["_DateISO"]  = _date_iso_from_ts(e["ts"])
    e["_key_date"] = e["_DateISO"]
    return e

def _ensure_edge_sw_cols(e: pd.DataFrame) -> pd.DataFrame:
    e = e.copy()
    # Season/Week best effort
    season = _s(e.get("_season", e.get("season", e.get("Season", ""))))
    week   = _s(e.get("_week",   e.get("week",   e.get("Week",   ""))))
    if (season == "").all() and ("_DateISO" in e.columns) and (e["_DateISO"] != "").any():
        season = e["_DateISO"].str.slice(0, 4)
    e["_season"] = season
    e["_week"]   = week
    e["_key_home_sw"] = _nick_core(e["_home_nick"]) + "|" + e["_season"] + "|" + e["_week"]
    e["_key_away_sw"] = _nick_core(e["_away_nick"]) + "|" + e["_season"] + "|" + e["_week"]
    return e

def _ensure_edge_market_side(e: pd.DataFrame) -> pd.DataFrame:
    e = e.copy()
    e["market_norm"] = _market_norm(
        e.get("market", e.get("Market", e.get("bet_type", e.get("BetType", ""))))
    )
    side_raw = _s(e.get("side", e.get("Side", e.get("pick_side", e.get("PickSide", "")))))
    e["side"] = _side_to_homeaway(side_raw, e["_home_nick"], e["_away_nick"])
    return e

def _ensure_edge_numeric(e: pd.DataFrame) -> pd.DataFrame:
    e = e.copy()
    # Try common numeric columns for line/price (doesn't overwrite if already present)
    if "line" not in e.columns:
        e["line"] = pd.to_numeric(
            e.get("line", e.get("handicap", e.get("total", e.get("spread", e.get("Line", np.nan))))),
            errors="coerce"
        )
    if "price" not in e.columns:
        e["price"] = pd.to_numeric(
            e.get("price", e.get("odds", e.get("Price", np.nan))),
            errors="coerce"
        )
    return e

# -------------------- normalization --------------------

def normalize_odds_lines(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()

    # Book
    d["book"] = _s(_first_nonempty(d, ["book","bookmaker","sportsbook","Sportsbook","source","Source"], ""))

    # Timestamp
    ts_src = _first_nonempty(d, [
        "commence_time","start_time","game_time","event_time","EventTime",
        "ts","timestamp","updated_at","last_updated",
        "Date","date","GameDate","EventDate",
    ], "")
    d["ts"] = _as_datetime_utc(ts_src)

    # Date keys
    d["_DateISO"]  = _date_iso_from_ts(d["ts"])
    d["_key_date"] = d["_DateISO"]

    # Teams
    home_src = _first_nonempty(d, ["home","home_team","HomeTeam","HOME","team_home","TeamHome","home_name","Home","participant_home"], "")
    away_src = _first_nonempty(d, ["away","away_team","AwayTeam","AWAY","team_away","TeamAway","away_name","Away","participant_away"], "")
    d["_home_nick"] = _nickify(home_src)
    d["_away_nick"] = _nickify(away_src)
    d["_home_core"] = _nick_core(d["_home_nick"])
    d["_away_core"] = _nick_core(d["_away_nick"])

    # Season/Week best effort
    d["_season"] = _s(_first_nonempty(d, ["_season","season","Season","year","Year"], ""))
    d["_week"]   = _s(_first_nonempty(d, ["_week","week","Week","game_week","GameWeek"], ""))
    if (d["_season"] == "").all() and (d["_DateISO"] != "").any():
        d["_season"] = d["_DateISO"].str.slice(0, 4)

    d["_key_home_sw"] = _nick_core(d["_home_nick"]) + "|" + d["_season"] + "|" + d["_week"]
    d["_key_away_sw"] = _nick_core(d["_away_nick"]) + "|" + d["_season"] + "|" + d["_week"]

    # ------- Market -------
    market_src = _first_nonempty(d, ["market","Market","bet_type","BetType","wager_type","WagerType","category","Category","label","Label"], "")
    d["market_norm"] = _market_norm(market_src)

    # ------- Side -------
    # pull a bunch of possible side/selection columns
    side_src = _first_nonempty(d, [
        "side","Side","selection","Selection","pick","Pick","outcome","Outcome",
        "runner","Runner","participant","Participant","team","Team","name","Name"
    ], "")
    # Special: map generic outcomes to side
    s_upper = _s(side_src).str.upper()
    s_upper = s_upper.replace({"HOME":"HOME","AWAY":"AWAY","OVER":"OVER","UNDER":"UNDER","O":"OVER","U":"UNDER"})
    # Fallback to team/phrase matching
    side_guess = _side_to_homeaway(s_upper, d["_home_nick"], d["_away_nick"])
    d["side"] = side_guess

    # Also produce side_norm for join_audit convenience
    d["side_norm"] = d["side"]

    # ------- Line / Price -------
    # line can live under many names
    d["line"] = pd.to_numeric(_first_nonempty(d, ["line","Line","handicap","Handicap","total","Total","points","Points","number","Number"], np.nan), errors="coerce")

    # American odds
    price_american = pd.to_numeric(_first_nonempty(d, ["price","Price","odds","Odds","american","American","us_odds","US_Odds"], np.nan), errors="coerce")
    # If price is clearly decimal odds, convert to American; else keep as-is
    # Heuristic: decimals typically between ~1.01 and ~100; Americans are like +/-100 to +/-1000
    decimal_src = pd.to_numeric(_first_nonempty(d, ["decimal","Decimal","odds_decimal","OddsDecimal"], np.nan), errors="coerce")
    # prefer explicit american if present; else if decimal present convert; else keep price_american
    def dec_to_american(x):
        if pd.isna(x): return np.nan
        try:
            x = float(x)
        except Exception:
            return np.nan
        if x <= 1.0:
            return np.nan
        return (100 * (x - 1)) if x >= 2.0 else (-100 / (x - 1))
    d["price"] = price_american
    need_price = d["price"].isna() & decimal_src.notna()
    d.loc[need_price, "price"] = decimal_src[need_price].map(dec_to_american)

    # Final normalization guardrails
    blank_mkt = (d["market_norm"] == "") | d["market_norm"].isna()
    if blank_mkt.any():
        infer_totals = blank_mkt & d["side_norm"].isin(["OVER","UNDER"])
        infer_spread = blank_mkt & ~infer_totals & d["line"].notna()
        infer_h2h    = blank_mkt & ~(infer_totals | infer_spread)
        d.loc[infer_totals, "market_norm"] = "TOTALS"
        d.loc[infer_spread, "market_norm"] = "SPREADS"
        d.loc[infer_h2h,    "market_norm"] = "H2H"

    return d

# -------------------- attach --------------------

def _rank_preferred_books(o: pd.DataFrame, prefer_books: list[str] | None) -> pd.Series:
    if not prefer_books:
        return pd.Series(0, index=o.index)
    pref_map = {b.upper(): i for i, b in enumerate(prefer_books)}
    return _s(o.get("book", "")).str.upper().map(pref_map).fillna(9999).astype(int)

def _best_row_per_group(o: pd.DataFrame, by_cols: list[str]) -> pd.DataFrame:
    """
    Within each group, choose the preferred book first (lowest _book_rank),
    then the most recent ts, then the row with non-null price, then non-null line.
    """
    o = o.copy()
    # NaT sorts last; we want newest first -> rank by -ts
    ts_rank = o["ts"].astype("int64", errors="ignore") if "ts" in o.columns else pd.Series(0, index=o.index)
    o["_ts_rank"] = -pd.to_numeric(ts_rank, errors="coerce").fillna(0)
    o["_price_missing"] = o["price"].isna().astype(int)
    o["_line_missing"]  = o["line"].isna().astype(int)

    o = o.sort_values(by=by_cols + ["_book_rank","_ts_rank","_price_missing","_line_missing"], ascending=[True]*len(by_cols) + [True, True, True, True])
    picked = o.groupby(by_cols, as_index=False).head(1).copy()

    # Clean temp cols
    return picked.drop(columns=[c for c in ["_ts_rank","_price_missing","_line_missing","_book_rank"] if c in picked.columns])

def attach_odds(
    edges: pd.DataFrame,
    odds_tidy: pd.DataFrame,
    prefer_books: list[str] | None = None
) -> pd.DataFrame:
    """
    Attach odds to graded edges using:
      1) STRICT: _key_date + teams(cores) + market_norm + side
      2) FALLBACK: _key_home_sw/_key_away_sw + market_norm + side

    Fill order: odds2 (SW) -> odds1 (date).
    If price still missing for SPREADS/TOTALS, default to -110.
    Output columns added:
      _odds_book, _odds_ts, _odds_market, _odds_side, _odds_line, _odds_price, _odds_join, _joined_with_odds
    """
    if edges is None or len(edges) == 0:
        return edges

    e = edges.copy()

    # --- Ensure required key columns on EDGES ---
    e = _ensure_edge_team_cols(e)
    e = _ensure_edge_date_cols(e)
    e = _ensure_edge_sw_cols(e)
    e = _ensure_edge_market_side(e)
    e = _ensure_edge_numeric(e)

    # --- Prepare ODDS (assume already normalized; normalize if not) ---
    o = odds_tidy.copy()
    required_cols = {
        "book","ts","_DateISO","_key_date","_home_nick","_away_nick","_home_core","_away_core",
        "_season","_week","_key_home_sw","_key_away_sw","market_norm","side","line","price"
    }
    if not required_cols.issubset(set(o.columns)):
        o = normalize_odds_lines(o)

    # Rank preferred books for selection
    o = o.copy()
    o["_book_rank"] = _rank_preferred_books(o, prefer_books)

    # ---------- STRICT JOIN: by date + cores + market + side ----------
    o1 = o.copy()
    o1["__key_strict"] = (
        _s(o1["_key_date"]) + "|" +
        _s(o1["_home_core"]) + "@" + _s(o1["_away_core"]) + "|" +
        _s(o1["market_norm"]) + "|" + _s(o1["side"])
    )
    e1 = e.copy()
    e1["__key_strict"] = (
        _s(e1["_key_date"]) + "|" +
        _s(e1["_home_core"]) + "@" + _s(e1["_away_core"]) + "|" +
        _s(e1["market_norm"]) + "|" + _s(e1["side"])
    )

    # Choose best odds per strict key
    o1_best = _best_row_per_group(
        o1.assign(_book_rank=o1["_book_rank"]),
        by_cols=["__key_strict"]
    )[["__key_strict","book","ts","market_norm","side","line","price"]].rename(columns={
        "book": "_odds_book",
        "ts": "_odds_ts",
        "market_norm": "_odds_market",
        "side": "_odds_side",
        "line": "_odds_line",
        "price": "_odds_price",
    })
    merged_date = e1.merge(o1_best, on="__key_strict", how="left")
    merged_date["_odds_join"] = np.where(merged_date["_odds_book"].notna(), "date", "")

    # ---------- SW FALLBACK: by season-week + market + side + swapped teams ----------
    # Build home/away SW keys (handle potential swap)
    o2 = o.copy()
    o2["__key_sw_home"] = _s(o2["_key_home_sw"]) + "|" + _s(o2["market_norm"]) + "|" + _s(o2["side"])
    o2["__key_sw_away"] = _s(o2["_key_away_sw"]) + "|" + _s(o2["market_norm"]) + "|" + _s(o2["side"])

    # For edges, create both possibilities and match either (home or away key indicates which team the side refers to)
    # We'll build two candidate keys and union-pick best by book+timestamp.
    e2 = e.copy()
    e2["__key_sw_home"] = _s(e2["_key_home_sw"]) + "|" + _s(e2["market_norm"]) + "|" + _s(e2["side"])
    e2["__key_sw_away"] = _s(e2["_key_away_sw"]) + "|" + _s(e2["market_norm"]) + "|" + _s(e2["side"])

    # Concatenate home/away keyed odds (they both carry the same odds row identity)
    o2_long = pd.concat([
        o2[["__key_sw_home","book","ts","market_norm","side","line","price"]].rename(columns={"__key_sw_home":"__key_sw"}),
        o2[["__key_sw_away","book","ts","market_norm","side","line","price"]].rename(columns={"__key_sw_away":"__key_sw"}),
    ], ignore_index=True)
    o2_long = o2_long.join(o["_book_rank"])  # align on original index if possible; if misaligned, fill 0
    if "_book_rank" not in o2_long.columns:
        o2_long["_book_rank"] = 0

    o2_best = _best_row_per_group(
        o2_long.assign(_book_rank=o2_long["_book_rank"]),
        by_cols=["__key_sw"]
    )[["__key_sw","book","ts","market_norm","side","line","price"]].rename(columns={
        "book": "_odds_book",
        "ts": "_odds_ts",
        "market_norm": "_odds_market",
        "side": "_odds_side",
        "line": "_odds_line",
        "price": "_odds_price",
    })

    # Try match on home key first
    e2_home = e2.merge(o2_best.rename(columns={"__key_sw":"__key_sw_home"}), on="__key_sw_home", how="left", suffixes=("",""))
    e2_home["_odds_join_sw"] = np.where(e2_home["_odds_book"].notna(), "sw", "")

    # For ones not matched, try away key
    need_away = e2_home["_odds_book"].isna()
    if need_away.any():
        e2_away = e2.loc[need_away].merge(o2_best.rename(columns={"__key_sw":"__key_sw_away"}), on="__key_sw_away", how="left")
        # Fill back into e2_home
        for c in ["_odds_book","_odds_ts","_odds_market","_odds_side","_odds_line","_odds_price"]:
            e2_home.loc[need_away, c] = e2_away.get(c)
        e2_home.loc[need_away, "_odds_join_sw"] = np.where(e2_away["_odds_book"].notna(), "sw", e2_home.loc[need_away, "_odds_join_sw"])

    # ---------- COMBINE: prefer SW attach then fallback to DATE attach ----------
    out = merged_date.copy()
    # For any rows missing odds from strict-date, fill from sw
    missing_date = out["_odds_book"].isna()
    if missing_date.any():
        fill_cols = ["_odds_book","_odds_ts","_odds_market","_odds_side","_odds_line","_odds_price"]
        for c in fill_cols:
            out.loc[missing_date, c] = e2_home.loc[missing_date, c]
        # join marker
        out.loc[missing_date, "_odds_join"] = e2_home.loc[missing_date, "_odds_join_sw"].fillna(out.loc[missing_date, "_odds_join"])

    # Default price for spreads/totals if still missing
    needs_default = out["_odds_price"].isna() & out["_odds_market"].isin(["SPREADS","TOTALS"])
    out.loc[needs_default, "_odds_price"] = -110

    out["_joined_with_odds"] = out["_odds_book"].notna()

    # Keep useful columns tidy (but don’t drop user columns)
    # (Return full DF with new odds columns.)
    return out

# -------------------- convenience --------------------

def normalize_and_attach_odds(
    edges: pd.DataFrame,
    raw_odds: pd.DataFrame,
    prefer_books: list[str] | None = None
) -> pd.DataFrame:
    """
    Convenience wrapper: normalize raw odds then attach to edges.
    """
    odds_tidy = normalize_odds_lines(raw_odds)
    return attach_odds(edges, odds_tidy, prefer_books=prefer_books)

