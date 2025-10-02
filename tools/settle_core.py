# tools/settle_core.py
from __future__ import annotations

import numpy as np
import pandas as pd

# -------------------- helpers --------------------

def _s(x) -> pd.Series:
    """Return a pandas StringDtype Series with empty-string fill."""
    if isinstance(x, pd.Series):
        return x.astype("string").fillna("")
    return pd.Series([x], dtype="string")

def _num_series(df: pd.DataFrame, candidates: list[str], regex: str | None = None) -> pd.Series:
    """
    Pick the first numeric-looking column from candidates (or by regex on column name) and coerce to float.
    Returns a float Series aligned to df.index with NaN for missing.
    """
    if regex:
        for c in df.columns:
            if pd.Series([c]).str.contains(regex, case=False, regex=True).any():
                return pd.to_numeric(df[c], errors="coerce").reindex(df.index)
    for col in candidates:
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce").reindex(df.index)
    return pd.Series(np.nan, index=df.index, dtype="float64")

def _str_series(df: pd.DataFrame, candidates: list[str], regex: str | None = None) -> pd.Series:
    """
    Pick the first string-looking column from candidates (or by regex on column name).
    Returns StringDtype with empty strings for missing.
    """
    if regex:
        for c in df.columns:
            if pd.Series([c]).str.contains(regex, case=False, regex=True).any():
                return _s(df[c]).reindex(df.index)
    for col in candidates:
        if col in df.columns:
            return _s(df[col]).reindex(df.index)
    return pd.Series([""] * len(df), index=df.index, dtype="string")

def _nickify(series: pd.Series) -> pd.Series:
    """Uppercase, strip punctuation, collapse spaces, and apply a few NFL aliases."""
    alias = {
        "REDSKINS": "COMMANDERS", "WASHINGTON": "COMMANDERS", "FOOTBALL": "COMMANDERS",
        "OAKLAND": "RAIDERS", "LV": "RAIDERS", "LAS": "RAIDERS", "VEGAS": "RAIDERS",
        "SD": "CHARGERS", "LA": "RAMS", "STL": "RAMS",
    }
    s = _s(series).str.upper().str.replace(r"[^A-Z0-9 ]+", "", regex=True).str.strip().replace(alias)
    return s.str.replace(r"\s+", "_", regex=True)

def _nick_core(s: pd.Series) -> pd.Series:
    """Return nickname token (last segment), e.g., SAN_FRANCISCO_49ERS -> 49ERS."""
    return _s(s).str.split("_").str[-1]

def _market_norm(s: pd.Series | str) -> pd.Series:
    """Normalize common market names to {H2H, SPREADS, TOTALS}."""
    s = _s(s).str.upper().str.replace(r"\s+", "", regex=True)
    return s.replace({
        "MONEYLINE": "H2H", "ML": "H2H",
        "POINTSPREAD": "SPREADS", "SPREAD": "SPREADS", "ATS": "SPREADS",
        "TOTALSPOINTS": "TOTALS", "TOTALS": "TOTALS", "TOTAL": "TOTALS",
        "OU": "TOTALS", "O/U": "TOTALS",
        "": "",
    })

def _p_to_american(p: pd.Series) -> pd.Series:
    """Convert win prob (0–1) to American odds."""
    p = pd.to_numeric(p, errors="coerce").clip(1e-6, 1.0 - 1e-6)
    return np.where(p >= 0.5, -100.0 * (p / (1.0 - p)), 100.0 * ((1.0 - p) / p))

def _winner_series(hs: pd.Series, as_: pd.Series, home: pd.Series, away: pd.Series) -> pd.Series:
    """Safe game winner: resolves NA booleans by filling with False."""
    gt = (hs > as_).fillna(False)
    lt = (as_ > hs).fillna(False)
    win = np.where(gt, home, np.where(lt, away, ""))
    return _s(pd.Series(win, index=home.index))

