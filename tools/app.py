import pandas as pd
import numpy as np
import os
import streamlit as st
from typing import Optional, Tuple

st.set_page_config(page_title="Backtest Dashboard", layout="wide")

# ----------------------------
# Odds helpers
# ----------------------------
def am_to_dec(am: Optional[float]) -> Optional[float]:
    try:
        x = float(am)
    except Exception:
        return None
    if x > 0: return 1.0 + x/100.0
    if x < 0: return 1.0 + 100.0/abs(x)
    return None

def american_profit(price: float, stake: float) -> float:
    dec = am_to_dec(price)
    if dec is None or pd.isna(stake): return np.nan
    return stake * (dec - 1.0)

def norm_market_series(s: pd.Series | None) -> pd.Series:
    if s is None: return pd.Series([], dtype="object")
    aliases = {
        "point spread": "spread",
        "spreads": "spread",
        "spread": "spread",
        "ml": "moneyline",
        "money line": "moneyline",
        "moneyline": "moneyline",
        "h2h": "moneyline",
        "totals": "total",
        "total": "total",
        "over/under": "total",
        "o/u": "total",
    }
    return (s.astype(str).str.strip().str.lower().replace(aliases))

# ----------------------------
# Data load
# ----------------------------
@st.cache_data
def load_graded() -> pd.DataFrame:
    path = "exports/edges_graded_plus.csv" if os.path.exists("exports/edges_graded_plus.csv") else "exports/edges_graded.csv"
    df = pd.read_csv(path, dtype=str, low_memory=False)

    for col in ["stake","price","line","result","league","season","week","market","side","game_id","status","home_team","away_team","game_date","parlay_id","ticket_id"]:
        if col not in df.columns: df[col] = pd.NA

    df["stake"]  = pd.to_numeric(df["stake"], errors="coerce").fillna(1.0)
    df["price"]  = pd.to_numeric(df["price"], errors="coerce")
    df["line"]   = pd.to_numeric(df["line"],  errors="coerce")
    df["result"] = df["result"].astype(str).str.strip().str.lower()
    df.loc[~df["result"].isin(["win","loss","push"]), "result"] = "na"

    df["market_norm"] = norm_market_series(df.get("market"))
    df["side_norm"]   = df.get("side","").astype(str).str.lower()
    df["league_norm"] = df.get("league","").astype(str).str.strip().str.lower()
    df["season_num"]  = pd.to_numeric(df.get("season"), errors="coerce")
    df["week_num"]    = pd.to_numeric(df.get("week"),   errors="coerce")
    return df

@st.cache_data
def load_odds_expected() -> Optional[pd.DataFrame]:
    try:
        ox = pd.read_csv("exports/historical_odds_expected.csv", dtype=str, low_memory=False)
        for c in ("ml_home","ml_away","spread_close","total_close"):
            if c in ox.columns: ox[c] = pd.to_numeric(ox[c], errors="coerce")
        return ox
    except FileNotFoundError:
        return None

