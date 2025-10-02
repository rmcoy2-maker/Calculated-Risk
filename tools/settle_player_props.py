# tools/settle_player_props.py
# Grades edges in exports/edges.csv using exports/player_game_stats.parquet and player_tds.parquet (if present)
import re
import pandas as pd
from pathlib import Path

EDGES = Path("exports/edges.csv")
STATS = Path("exports/player_game_stats.parquet")
TDS   = Path("exports/player_tds.parquet")  # optional (from build_player_tds.py)

def load_edges() -> pd.DataFrame:
    if not EDGES.exists():
        raise FileNotFoundError(EDGES)
    e = pd.read_csv(EDGES)
    e.columns = [c.lower() for c in e.columns]
    for c in ("season","week","game_id","player_id","line"):
        if c in e.columns:
            e[c] = pd.to_numeric(e[c], errors="coerce")
    return e

def parse_player_id(row) -> int | None:
    pid = row.get("player_id")
    if pd.notna(pid):
        return int(pid)
    sel = str(row.get("selection","")).lower()
    m = re.search(r"player:(\d+)", sel)
    return int(m.group(1)) if m else None

def settle_numeric(e: pd.DataFrame, stats: pd.DataFrame, market_prefix: str, stat_col: str):
    mask = e["market"].str.lower().str.startswith(market_prefix)
    sub = e[mask].copy()
    if sub.empty:
        return e
    sub["player_id"] = sub.apply(parse_player_id, axis=1)
    key = ["season","week","game_id","player_id"]
    joined = sub.merge(stats[key + [stat_col]], on=key, how="left")
    # market forms: "player_pass_yds:over", "player_rec:under", etc. with numeric 'line'
    side = joined["market"].str.lower().str.split(":", n=1).str[1].fillna("")
    line = pd.to_numeric(joined.get("line"), errors="coerce")
    val  = pd.to_numeric(joined[stat_col], errors="coerce")
    win  = (side=="over")  & (val >= line)
    lose = (side=="under") & (val <= line)
    # ties/push when val == line for point props
    push = (val == line) & (side.isin(["over","under"]))
    joined["result"] = pd.NA
    joined.loc[win, "result"]  = "win"
    joined.loc[lose, "result"] = "lose"
    joined.loc[push, "result"] = "push"
    e.loc[joined.index, "result"] = joined["result"]
    return e

if __name__ == "__main__":
    edges = load_edges()
    if not STATS.exists():
        raise FileNotFoundError(STATS)
    stats = pd.read_parquet(STATS)

    # QB passing yards
    edges = settle_numeric(edges, stats, "player_pass_yds", "pass_yards")
    # QB pass attempts
    edges = settle_numeric(edges, stats, "player_pass_att", "pass_attempts")
    # Receptions
    edges = settle_numeric(edges, stats, "player_rec", "receptions")
    # Receiving yards
    edges = settle_numeric(edges, stats, "player_rec_yds", "rec_yards")
    # Rushing attempts
    edges = settle_numeric(edges, stats, "player_rush_att", "rush_att")
    # Rushing yards
    edges = settle_numeric(edges, stats, "player_rush_yds", "rush_yards")

    # Anytime TD (optional; uses exports/player_tds.parquet if you built it)
    if TDS.exists():
        tds = pd.read_parquet(TDS)
        td_mask = edges["market"].str.lower().str.startswith("player_td:anytime")
        attd = edges[td_mask].copy()
        if not attd.empty:
            attd["player_id"] = attd.apply(parse_player_id, axis=1)
            key = ["season","week","game_id","player_id"]
            joined = attd.merge(tds[key + ["anytime_td_hit"]], on=key, how="left")
            edges.loc[joined.index, "result"] = joined["anytime_td_hit"].map({1:"win", 0:"lose"})

    edges.to_csv(EDGES, index=False)
    print("Settled player props into", EDGES)