def _pick_team_series(d: pd.DataFrame) -> pd.Series:
    """
    Derive _pick_nick (team picked) when missing:
      - If present, use it.
      - Else, if side equals home/away nick -> map to that team (SPREADS/H2H).
      - Else, for H2H if p_win present, derive by orientation vs winners.
      - Totals return "" (OVER/UNDER is teamless).
    """
    if "_pick_nick" in d.columns and not d["_pick_nick"].isna().all():
        return _s(d["_pick_nick"])

    home = _str_series(d, ["_home_nick", "home_team", "HomeTeam"])
    away = _str_series(d, ["_away_nick", "away_team", "AwayTeam"])
    side_raw = _str_series(d, ["side"]).str.upper()
    market = _market_norm(_str_series(d, ["market"]))

    # Map textual team in side to HOME/AWAY
    side_mapped = side_raw.copy()
    side_mapped = np.where(side_raw == _s(home).str.upper(), "HOME", side_mapped)
    side_mapped = np.where(side_raw == _s(away).str.upper(), "AWAY", side_mapped)
    side_mapped = pd.Series(side_mapped, index=d.index, dtype="string")

    pick = pd.Series([""] * len(d), index=d.index, dtype="string")

    # SPREADS: pick team by HOME/AWAY
    is_spread = market.eq("SPREADS")
    pick.loc[is_spread & side_mapped.eq("HOME")] = home[is_spread & side_mapped.eq("HOME")]
    pick.loc[is_spread & side_mapped.eq("AWAY")] = away[is_spread & side_mapped.eq("AWAY")]

    # H2H: if side already names a team, use it; else derive from p_win orientation
    is_ml = market.eq("H2H")
    if is_ml.any():
        eq_home = side_raw.eq(_s(home).str.upper())
        eq_away = side_raw.eq(_s(away).str.upper())
        pick.loc[is_ml & eq_home] = home[is_ml & eq_home]
        pick.loc[is_ml & eq_away] = away[is_ml & eq_away]

        need = is_ml & pick.eq("")
        if need.any() and "p_win" in d.columns:
            p = pd.to_numeric(d.loc[need, "p_win"], errors="coerce")
            home_ml = home[need]; away_ml = away[need]

            # Orientation by comparing to actual winners (when known)
            hs = _num_series(d, ["home_score", "HomeScore"])
            as_ = _num_series(d, ["away_score", "AwayScore"])
            winner = _winner_series(hs, as_, home, away)

            known = winner[need].ne("")
            base_pick = np.where(p >= 0.5, home_ml, away_ml)  # assume p = home prob
            alt_pick  = np.where(p >= 0.5, away_ml, home_ml)  # assume p = away prob
            if known.any():
                base_acc = (pd.Series(base_pick, index=home_ml.index)[known] == winner[need][known]).mean()
                alt_acc  = (pd.Series(alt_pick,  index=home_ml.index)[known] == winner[need][known]).mean()
                chosen = alt_pick if (alt_acc > base_acc + 1e-9) else base_pick
            else:
                chosen = base_pick
            pick.loc[need] = pd.Series(chosen, index=home_ml.index)

    # TOTALS: stays empty (teamless)
    return pick.fillna("")

# -------------------- settlement --------------------

