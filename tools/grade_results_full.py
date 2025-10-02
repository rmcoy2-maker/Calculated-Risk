# grade_results_full.py — with fallback lines & minimal odds
import math, numpy as np, pandas as pd
from typing import Optional

# ---------- paths / config ----------
EDGES  = r"C:\Projects\edge-finder\exports\edges_graded_wlp.csv"
SCORES = r"C:\Projects\edge-finder\exports\scores.csv"
OUT    = r"C:\Projects\edge-finder\exports\edges_graded_full.csv"
TEAM_SUMMARY_OUT = r"C:\Projects\edge-finder\exports\breakdown_teams.csv"

DEFAULT_STAKE = 1.0
# Minimal/conservative American odds when missing (typical spread/total juice)
DEFAULT_AMERICAN_ODDS = -110.0

# ---------- helpers ----------
def N(s):
    try: return ("" if s is None else str(s)).strip().upper()
    except: return ""

def L(s):
    try: return ("" if s is None else str(s)).strip().lower()
    except: return ""

def F(x):
    try: return float(x)
    except Exception: return float("nan")

ABBR_TO_NICK = {
    "ARI":"CARDINALS","ATL":"FALCONS","CAR":"PANTHERS","CHI":"BEARS","DAL":"COWBOYS","DET":"LIONS",
    "GB":"PACKERS","LAR":"RAMS","LA":"RAMS","MIN":"VIKINGS","NO":"SAINTS","NYG":"GIANTS",
    "PHI":"EAGLES","SEA":"SEAHAWKS","SF":"49ERS","TB":"BUCCANEERS","TAM":"BUCCANEERS",
    "WAS":"COMMANDERS","WSH":"COMMANDERS","WFT":"COMMANDERS","STL":"RAMS",
    "BAL":"RAVENS","BUF":"BILLS","CIN":"BENGALS","CLE":"BROWNS","DEN":"BRONCOS","HOU":"TEXANS",
    "IND":"COLTS","JAX":"JAGUARS","JAC":"JAGUARS","KC":"CHIEFS","LAC":"CHARGERS","LV":"RAIDERS",
    "MIA":"DOLPHINS","NE":"PATRIOTS","NYJ":"JETS","PIT":"STEELERS","TEN":"TITANS",
    "OAK":"RAIDERS","SD":"CHARGERS","BOS":"PATRIOTS"
}
NICK_ALIAS = {
    "REDSKINS":"COMMANDERS","FOOTBALL":"COMMANDERS","TEAM":"COMMANDERS","OILERS":"TITANS",
    "JAGUAR":"JAGUARS","BUCCANEER":"BUCCANEERS"
}

def nickname_from_full(team: str) -> str:
    s = N(team).replace(".", " ").replace("-", " ")
    s = " ".join(s.split())
    if not s: return ""
    parts = s.split(" ")
    nick = parts[-1] if parts else ""
    if nick == "TEAM" and len(parts) >= 2 and parts[-2] == "FOOTBALL":
        nick = "COMMANDERS"
    return NICK_ALIAS.get(nick, nick)

def nickname_any(s: str) -> str:
    s = N(s)
    if not s: return ""
    if len(s) <= 3 and s in ABBR_TO_NICK:
        return ABBR_TO_NICK[s]
    return NICK_ALIAS.get(nickname_from_full(s), nickname_from_full(s))

def norm_market(m: str) -> str:
    m = L(m)
    if m in ("moneyline","h2h"): return "moneyline"
    if m in ("spread","spreads"): return "spread"
    if m in ("total","totals","o/u","over/under"): return "total"
    return m or ""

def american_profit(odds_val, stake: float) -> Optional[float]:
    try:
        o = float(str(odds_val))
    except Exception:
        return None
    if math.isnan(o): return None
    if o > 0:  return stake * (o / 100.0)
    if o < 0:  return stake * (100.0 / abs(o))
    return None

def first_non_null_float(row, cols):
    for c in cols:
        try:
            v = float(row.get(c))
            if not math.isnan(v): return v
        except: pass
    return float("nan")

# ---------- load ----------
edges  = pd.read_csv(EDGES, low_memory=False)
scores = pd.read_csv(SCORES, low_memory=False)

for df in (edges, scores):
    for c in ("season","home","away","team_home","team_away","hometeam","awayteam",
              "home_team_g","away_team_g","_home_abbr_norm","_away_abbr_norm",
              "side","selection","market","line","_ref_line","over_under_line","_tot_line","_tot_side",
              "odds","stake","staked","result","result_norm","bet_id","slip_id"):
        if c in df.columns: df[c] = df[c].astype(str)

# ---------- market normalization for UI (_market_norm2) ----------
edges["_market_norm2"] = edges["market"].apply(norm_market)