# ----------------------------
# Enrichment (backfill odds/lines; compute per-leg profit)
# ----------------------------
def enrich(df: pd.DataFrame, oddsx: Optional[pd.DataFrame],
           assume_ml=-110, assume_sp=-110, assume_tot=-110) -> pd.DataFrame:
    f = df.copy()
    if f.empty: return f

    if "market_norm" not in f.columns:
        f["market_norm"] = norm_market_series(f.get("market"))
    if "side_norm" not in f.columns:
        f["side_norm"] = f.get("side","").astype(str).str.lower()

    if oddsx is not None and "game_id" in f.columns:
        f = f.merge(oddsx[["game_id","ml_home","ml_away","spread_close","total_close"]],
                    on="game_id", how="left")
    else:
        for c in ("ml_home","ml_away","spread_close","total_close"):
            if c not in f.columns: f[c] = pd.NA

    # price backfill
    ml_home = (f["market_norm"]=="moneyline") & (f["side_norm"]=="home")
    ml_away = (f["market_norm"]=="moneyline") & (f["side_norm"]=="away")
    f.loc[ml_home & f["price"].isna(), "price"] = f.loc[ml_home, "ml_home"]
    f.loc[ml_away & f["price"].isna(), "price"] = f.loc[ml_away, "ml_away"]

    # line backfill
    is_spread = f["market_norm"].eq("spread")
    is_total  = f["market_norm"].eq("total")
    f.loc[is_spread & f["line"].isna() & (f["side_norm"]=="home"), "line"] = f.loc[is_spread & (f["side_norm"]=="home"), "spread_close"]
    f.loc[is_spread & f["line"].isna() & (f["side_norm"]=="away"), "line"] = -f.loc[is_spread & (f["side_norm"]=="away"), "spread_close"]
    f.loc[is_total  & f["line"].isna(), "line"] = f.loc[is_total, "total_close"]

    # fallback juice
    f.loc[ml_home & f["price"].isna(), "price"] = assume_ml
    f.loc[ml_away & f["price"].isna(), "price"] = assume_ml
    f.loc[is_spread & f["price"].isna(),        "price"] = assume_sp
    f.loc[is_total  & f["price"].isna(),        "price"] = assume_tot

    # per-leg profit (robust: list-comp avoids DataFrame-apply edge case)
    def leg_profit(r):
        res = (r.get("result") or "").strip().lower()
        stake = float(r.get("stake") or 1.0)
        if res == "push": return 0.0
        if res not in ("win","loss"): return float("nan")
        dec = am_to_dec(r.get("price"))
        if dec is None: return float("nan")
        return stake*(dec-1.0) if res=="win" else -stake

    f["profit_units"] = [leg_profit(r) for _, r in f.iterrows()]
    return f

# ----------------------------
# Parlay math
# ----------------------------
def parlay_profit(group: pd.DataFrame) -> float:
    legs = group[group["result"].isin(["win","loss","push"])].copy()
    if len(legs) == 0: return 0.0
    if any(legs["result"].eq("loss")):
        if all(legs["result"].eq("push")): return 0.0
        return -float(legs["stake"].iloc[0] or 1.0)
    decs = []
    for _, r in legs.iterrows():
        if r["result"]=="push": continue
        d = am_to_dec(r.get("price"))
        if d is None: return float("nan")
        decs.append(d)
    if not decs: return 0.0
    stake = float(legs["stake"].iloc[0] or 1.0)
    dec_comb = 1.0
    for d in decs: dec_comb *= d
    return stake*(dec_comb-1.0)

def parlay_near_miss(group: pd.DataFrame) -> Tuple[bool, float, int, int, int, int]:
    legs = group[group["result"].isin(["win","loss","push"])].copy()
    if len(legs) < 2:
        return (False, 0.0, len(legs), int((legs["result"]=="win").sum()),
                int((legs["result"]=="loss").sum()), int((legs["result"]=="push").sum()))
    losses = int((legs["result"]=="loss").sum())
    if losses != 1:
        return (False, 0.0, len(legs), int((legs["result"]=="win").sum()),
                losses, int((legs["result"]=="push").sum()))
    decs = []
    for _, r in legs.iterrows():
        if r["result"]=="push": continue
        d = am_to_dec(r.get("price"))
        if d is None:
            return (True, float("nan"), len(legs), int((legs["result"]=="win").sum()),
                    losses, int((legs["result"]=="push").sum()))
        decs.append(d)
    if not decs: return (True, 0.0, len(legs), int((legs["result"]=="win").sum()),
                         losses, int((legs["result"]=="push").sum()))
    stake = float(legs["stake"].iloc[0] or 1.0)
    dec_comb = 1.0
    for d in decs: dec_comb *= d
    potential = stake*(dec_comb-1.0)
    return (True, potential, len(legs), int((legs["result"]=="win").sum()),
            losses, int((legs["result"]=="push").sum()))

# ----------------------------
# Sidebar (global)
# ----------------------------
df = load_graded()
oddsx = load_odds_expected()

st.sidebar.header("Assumptions")
assume_ml  = st.sidebar.number_input("Fallback ML price", value=-110, step=5, format="%d")
assume_sp  = st.sidebar.number_input("Fallback Spread price", value=-110, step=5, format="%d")
assume_tot = st.sidebar.number_input("Fallback Total price", value=-110, step=5, format="%d")
st.sidebar.button("🔃 Refresh data", on_click=st.cache_data.clear)

