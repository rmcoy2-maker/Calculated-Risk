# tools/build_player_stats.py
# Creates exports/player_game_stats.parquet from datasets/nfl/plays/*_plays.csv
import pandas as pd
from pathlib import Path

PLAYS_DIR = Path("datasets/nfl/plays")
OUT = Path("exports/player_game_stats.parquet")
OUT.parent.mkdir(parents=True, exist_ok=True)

# Column fallback mapper (adjust if your schema differs)
ALIAS = {
    "season": ["season", "year"],
    "week": ["week"],
    "game_id": ["game_id", "gid", "gameid"],

    "passer_player_id": ["passer_player_id", "passer_id", "qb_id"],
    "passer_player_name": ["passer_player_name", "passer", "qb_name"],

    "receiver_player_id": ["receiver_player_id", "target_player_id", "wr_id"],
    "receiver_player_name": ["receiver_player_name", "target_player_name", "wr_name"],

    "rusher_player_id": ["rusher_player_id", "rusher_id", "rb_id"],
    "rusher_player_name": ["rusher_player_name", "rusher", "rb_name"],

    "pass_attempt": ["pass_attempt", "is_pass", "pass"],
    "complete_pass": ["complete_pass", "is_complete", "complete"],
    "pass_yards": ["pass_yards", "yards_gained", "air_yards_after_catch"],
    "pass_touchdown": ["pass_touchdown", "pass_td"],

    "interception": ["interception", "interception_thrown"],

    "rush_attempt": ["rush_attempt", "is_rush", "rush"],
    "rush_yards": ["rush_yards", "yards_gained"],
    "rush_touchdown": ["rush_touchdown", "rush_td"],

    "reception": ["reception", "complete_pass"],  # if complete == 1 for receiver row
    "rec_yards": ["rec_yards", "yards_gained", "yac"],
    "rec_touchdown": ["rec_touchdown", "rec_td", "receiving_td"],
}

def pick(df, name):
    for c in ALIAS[name]:
        if c in df.columns:
            return c
    return None

def load_one(csv: Path) -> pd.DataFrame:
    df = pd.read_csv(csv)
    # Map required columns or create zeros
    need_flags = ["pass_attempt","complete_pass","pass_yards","pass_touchdown",
                  "interception","rush_attempt","rush_yards","rush_touchdown",
                  "reception","rec_yards","rec_touchdown"]
    id_cols = ["season","week","game_id",
               "passer_player_id","passer_player_name",
               "receiver_player_id","receiver_player_name",
               "rusher_player_id","rusher_player_name"]

    out = pd.DataFrame()
    # Attach identifiers (allow per-file constants if not per-row)
    for k in ["season","week","game_id"]:
        col = pick(df, k)
        out[k] = pd.to_numeric(df[col], errors="coerce") if col else pd.NA

    # Normalize flag/value columns  ✅ ensure Series when missing
    for k in need_flags:
        col = pick(df, k)
        s = df[col] if col else 0
        if "yards" in k:
            out[k] = pd.to_numeric(s, errors="coerce").fillna(0)
        else:
            out[k] = pd.to_numeric(s, errors="coerce").fillna(0).astype(int)

    # Attach player ids/names (may be NaN for rows not involving that role)
    for k in ["passer_player_id","passer_player_name","receiver_player_id","receiver_player_name",
              "rusher_player_id","rusher_player_name"]:
        col = pick(df, k)
        out[k] = df[col] if col else None

    # --- Aggregate per role ---
    season = pd.to_numeric(out["season"], errors="coerce").dropna()
    week   = pd.to_numeric(out["week"], errors="coerce").dropna()
    gid    = pd.to_numeric(out["game_id"], errors="coerce").dropna()
    season = int(season.iloc[0]) if not season.empty else None
    week   = int(week.iloc[0]) if not week.empty else None
    gid    = int(gid.iloc[0]) if not gid.empty else None

    # QBs
    q = out.groupby(["passer_player_id","passer_player_name"], dropna=False).agg(
        pass_attempts=("pass_attempt","sum"),
        completions=("complete_pass","sum"),
        pass_yards=("pass_yards","sum"),
        pass_tds=("pass_touchdown","sum"),
        interceptions=("interception","sum"),
    ).reset_index()
    q["season"], q["week"], q["game_id"], q["role"] = season, week, gid, "qb"
    q = q.rename(columns={"passer_player_id":"player_id","passer_player_name":"player_name"})

    # Receivers
    rcv = out.groupby(["receiver_player_id","receiver_player_name"], dropna=False).agg(
        targets=("pass_attempt","sum"),
        receptions=("reception","sum"),
        rec_yards=("rec_yards","sum"),
        rec_tds=("rec_touchdown","sum"),
    ).reset_index()
    rcv["season"], rcv["week"], rcv["game_id"], rcv["role"] = season, week, gid, "receiver"
    rcv = rcv.rename(columns={"receiver_player_id":"player_id","receiver_player_name":"player_name"})

    # Rushers
    rsh = out.groupby(["rusher_player_id","rusher_player_name"], dropna=False).agg(
        rush_att=("rush_attempt","sum"),
        rush_yards=("rush_yards","sum"),
        rush_tds=("rush_touchdown","sum"),
    ).reset_index()
    rsh["season"], rsh["week"], rsh["game_id"], rsh["role"] = season, week, gid, "rusher"
    rsh = rsh.rename(columns={"rusher_player_id":"player_id","rusher_player_name":"player_name"})

    return pd.concat([q, rcv, rsh], ignore_index=True)

def load_all() -> pd.DataFrame:
    rows = []
    for f in sorted(PLAYS_DIR.glob("*_plays.csv")):
        rows.append(load_one(f))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["player_id","player_name","role","season","week","game_id",
                 "pass_attempts","completions","pass_yards","pass_tds","interceptions",
                 "targets","receptions","rec_yards","rec_tds",
                 "rush_att","rush_yards","rush_tds"]
    )

if __name__ == "__main__":
    df = load_all()
    # enforce 2017+ just in case files include earlier
    df = df[pd.to_numeric(df["season"], errors="coerce").fillna(0) >= 2017]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"wrote {OUT} with {len(df):,} rows; seasons: {sorted(df['season'].dropna().unique().tolist())[:5]} ...")