# ---------- build keys + merge scores ----------
def pick_home(r):
    for c in ("_home_abbr_norm","home","team_home","hometeam","home_team_g"):
        if c in r and N(r[c]): return N(r[c])
    return ""

def pick_away(r):
    for c in ("_away_abbr_norm","away","team_away","awayteam","away_team_g"):
        if c in r and N(r[c]): return N(r[c])
    return ""

E = edges.copy()
E["SEASON"]   = E["season"].astype(str).str.extract(r"(\d{4})", expand=False).fillna(E["season"].astype(str))
E["HOME_RAW"] = E.apply(pick_home, axis=1)
E["AWAY_RAW"] = E.apply(pick_away, axis=1)
E["HOME_NK"]  = E["HOME_RAW"].apply(nickname_any)
E["AWAY_NK"]  = E["AWAY_RAW"].apply(nickname_any)
E["SIDE_RAW"] = E.apply(lambda r: N(r.get("side") or r.get("selection")), axis=1)
E["SIDE_NK"]  = E["SIDE_RAW"].apply(nickname_any)
E["MKT_RAW"]  = E["market"].astype(str).str.lower()
E["MKT"]      = E["MKT_RAW"].apply(norm_market)

S = scores.copy()
S["SEASON"]  = S["season"].astype(str).str.extract(r"(\d{4})", expand=False).fillna(S["season"].astype(str))
S["HOME_NK"] = S["home"].astype(str).apply(nickname_any)
S["AWAY_NK"] = S["away"].astype(str).apply(nickname_any)

keep = ["SEASON","home_score","away_score","HOME_NK","AWAY_NK"]
m1 = E.merge(S[keep], on=["SEASON","HOME_NK","AWAY_NK"], how="left")
m2 = E.merge(S[keep], left_on=["SEASON","AWAY_NK","HOME_NK"], right_on=["SEASON","HOME_NK","AWAY_NK"], how="left", suffixes=("","_sw"))
E["home_score"] = m1["home_score"].combine_first(m2["home_score"])
E["away_score"] = m1["away_score"].combine_first(m2["away_score"])

with_scores = int(E["home_score"].notna().sum())
print(f"[diag] rows={len(E)} with_scores={with_scores}")

# ---------- diagnostics for ML ----------
is_ml           = E["MKT"].eq("moneyline")
ml_total        = int(is_ml.sum())
ml_with_side    = int((is_ml & E["SIDE_RAW"].ne("")).sum())
ml_with_scores  = int((is_ml & E["home_score"].notna()).sum())
ml_side_is_home = int((is_ml & (E["SIDE_NK"]==E["HOME_NK"])).sum())
ml_side_is_away = int((is_ml & (E["SIDE_NK"]==E["AWAY_NK"])).sum())
print(f"[diag-ml] total={ml_total} with_side={ml_with_side} with_scores={ml_with_scores} side=home_matches={ml_side_is_home} side=away_matches={ml_side_is_away}")

# ---------- fallback lines & odds (scoped by market) ----------
E["spread_line_filled"]  = np.nan
E["total_line_filled"]   = np.nan
E["default_spread_line"] = False
E["default_total_line"]  = False

# SPREAD: prefer real line; else default to -2.5 on the bet side (avoids pushes)
ms = E["MKT"].eq("spread")
E.loc[ms, "spread_line_filled"] = E.loc[ms].apply(
    lambda r: first_non_null_float(r, ["line","_ref_line"]), axis=1
)
need_spread = ms & E["spread_line_filled"].isna()

# We don’t know the true favorite, so give *the selected side* a small fave line.
# Our grader uses:
#   - home side: margin = h - a + line
#   - away side: margin = a - h + line
# Setting line = -2.5 means “your team -2.5”, which avoids pushes but keeps it realistic.
E.loc[need_spread, "spread_line_filled"]  = -2.5
E.loc[need_spread, "default_spread_line"] = True

# TOTAL: prefer real line; else default to a league-average (no auto-push)
mt = E["MKT"].eq("total")
E.loc[mt, "total_line_filled"] = E.loc[mt].apply(
    lambda r: first_non_null_float(r, ["over_under_line","_tot_line","line"]), axis=1
)
need_total = mt & E["total_line_filled"].isna()
E.loc[need_total, "total_line_filled"]  = 44.5  # baseline NFL total
E.loc[need_total, "default_total_line"] = True

# Odds: prefer real; else default to -110 (conservative)
def odds_of(r):
    try:
        o = float(r.get("odds"))
        if not math.isnan(o): return o, False
    except: pass
    return float(DEFAULT_AMERICAN_ODDS), True

oddf = E.apply(odds_of, axis=1, result_type="expand")
E["odds_filled"]  = oddf[0]
E["default_odds"] = oddf[1].astype(bool)