st.sidebar.header("Filters")
league_opts = sorted(x for x in df["league_norm"].dropna().unique() if x) or ["nfl"]
league_sel  = st.sidebar.selectbox("League", league_opts, index=0)
season_opts = sorted(df["season_num"].dropna().unique().tolist())
season_sel  = st.sidebar.multiselect("Season(s)", season_opts, default=(season_opts[-1:] if season_opts else []))
week_opts   = sorted(df["week_num"].dropna().unique().tolist())
week_sel    = st.sidebar.multiselect("Week(s)", week_opts, default=[])

market_opts = sorted([m for m in pd.unique(df["market_norm"].dropna()) if m])
preferred_defaults = [m for m in ["spread","moneyline","total"] if m in market_opts] or (market_opts[:1] if market_opts else [])
market_sel  = st.sidebar.multiselect("Market(s)", options=market_opts, default=preferred_defaults)

# base filtered frame
base = df.copy()
if league_sel: base = base[base["league_norm"]==league_sel]
if season_sel: base = base[base["season_num"].isin(season_sel)]
if week_sel:   base = base[base["week_num"].isin(week_sel)]
if market_sel: base = base[base["market_norm"].isin(market_sel)]

# Enrich once
enriched = enrich(base, oddsx, assume_ml, assume_sp, assume_tot)

# ----------------------------
# UI Tabs
# ----------------------------
tab_explore, tab_backtest, tab_walk, tab_predict = st.tabs(["Explore", "Backtest", "Walk-Forward", "Predict"])

# Explore
with tab_explore:
    played = enriched[enriched["result"].isin(["win","loss","push"])].copy()
    wl     = enriched[enriched["result"].isin(["win","loss"])].copy()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Bets graded", len(played))
    c2.metric("WL bets", len(wl))
    c3.metric("Win %", f"{(wl['result'].eq('win').mean()*100 if len(wl) else 0):.2f}%")
    c4.metric("Total units", f"{np.nansum(played['profit_units']):.2f}")

    st.subheader("Summary")
    cols = ["season","week","game_id","market","side","line","price","result","profit_units"]
    cols = [c for c in cols if c in played.columns]
    sort_cols = [c for c in ["season_num","week_num","season","week"] if c in played.columns]
    view = played.sort_values(by=sort_cols, na_position="last") if sort_cols else played
    st.dataframe(view[cols] if cols else view, use_container_width=True)

    st.subheader("Profit by Week")
    if {"season_num","week_num"}.issubset(played.columns):
        wk = (played.groupby(["season_num","week_num"], dropna=True)["profit_units"]
                     .sum().reset_index().sort_values(["season_num","week_num"]))
        wk["season_week"] = wk["season_num"].astype("Int64").astype(str) + "-W" + wk["week_num"].astype("Int64").astype(str)
        st.area_chart(wk.set_index("season_week")["profit_units"])

