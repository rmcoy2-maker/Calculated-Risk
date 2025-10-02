from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

# Simple, robust settlement logic:
# - expects edges having _date_iso, _home_nick, _away_nick, market_norm, side_norm, line, price
# - expects scores with HomeScore, AwayScore, and same nicknames used by your join (already normalized upstream)
# - returns a DataFrame with a bit of metadata and win/loss/push result

def _as_s(x): return pd.Series(x, dtype="string") if not isinstance(x, pd.Series) else x.astype("string")

def _result_from_scores(row):
    m, side = (row.get("market_norm","") or "").upper(), (row.get("side_norm","") or "").upper()
    hs, as_ = row.get("HomeScore"), row.get("AwayScore")
    try:
        hs = float(hs); as_ = float(as_)
    except Exception:
        return "UNKNOWN"
    # moneyline
    if m == "H2H":
        if hs > as_: return "WIN" if side=="HOME" else "LOSS"
        if hs < as_: return "WIN" if side=="AWAY" else "LOSS"
        return "PUSH"
    # spreads; line > 0 means underdog gets points
    if m == "SPREADS":
        ln = row.get("line")
        try: ln = float(ln)
        except Exception: return "UNKNOWN"
        margin = hs - as_
        # home covers if margin > -line (because away got +line)
        if side == "HOME":
            if margin > -ln: return "WIN"
            if margin == -ln: return "PUSH"
            return "LOSS"
        if side == "AWAY":
            if -margin > ln: return "WIN"
            if -margin == ln: return "PUSH"
            return "LOSS"
        return "UNKNOWN"
    # totals
    if m == "TOTALS":
        ln = row.get("line")
        try: ln = float(ln)
        except Exception: return "UNKNOWN"
        tot = hs + as_
        if side == "OVER":
            if tot > ln: return "WIN"
            if tot == ln: return "PUSH"
            return "LOSS"
        if side == "UNDER":
            if tot < ln: return "WIN"
            if tot == ln: return "PUSH"
            return "LOSS"
        return "UNKNOWN"
    return "UNKNOWN"

def settle_bets(edges: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    e = edges.copy()
    s = scores.copy()

    # tolerate different score column casings
    for cand in (("HomeScore","AwayScore"), ("home_score","away_score"), ("homescore","awayscore")):
        if cand[0] in s.columns and cand[1] in s.columns:
            s = s.rename(columns={cand[0]:"HomeScore", cand[1]:"AwayScore"})
            break

    # required columns checks (soft)
    req_e = ["_date_iso","_home_nick","_away_nick","market_norm","side_norm"]
    for c in req_e:
        if c not in e.columns:
            e[c] = pd.NA

    # primary join key: date + teams
    e["_key_home"] = _as_s(e["_home_nick"]) + "|" + _as_s(e["_date_iso"])
    e["_key_away"] = _as_s(e["_away_nick"]) + "|" + _as_s(e["_date_iso"])
    s["_key_home"] = _as_s(s.get("_home_nick", "")) + "|" + _as_s(s.get("_date_iso", s.get("DateISO","")))
    s["_key_away"] = _as_s(s.get("_away_nick", "")) + "|" + _as_s(s.get("_date_iso", s.get("DateISO","")))

    # join both directions and coalesce
    hmap = s.set_index(["_key_home"])[["HomeScore","AwayScore"]].rename(columns={"HomeScore":"hs_h","AwayScore":"as_h"})
    amap = s.set_index(["_key_away"])[["HomeScore","AwayScore"]].rename(columns={"HomeScore":"hs_a","AwayScore":"as_a"})
    e = e.join(hmap, on="_key_home", how="left").join(amap, on="_key_away", how="left")
    e["HomeScore"] = e["hs_h"].combine_first(e["hs_a"])
    e["AwayScore"] = e["as_h"].combine_first(e["as_a"])
    e.drop(columns=[c for c in ("hs_h","as_h","hs_a","as_a") if c in e.columns], inplace=True)

    # compute result
    e["_settle_result"] = e.apply(_result_from_scores, axis=1)

    # implied return (american odds price) – if present
    def _ret(row):
        p = row.get("price")
        try: p = float(p)
        except Exception: return np.nan
        if p > 0:  # +150 -> 1.5 profit per 1
            return p/100.0
        else:     # -150 -> 0.666 profit per 1 if win
            return 100.0/abs(p)
    e["_unit_profit"] = e.apply(lambda r: (_ret(r) if r["_settle_result"]=="WIN" else (0.0 if r["_settle_result"]=="PUSH" else -1.0)), axis=1)

    return e

