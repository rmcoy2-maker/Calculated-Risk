from __future__ import annotations
import pandas as pd
from tools.io_utils import read_csv, to_int, to_float, norm_team


FILL_COLS = ["season","week","league","game_date","home_team","away_team","home_score","away_score","status","game_id"]

def norm_date_str(s: pd.Series) -> pd.Series:
    dt = pd.to_datetime(s, errors="coerce")
    out = dt.dt.strftime("%Y-%m-%d")
    return out.fillna("")

def build_keys(df: pd.DataFrame) -> pd.DataFrame:
    # numeric
    if "season" in df: df["season"] = to_int(df["season"])
    if "week"   in df: df["week"]   = to_int(df["week"])

    # teams
    for c in ("home_team","away_team"):
        if c in df.columns: df[c] = df[c].map(norm_team)

    # team_key (away@home) as string
    away = df.get("away_team")
    home = df.get("home_team")
    if away is not None and home is not None:
        df["team_key"] = (away.fillna("") + "@" + home.fillna("")).astype(str)
    else:
        df["team_key"] = ""

    # date_key as normalized YYYY-MM-DD string (or empty)
    df["date_key"] = norm_date_str(df.get("game_date")) if "game_date" in df.columns else ""
    return df

def safe_merge(left: pd.DataFrame, right: pd.DataFrame, on, how="left", suffixes=("", "_g")) -> pd.DataFrame:
    # ensure join keys are strings on both sides to avoid dtype mismatches
    left  = left.copy()
    right = right.copy()
    for k in on:
        left[k]  = left[k].astype(str)
        right[k] = right[k].astype(str)
    keep = list(dict.fromkeys(on + FILL_COLS))  # unique, order-preserving
    present = [c for c in keep if c in right.columns]
    return left.merge(right[present], on=on, how=how, suffixes=suffixes)

def coalesce(base: pd.DataFrame, other: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = base.copy()
    for c in cols:
        if c in out.columns and c in other.columns:
            out[c] = out[c].combine_first(other[c])
    return out

def join_edges_games(edges: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    # Pass 0: exact by game_id
    m0 = safe_merge(edges, games, on=["game_id"], how="left")

    # Build keys for fallback joins
    edges_k = build_keys(edges.copy())
    games_k = build_keys(games.copy())

    # Pass 1: season+week+team_key
    m1 = safe_merge(edges_k, games_k, on=["season","week","team_key"], how="left")
    filled = coalesce(m0, m1, FILL_COLS)

    # Pass 2: date_key+team_key (helps when week missing)
    m2 = safe_merge(edges_k, games_k, on=["date_key","team_key"], how="left")
    filled = coalesce(filled, m2, FILL_COLS)

    return filled

def american_profit(price:int, stake:float):
    if pd.isna(price) or pd.isna(stake): return None
    price = int(price); stake = float(stake)
    return stake * (price/100.0) if price > 0 else stake * (100.0/abs(price))

def grade_row(r: pd.Series):
    hs, as_ = r.get("home_score"), r.get("away_score")
    status = str(r.get("status","")).lower()
    mkt = str(r.get("market","")).lower()
    side = str(r.get("side","")).lower()
    line = r.get("line")

    if pd.isna(hs) or pd.isna(as_) or status != "final":
        return ("na", None, "not final or missing scores")

    hs = int(hs); as_ = int(as_)
    sign = lambda x: 1 if x > 0 else (0 if x == 0 else -1)

    if mkt == "moneyline":
        winner = "home" if hs > as_ else ("away" if as_ > hs else "push")
        if winner == "push": return ("push", 0.0, "tie")
        return ("win" if side == winner else "loss", None, "")

    if mkt == "spread":
        if pd.isna(line): return ("na", None, "missing line")
        adj = (hs - as_) - (line if side == "home" else -line)
        s = sign(adj)
        return ("win" if s>0 else "push" if s==0 else "loss", None, "")

    if mkt == "total":
        if pd.isna(line): return ("na", None, "missing line")
        tot = hs + as_
        s = sign((tot - line) if side=="over" else (line - tot))
        return ("win" if s>0 else "push" if s==0 else "loss", None, "")

    return ("na", None, f"unsupported market: {mkt}")

def main(edges_path, games_path, out_path):
    edges = read_csv(edges_path)
    games = read_csv(games_path)

    # numeric coercions
    edges["price"] = to_int(edges.get("price"))
    edges["stake"] = to_float(edges.get("stake")).fillna(1.0)
    edges["line"]  = to_float(edges.get("line"))

    # normalize teams for keys
    for c in ("home_team","away_team"):
        if c in edges.columns: edges[c] = edges[c].map(norm_team)
        if c in games.columns: games[c] = games[c].map(norm_team)

    m = join_edges_games(edges, games)

    # Grade
    res, why, profit = [], [], []
    for _, r in m.iterrows():
        outcome, _, reason = grade_row(r)
        res.append(outcome); why.append(reason)
        if outcome == "win":
            profit.append(american_profit(r.get("price"), r.get("stake")))
        elif outcome == "loss":
            stk = r.get("stake")
            profit.append(-float(stk) if not pd.isna(stk) else None)
        elif outcome == "push":
            profit.append(0.0)
        else:
            profit.append(None)

    m["result"] = res
    m["reason"] = why
    m["profit_units"] = profit

    m.to_csv(out_path, index=False)
    vc = m["result"].value_counts(dropna=False).to_dict()
    print(f"[ok] wrote {out_path} rows={len(m)} results={vc}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", required=True)
    ap.add_argument("--games", required=True)
    ap.add_argument("--out",   required=True)
    args = ap.parse_args()
    main(args.edges, args.games, args.out)