# Backtest
with tab_backtest:
    st.write("Run a historical backtest for a **specific season** and **week range**.")
    c1,c2,c3,c4 = st.columns(4)
    seasons_available = sorted(df["season_num"].dropna().unique().tolist()) or [2025]
    sel_season = c1.selectbox("Season", seasons_available, index=0)
    wmin = int(enriched[enriched["season_num"]==sel_season]["week_num"].min() or 1) if (enriched["season_num"]==sel_season).any() else 1
    wmax = int(enriched[enriched["season_num"]==sel_season]["week_num"].max() or 18) if (enriched["season_num"]==sel_season).any() else 18
    r_from = c2.number_input("Week from", min_value=1, max_value=99, value=wmin, step=1)
    r_to   = c3.number_input("Week to",   min_value=1, max_value=99, value=wmax, step=1)
    use_parlays = c4.toggle("Aggregate by parlay_id/ticket_id", value=False)
    show_near   = st.checkbox("Show near-miss parlays", value=True)

    window = enriched[(enriched["season_num"]==sel_season) & (enriched["week_num"].between(r_from, r_to, inclusive="both"))]
    if use_parlays and (("parlay_id" in window.columns) or ("ticket_id" in window.columns)):
        parlay_col = "parlay_id" if "parlay_id" in window.columns else "ticket_id"
        tix = window.groupby(parlay_col).apply(parlay_profit).reset_index(name="profit_units")
        lab = window.groupby(parlay_col).agg(season_num=("season_num","min"), week_num=("week_num","min")).reset_index()
        played = tix.merge(lab, on=parlay_col, how="left")
        st.metric("Tickets graded", len(played))
        st.metric("Total units", f"{np.nansum(played['profit_units']):.2f}")
        st.dataframe(played.sort_values(["season_num","week_num"]), use_container_width=True)
        if show_near:
            nm = window.groupby(parlay_col).apply(parlay_near_miss).apply(pd.Series).reset_index()
            nm.columns = [parlay_col,"near_miss","potential_units","legs","wins","losses","pushes"]
            near = nm[nm["near_miss"]==True].copy()
            st.subheader("Near-miss parlays")
            st.write(f"Count: **{len(near)}** | Potential units if 1 more leg won: **{near['potential_units'].sum():.2f}**")
            st.dataframe(near.sort_values("potential_units", ascending=False).head(100), use_container_width=True)
    else:
        played = window[window["result"].isin(["win","loss","push"])].copy()
        wl     = window[window["result"].isin(["win","loss"])].copy()
        st.metric("Bets graded", len(played))
        st.metric("Win %", f"{(wl['result'].eq('win').mean()*100 if len(wl) else 0):.2f}%")
        st.metric("Total units", f"{np.nansum(played['profit_units']):.2f}")
        cols = ["season","week","game_id","market","side","line","price","result","profit_units"]
        cols = [c for c in cols if c in played.columns]
        st.dataframe(played.sort_values(["season_num","week_num"])[cols] if cols else played, use_container_width=True)

# Walk-Forward
with tab_walk:
    st.write("Leakage-free walk-forward: for each week W, test week W using only data from weeks < W.")
    seasons_available = sorted(df["season_num"].dropna().unique().tolist()) or [2025]
    w_season = st.selectbox("Season (walk-forward)", seasons_available, index=0)
    sw1, sw2 = st.columns(2)
    wf_start = sw1.number_input("Start week", min_value=1, max_value=99, value=1, step=1)
    wf_end   = sw2.number_input("End week", min_value=1, max_value=99, value=int(df[df["season_num"]==w_season]["week_num"].max() or 18), step=1)

    wf_rows = []
    cum = 0.0
    weeks = sorted([int(w) for w in enriched[(enriched["season_num"]==w_season)]["week_num"].dropna().unique() if wf_start <= w <= wf_end])
    for wk in weeks:
        test = enriched[(enriched["season_num"]==w_season) & (enriched["week_num"]==wk) & (enriched["result"].isin(["win","loss","push"]))].copy()
        units = float(np.nansum(test["profit_units"]))
        winp  = float((test["result"].eq("win").mean()*100.0) if len(test) else 0.0)
        cum  += units
        wf_rows.append({"season":int(w_season),"week":wk,"bets":len(test),"win_pct":round(winp,2),"units":round(units,2),"cum_units":round(cum,2)})
    wf = pd.DataFrame(wf_rows)
    st.dataframe(wf, use_container_width=True)

# Predict (demo)
with tab_predict:
    st.write("Prediction sandbox (demo): for **non-final** games, show moneyline candidates using implied probability thresholds.")
    future = df.copy()
    if "status" in future.columns:
        future = future[future["status"].astype(str).str.lower() != "final"]
    else:
        future = future[future["result"].eq("na")]

    future = enrich(future, oddsx, assume_ml, assume_sp, assume_tot)
    future_ml = future[future["market_norm"]=="moneyline"].copy()
    if future_ml.empty:
        st.info("No future moneyline rows available.")
    else:
        def implied(price):
            try: p=float(price)
            except: return np.nan
            return 100/(p+100) if p>0 else abs(p)/(abs(p)+100)
        future_ml["implied_prob"] = future_ml["price"].apply(implied)
        th = st.slider("Min implied win probability to list (favorites)", 0.0, 1.0, 0.55, 0.01)
        show = future_ml[future_ml["implied_prob"]>=th].copy()
        cols = ["season","week","game_id","home_team","away_team","side","price","implied_prob"]
        cols = [c for c in cols if c in show.columns]
        st.dataframe(show.sort_values(["season_num","week_num"])[cols] if cols else show, use_container_width=True)