def settle_bets(
    df: pd.DataFrame,
    assume_ml_price: str = "even",     # "even" | "pwin" | "none"
    st_default_price: float | None = -110.0,
    odds_coverage_starts: int = 2006
) -> pd.DataFrame:
    """
    Grade bets and compute profit per $1.
    - H2H: settles by winner; price can be estimated from p_win if missing (assume_ml_price).
    - SPREADS/TOTALS: settles by line; default price applied if missing (st_default_price).
    - Seasons < odds_coverage_starts are flagged PRE_COVERAGE; missing ST lines are VOID.
    """
    d = df.copy()

    # Normalize identifiers and keys (tolerant to different schemas)
    d["market_norm"] = _market_norm(_str_series(d, ["market"]))
    if "_home_nick" not in d.columns or d["_home_nick"].isna().all():
        d["_home_nick"] = _nickify(_str_series(d, ["home_team", "HomeTeam"]))
    if "_away_nick" not in d.columns or d["_away_nick"].isna().all():
        d["_away_nick"] = _nickify(_str_series(d, ["away_team", "AwayTeam"]))

    d["_pick_nick"]  = _pick_team_series(d)

    hs    = _num_series(d, ["home_score", "HomeScore"])
    as_   = _num_series(d, ["away_score", "AwayScore"])
    line  = _num_series(d, ["line", "handicap", "spread", "total", "Line", "Handicap", "Spread", "Total"])
    price = _num_series(d, ["price", "odds", "Price", "Odds"])

    home  = _str_series(d, ["_home_nick", "home_team", "HomeTeam"])
    away  = _str_series(d, ["_away_nick", "away_team", "AwayTeam"])
    side  = _str_series(d, ["side"]).str.upper()

    # Season numeric to determine coverage
    season_num = pd.to_numeric(_str_series(d, ["_season", "season"]), errors="coerce")
    pre_cov = season_num < odds_coverage_starts

    # --- winners (NA-safe) ---
    winner = _winner_series(hs, as_, home, away)

    # --- result container ---
    result = pd.Series(["VOID"] * len(d), index=d.index, dtype="string")

    # ===== H2H =====
    is_ml = d["market_norm"].eq("H2H")
    if is_ml.any():
        pick_ml = d.loc[is_ml, "_pick_nick"].copy()
        # derive pick if missing via p_win orientation
        need_pick = pick_ml.eq("")
        if need_pick.any() and "p_win" in d.columns:
            p = pd.to_numeric(d.loc[is_ml, "p_win"], errors="coerce")
            home_ml = home[is_ml]; away_ml = away[is_ml]
            win_ml  = winner[is_ml]
            known = win_ml.ne("")
            base_pick = np.where(p >= 0.5, home_ml, away_ml)
            alt_pick  = np.where(p >= 0.5, away_ml, home_ml)
            if known.any():
                base_acc = (pd.Series(base_pick, index=pick_ml.index)[known] == win_ml[known]).mean()
                alt_acc  = (pd.Series(alt_pick,  index=pick_ml.index)[known] == win_ml[known]).mean()
                chosen = alt_pick if (alt_acc > base_acc + 1e-9) else base_pick
            else:
                chosen = base_pick
            pick_ml[need_pick] = pd.Series(chosen, index=pick_ml.index)[need_pick]

        win_ml = winner[is_ml]
        r = np.where(pick_ml.eq(""), "VOID",
            np.where(win_ml.eq(""), "PUSH",
            np.where(pick_ml.eq(win_ml), "WIN", "LOSE")))
        result.loc[is_ml] = r

    # ===== SPREADS =====
    is_spread = d["market_norm"].eq("SPREADS")
    if is_spread.any():
        # map side textual team -> HOME/AWAY
        side_mapped = side.copy()
        side_mapped = np.where(side == _s(home).str.upper(), "HOME", side_mapped)
        side_mapped = np.where(side == _s(away).str.upper(), "AWAY", side_mapped)
        side_mapped = pd.Series(side_mapped, index=d.index, dtype="string")

        sp = d.loc[is_spread].copy()
        margin = (hs - as_)[is_spread]
        ln = line[is_spread]
        pick_team = sp["_pick_nick"].copy()
        # If no _pick_nick, infer from side HOME/AWAY
        need_pick = pick_team.eq("")
        pick_team.loc[need_pick & side_mapped[is_spread].eq("HOME")] = home[is_spread][need_pick & side_mapped[is_spread].eq("HOME")]
        pick_team.loc[need_pick & side_mapped[is_spread].eq("AWAY")] = away[is_spread][need_pick & side_mapped[is_spread].eq("AWAY")]

        # picked line flips if away
        pick_line = ln.copy()
        pick_line.loc[pick_team == away[is_spread]] = -pick_line.loc[pick_team == away[is_spread]]

        missing = ln.isna() | pick_team.eq("")
        gt = (margin > pick_line).fillna(False)
        lt = (margin < pick_line).fillna(False)
        r = np.where(missing, "VOID", np.where(gt, "WIN", np.where(lt, "LOSE", "PUSH")))
        result.loc[is_spread] = r

    # ===== TOTALS =====
    is_totals = d["market_norm"].eq("TOTALS")
    if is_totals.any():
        total_pts = (hs + as_)[is_totals]
        ln = line[is_totals]
        sd = side[is_totals]
        missing = ln.isna() | ~sd.isin(["OVER","UNDER"])
        push_mask = (total_pts == ln).fillna(False)
        over_win  = (sd.eq("OVER")  & (total_pts > ln).fillna(False))
        under_win = (sd.eq("UNDER") & (total_pts < ln).fillna(False))
        win_mask  = over_win | under_win
        r = np.where(missing, "VOID", np.where(push_mask, "PUSH", np.where(win_mask, "WIN", "LOSE")))
        result.loc[is_totals] = r

    d["_result"] = result

    # ===== Pricing assumptions =====
    # Default price for SPREADS/TOTALS if missing (e.g., -110)
    if st_default_price is not None:
        st_mask = d["market_norm"].isin(["SPREADS","TOTALS"]) & price.isna()
        if st_mask.any():
            price.loc[st_mask] = float(st_default_price)

    # H2H price estimation from p_win (or pick'em), when missing
    need_ml_price = d["market_norm"].eq("H2H") & price.isna()
    if need_ml_price.any():
        if assume_ml_price == "even":
            price.loc[need_ml_price] = 100.0  # +100
        elif assume_ml_price == "pwin" and "p_win" in d.columns:
            price.loc[need_ml_price] = _p_to_american(d.loc[need_ml_price, "p_win"])
        # "none": leave NaN → payout treats as 0

    # If pre-coverage and SPREADS/TOTALS have no line -> force VOID
    precov_st = pre_cov & d["market_norm"].isin(["SPREADS","TOTALS"]) & line.isna()
    if precov_st.any():
        d.loc[precov_st, "_result"] = "VOID"

    # ===== Profit per $1 =====
    price_clean = price.fillna(0.0)
    payout = np.where(
        price_clean >= 100.0, price_clean / 100.0,
        np.where(price_clean < 0.0, 100.0 / np.abs(price_clean), 0.0)
    )
    d["_profit_per_$1"] = np.where(d["_result"].eq("WIN"), payout,
                            np.where(d["_result"].eq("LOSE"), -1.0, 0.0)).astype(float)

    # Flags for diagnostics
    d["_has_line"]  = ~line.isna()
    d["_has_price"] = ~price.isna()
    d["_coverage_scope"] = np.where(pre_cov, "PRE_COVERAGE", "FULL")

    return d