# ---------- grading ----------
def grade_row(r):
    mkt = L(r.get("MKT"))
    h, a = F(r.get("home_score")), F(r.get("away_score"))
    if math.isnan(h) or math.isnan(a):
        return None

    # Moneyline
    if mkt == "moneyline":
        side_nk, home_nk, away_nk = N(r.get("SIDE_NK")), N(r.get("HOME_NK")), N(r.get("AWAY_NK"))
        def matches(x, y): return x == y or x.startswith(y) or y.startswith(x)
        if matches(side_nk, home_nk):
            return "win" if h > a else "loss" if a > h else "push"
        if matches(side_nk, away_nk):
            return "win" if a > h else "loss" if h > a else "push"
        return None

    # Spread (ATS) — use filled line (may be 0 default)
    if mkt == "spread":
        ln = F(r.get("spread_line_filled"))
        if math.isnan(ln): return None
        side_nk, home_nk, away_nk = N(r.get("SIDE_NK")), N(r.get("HOME_NK")), N(r.get("AWAY_NK"))
        if side_nk == home_nk:
            margin = h - a + ln
        elif side_nk == away_nk:
            margin = a - h + ln
        else:
            return None
        return "win" if margin > 0 else "loss" if margin < 0 else "push"

    # Total (O/U) — use filled line (may be game total default)
    if mkt == "total":
        ln = F(r.get("total_line_filled"))
        if math.isnan(ln): return None
        pts  = h + a
        side = L(r.get("_tot_side") or r.get("side"))
        if side == "over":
            return "win" if pts > ln else "loss" if pts < ln else "push"
        if side == "under":
            return "win" if pts < ln else "loss" if pts > ln else "push"
        return None

    return None

E["result"] = E.apply(grade_row, axis=1)
E["result_norm"] = E["result"].where(E["result"].isin(["win","loss","push"]), other=np.nan)
E["settled_bool"] = E["result_norm"].isin(["win","loss","push"])

# ---------- stake & profit ----------
def stake_of(r):
    for c in ("stake","staked"):
        if c in r and str(r[c]).strip()!="":
            try:
                v = float(r[c])
                if not math.isnan(v): return v
            except: pass
    return DEFAULT_STAKE

def leg_profit(r):
    res = r.get("result_norm")
    st  = stake_of(r)
    if res == "win":
        ap = american_profit(r.get("odds_filled"), st)
        return 0.0 if ap is None else ap
    if res == "loss":
        return -st
    return 0.0  # push or not graded

E["stake"]  = [stake_of(r) for _, r in E.iterrows()]
E["profit"] = [leg_profit(r) for _, r in E.iterrows()]

# ---------- team breakdown ----------
def pick_team_bucket(r):
    m = L(r.get("MKT"))
    if m in ("moneyline","spread"):
        t = N(r.get("SIDE_NK"))
        return t if t else "(UNKNOWN_TEAM)"
    if m == "total":
        s = L(r.get("_tot_side") or r.get("side"))
        if s in ("over","under"):
            return s.upper()
        return "(TOTAL)"
    return "(OTHER)"

E["team_bucket"] = [pick_team_bucket(r) for _, r in E.iterrows()]
res = E["result_norm"].fillna("")
team_gp = (E
    .assign(win=(res=="win").astype(int),
            loss=(res=="loss").astype(int),
            push=(res=="push").astype(int))
    .groupby("team_bucket", dropna=False)
    .agg(bets=("team_bucket","size"),
         wins=("win","sum"),
         losses=("loss","sum"),
         pushes=("push","sum"),
         profit=("profit","sum"))
    .reset_index())
team_gp["hit%"] = (team_gp["wins"] / team_gp["bets"] * 100.0).round(2)
team_gp = team_gp.sort_values(["profit","hit%","bets"], ascending=[False, False, False])
team_gp.to_csv(TEAM_SUMMARY_OUT, index=False)

# ---------- write output ----------
# Keep _market_norm2; include flags for transparency
drop_helpers = ["SEASON","HOME_RAW","AWAY_RAW","MKT_RAW"]
E_out = E.drop(columns=[c for c in drop_helpers if c in E.columns], errors="ignore")
E_out.to_csv(OUT, index=False)

graded = int(E_out["settled_bool"].sum()) if "settled_bool" in E_out.columns else 0
wins   = int((E_out.get("result_norm")=="win").sum())
losses = int((E_out.get("result_norm")=="loss").sum())
pushes = int((E_out.get("result_norm")=="push").sum())
print(f"[ok] wrote {OUT}")
print(f"[summary] rows={len(E_out)} graded={graded}  win={wins} loss={losses} push={pushes}")
print(f"[ok] team breakdown -> {TEAM_SUMMARY_OUT}")
print("[note] default flags: default_spread_line, default_total_line, default_odds (True/False)")

