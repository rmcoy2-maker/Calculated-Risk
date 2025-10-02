import pandas as pd
import re

# Extend this as needed
TEAM_TO_ABBR = {
    "Arizona Cardinals":"ARI",
    "Atlanta Falcons":"ATL",
    "Baltimore Ravens":"BAL",
    "Buffalo Bills":"BUF",
    "Carolina Panthers":"CAR",
    "Chicago Bears":"CHI",
    "Cincinnati Bengals":"CIN",
    "Cleveland Browns":"CLE",
    "Dallas Cowboys":"DAL",
    "Denver Broncos":"DEN",
    "Detroit Lions":"DET",
    "Green Bay Packers":"GB",
    "Houston Texans":"HOU",
    "Indianapolis Colts":"IND",
    "Jacksonville Jaguars":"JAC",  # (JAX → JAC)
    "Kansas City Chiefs":"KC",
    "Las Vegas Raiders":"LV",      # (OAK → LV)
    "Los Angeles Chargers":"LAC",  # (SD → LAC)
    "Los Angeles Rams":"LAR",      # (STL → LAR)
    "Miami Dolphins":"MIA",
    "Minnesota Vikings":"MIN",
    "New England Patriots":"NE",
    "New Orleans Saints":"NO",
    "New York Giants":"NYG",
    "New York Jets":"NYJ",
    "Philadelphia Eagles":"PHI",
    "Pittsburgh Steelers":"PIT",
    "San Francisco 49ers":"SF",
    "Seattle Seahawks":"SEA",
    "Tampa Bay Buccaneers":"TB",
    "Tennessee Titans":"TEN",
    "Washington Commanders":"WAS", # (WSH → WAS)
}

def parse_game_id_to_parts(s: str):
    """
    'Los Angeles Chargers@Las Vegas Raiders_2025-09-16T02:05:19Z'
    -> ('Los Angeles Chargers','Las Vegas Raiders','2025-09-16')
    """
    if not isinstance(s, str) or "@" not in s or "_" not in s:
        return (None, None, None)
    teams, ts = s.split("_", 1)
    home_full, away_full = teams.split("@", 1)
    # date-only; tolerate 'T..Z' or plain date
    m = re.match(r"(\d{4}-\d{2}-\d{2})", ts)
    d = m.group(1) if m else None
    return (home_full.strip(), away_full.strip(), d)

def norm_abbr_from_full(name: str) -> str | None:
    if not isinstance(name, str):
        return None
    name = name.strip()
    return TEAM_TO_ABBR.get(name)

def build_unordered_key(season, date_str, a_abbr, b_abbr):
    if pd.isna(season) or not date_str or not a_abbr or not b_abbr:
        return None
    a,b = sorted([a_abbr, b_abbr])
    return f"{int(season)}|{date_str}|{a}|{b}"