# -------------------- metrics & filters --------------------

def filter_by_season_week(df: pd.DataFrame, season: str | int = "All", week: str | int = "All Weeks") -> pd.DataFrame:
    """
    Filter dataframe by season and week, tolerant to formats like '1', '01', 'Week 1'.
    Looks for `_season`/`_week` first, falls back to `season`/`week`/`Week`.
    """
    d = df.copy()

    # Canonical season as 4 digits if possible
    seas_src = d.get("_season", d.get("season", ""))
    seas = _s(seas_src).str.extract(r"(\d{4})", expand=False).fillna("")
    d["_season"] = seas

    # Canonical week as digits (1..)
    wk_src = d.get("_week", d.get("week", d.get("Week", "")))
    wk = _s(wk_src).str.extract(r"(\d+)", expand=False).fillna("")
    d["_week"] = wk

    if season != "All":
        d = d[d["_season"] == str(season)]
    if week != "All Weeks":
        d = d[d["_week"] == str(week)]
    return d

def metrics_by_market(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate bet results by normalized market."""
    if df.empty:
        return pd.DataFrame(columns=["market","bets","wins","losses","pushes","profit","roi_per_bet"])
    d = df.copy()
    d["market_norm"] = _market_norm(d.get("market", pd.Series([""] * len(d))))
    grp = d.groupby("market_norm", dropna=False)
    bets   = grp.size().rename("bets")
    counts = grp["_result"].value_counts().unstack(fill_value=0)
    for k in ("WIN","LOSE","PUSH"):
        if k not in counts.columns:
            counts[k] = 0
    profit = grp["_profit_per_$1"].sum(min_count=1).rename("profit")
    roi    = grp["_profit_per_$1"].mean().rename("roi_per_bet")
    out = pd.concat([bets, counts["WIN"], counts["LOSE"], counts["PUSH"], profit, roi], axis=1)
    out.columns = ["bets","wins","losses","pushes","profit","roi_per_bet"]
    return out.reset_index().rename(columns={"market_norm":"market"}).fillna(0)

def metrics_by_team(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate by picked team (team-level performance of your bets)."""
    if df.empty:
        return pd.DataFrame(columns=["team","bets","wins","losses","pushes","profit","roi_per_bet"])
    t = df.copy()
    if "_pick_nick" not in t.columns or t["_pick_nick"].isna().all():
        t["_pick_nick"] = t.get("_pick_team", "").astype("string")
    t["team"] = _s(t["_pick_nick"])
    t["is_win"]  = t["_result"].eq("WIN")
    t["is_loss"] = t["_result"].eq("LOSE")
    t["is_push"] = t["_result"].eq("PUSH")
    g = t.groupby("team", dropna=False).agg(
        bets=("team","size"),
        wins=("is_win","sum"),
        losses=("is_loss","sum"),
        pushes=("is_push","sum"),
        profit=("_profit_per_$1","sum"),
        roi_per_bet=("_profit_per_$1","mean"),
    ).reset_index()
    return g.sort_values(["profit","wins"], ascending=[False, False]).fillna(0)