def attach_scores_by_unordered_key(edges: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    e = edges.copy()

    # Derive keys from game_id where needed
    if "game_id" in e.columns:
        parts = e["game_id"].apply(parse_game_id_to_parts)
        e[["_home_full","_away_full","_date_only"]] = pd.DataFrame(parts.tolist(), index=e.index)
        e["_home_abbr_from_full"] = e["_home_full"].apply(norm_abbr_from_full)
        e["_away_abbr_from_full"] = e["_away_full"].apply(norm_abbr_from_full)

        # Prefer existing abbrs if present; else use derived
        def pick(col1, col2):
            c1 = e[col1] if col1 in e.columns else pd.Series([None]*len(e))
            c2 = e[col2]
            return c1.where(c1.notna() & (c1.astype(str).str.len()>0), c2)

        e["_home_abbr_eff"] = pick("home_abbr","_home_abbr_from_full")
        e["_away_abbr_eff"] = pick("away_abbr","_away_abbr_from_full")

        # Prefer explicit game_date if present, else parsed date
        if "game_date" in e.columns:
            gd = e["game_date"].astype(str).str[:10]  # yyyy-mm-dd
            e["_date_eff"] = gd.where(gd.notna() & gd.ne(""), e["_date_only"])
        else:
            e["_date_eff"] = e["_date_only"]

        e["_key_u"] = [
            build_unordered_key(sea, dt, ha, aa)
            for sea, dt, ha, aa in zip(e.get("season"), e["_date_eff"], e["_home_abbr_eff"], e["_away_abbr_eff"])
        ]
    else:
        e["_key_u"] = None  # nothing we can do here

    # Prepare scores with the same unordered key
    s = scores.copy()
    # Try to assemble abbrs from either abbr or full names
    for a, b in [("home", "away")]:
        pass
    def best_abbr(df, side):
        # Use abbr if present; else map from full team name columns
        cand = None
        for c in [f"{side}_abbr", f"{side}_team_norm", f"{side}_team", f"{side}_name"]:
            if c in df.columns:
                cand = df[c].astype(str)
                break
        if cand is None:
            return pd.Series([None]*len(df), index=df.index)
        mapped = cand.map(TEAM_TO_ABBR).where(cand.isin(TEAM_TO_ABBR.keys()), cand)
        # If mapped still looks like a full name not in dict, try exact dict lookup
        mapped = mapped.replace("", pd.NA)
        return mapped

    s["_home_abbr_eff"] = best_abbr(s, "home")
    s["_away_abbr_eff"] = best_abbr(s, "away")
    if "game_date" in s.columns:
        s["_date_eff"] = s["game_date"].astype(str).str[:10]
    else:
        # if have a timestamp column, adapt here
        s["_date_eff"] = s.get("date", pd.Series([None]*len(s)))

    s["_key_u"] = [
        build_unordered_key(sea, dt, ha, aa)
        for sea, dt, ha, aa in zip(s.get("season"), s["_date_eff"], s["_home_abbr_eff"], s["_away_abbr_eff"])
    ]

    # Merge by unordered key (left join)
    keep = ["_key_u","home_score","away_score"]
    for c in ["home_points","away_points","pts_home","pts_away"]:
        if c in s.columns: keep += [c]
    s_small = s[keep].drop_duplicates("_key_u")

    merged = e.merge(s_small, on="_key_u", how="left")

    # Consolidate score columns to home_score_y/away_score_y
    if "home_score" in merged.columns:
        merged["home_score_y"] = merged["home_score"]
        merged.drop(columns=["home_score"], inplace=True)
    if "away_score" in merged.columns:
        merged["away_score_y"] = merged["away_score"]
        merged.drop(columns=["away_score"], inplace=True)
    for src, dst in [("home_points","home_score_y"), ("away_points","away_score_y"),
                     ("pts_home","home_score_y"), ("pts_away","away_score_y")]:
        if src in merged.columns and dst not in merged.columns:
            merged[dst] = pd.to_numeric(merged[src], errors="coerce")

    return merged

def grade_totals(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # choose columns
    def pick(names):
        for n in names:
            if n in out.columns: return n
        return None
    market_col = pick(["market_norm","market"])
    home_col   = pick(["home_score_y","home_score","home_points"])
    away_col   = pick(["away_score_y","away_score","away_points"])
    line_col   = pick(["over_under_line","line","total_line"])

    # numeric
    for c in [home_col, away_col, line_col]:
        if c: out[c] = pd.to_numeric(out[c], errors="coerce")

    is_total = out[market_col].astype(str).str.lower().eq("total")
    scores_ok = out[home_col].notna() & out[away_col].notna()
    ou_ok = out[line_col].notna()
    mask = is_total & scores_ok & ou_ok

    tot = out[home_col] + out[away_col]
    side = out["side"].astype(str).str.upper()

    push   = mask & (tot == out[line_col])
    over_w = mask & side.eq("OVER")  & (tot > out[line_col])
    over_l = mask & side.eq("OVER")  & (tot < out[line_col])
    under_w= mask & side.eq("UNDER") & (tot < out[line_col])
    under_l= mask & side.eq("UNDER") & (tot > out[line_col])

    if "result_norm" not in out.columns:
        out["result_norm"] = pd.NA

    out.loc[push, "result_norm"] = "push"
    out.loc[over_w | under_w, "result_norm"] = "win"
    out.loc[over_l | under_l, "result_norm"] = "loss"

    if "why_other" not in out.columns:
        out["why_other"] = pd.NA
    left = is_total & out["result_norm"].isna()
    out.loc[left & ~(scores_ok & ou_ok), "why_other"] = "Missing final scores or OU line"
    out.loc[left &  (scores_ok & ou_ok), "why_other"] = "Totals logic fall-through"

    return out

# --- Usage in your pipeline ---
edges = pd.read_csv("exports/edges.csv", low_memory=False)  # or the pre-merged frame before scores
scores = pd.read_csv("exports/scores_clean.csv", low_memory=False)  # your normalized scores file

merged = attach_scores_by_unordered_key(edges, scores)
graded = grade_totals(merged)
graded.to_csv("exports/edges_graded_full.csv", index=False)
print("Totals graded; wrote exports/edges_graded_full.csv")

