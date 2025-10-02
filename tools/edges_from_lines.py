# tools/build_edges_from_lines.py
from __future__ import annotations

import pandas as pd
from pathlib import Path

# --- import your loader ---
# db/market_lines.csv -> DataFrame
from pull_lines import load_lines  # uses db/market_lines.csv  (you already have this)  # noqa

ROOT = Path(__file__).resolve().parents[1] if (Path(__file__).parent.name == "tools") else Path(__file__).resolve().parents[0]
EXPORTS = ROOT / "exports"
EXPORTS.mkdir(parents=True, exist_ok=True)
OUT = EXPORTS / "edges.csv"

# common synonyms we normalize to: game_id, book, market, team/player, side, line, odds, p_win, ref
RENAMES = {
    "sportsbook": "book",
    "book_name": "book",
    "sports_book": "book",
    "american": "odds",
    "price": "odds",
    "selection": "side",
    "team": "side",
    "competitor": "side",
    "participant": "player",
    "athlete": "player",
    "bet_type": "market",
    "market_type": "market",
    "wager_type": "market",
    "total": "line",
    "points": "line",
    "threshnew": "line",
    "prob": "p_win",
    "probability": "p_win",
    "implied_prob": "p_win",
    "note": "ref",
    "id": "ref",
}

def _lower(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={k.lower(): v for k, v in RENAMES.items() if k.lower() in df.columns})
    for col in ["game_id","book","market","side","player","line","odds","p_win","ref","home_team","away_team","start_time","outcome"]:
        if col not in df.columns:
            df[col] = None
    return df

def _mk_game_id(row: pd.Series) -> str | None:
    # prefer provided game_id; else derive from teams+date if available
    if pd.notna(row.get("game_id")) and str(row.get("game_id")).strip():
        return str(row["game_id"])
    ht, at = row.get("home_team"), row.get("away_team")
    dt = str(row.get("start_time") or "")
    if pd.notna(ht) and pd.notna(at):
        base = f"{dt[:10]}-{str(at)[:3]}@{str(ht)[:3]}".replace(" ", "")
        return base
    return None

def _to_int_odds(val):
    try:
        f = float(val)
        return int(round(f))
    except Exception:
        try:
            s = str(val).replace("+","")
            if s.lstrip("-").isdigit():
                return int(s)
        except Exception:
            pass
    return None

def build_edges(df_src: pd.DataFrame) -> pd.DataFrame:
    d = _lower(df_src)

    rows = []

    # ---------- Moneyline ----------
    ml_mask = d["market"].astype(str).str.lower().isin(["ml","moneyline"]) | d["market"].astype(str).str.contains("moneyline", case=False, na=False)
    for _, r in d[ml_mask].iterrows():
        rows.append({
            "game_id": _mk_game_id(r),
            "market": "Moneyline",
            "side": r.get("side"),
            "line": None,
            "book": r.get("book"),
            "odds": _to_int_odds(r.get("odds")),
            "p_win": r.get("p_win"),
            "ref": r.get("ref"),
        })

    # ---------- Spread ----------
    sp_mask = d["market"].astype(str).str.contains("spread", case=False, na=False) | d["market"].astype(str).str.lower().eq("spread")
    for _, r in d[sp_mask].iterrows():
        rows.append({
            "game_id": _mk_game_id(r),
            "market": "Spread",
            "side": r.get("side"),
            "line": r.get("line"),
            "book": r.get("book"),
            "odds": _to_int_odds(r.get("odds")),
            "p_win": r.get("p_win"),
            "ref": r.get("ref"),
        })

    # ---------- Totals (Over/Under) ----------
    tot_mask = d["market"].astype(str).str.contains("total", case=False, na=False) | d["market"].astype(str).str.lower().eq("total")
    for _, r in d[tot_mask].iterrows():
        ou = (r.get("outcome") or r.get("side") or "").strip().title()
        if ou not in ("Over","Under"):
            s = str(r.get("side") or "")
            if "o" in s.lower(): ou = "Over"
            elif "u" in s.lower(): ou = "Under"
            else: ou = "Over"
        rows.append({
            "game_id": _mk_game_id(r),
            "market": "Total",
            "side": ou,                        # Over / Under
            "line": r.get("line"),             # number (e.g., 45.5)
            "book": r.get("book"),
            "odds": _to_int_odds(r.get("odds")),
            "p_win": r.get("p_win"),
            "ref": r.get("ref"),
        })

    # ---------- Props (basic pass) ----------
    prop_mask = d["market"].astype(str).str.contains("prop", case=False, na=False) | d.columns.to_list().__contains__("player")
    pr = d[prop_mask]
    for _, r in pr.iterrows():
        m = str(r.get("market") or "").strip()
        ptype = m.split(":", 1)[-1].strip() if ":" in m.lower() else (m if "prop" in m.lower() else "Prop")
        ou = (r.get("outcome") or r.get("side") or "").strip().title()
        if ou not in ("Over","Under"): ou = "Over"
        side = f"{ou} {str(r.get('player') or r.get('side') or '')}".strip()
        rows.append({
            "game_id": _mk_game_id(r),
            "market": f"Prop: {ptype}",
            "side": side,                      # e.g., 'Over Travis Kelce'
            "line": r.get("line"),
            "book": r.get("book"),
            "odds": _to_int_odds(r.get("odds")),
            "p_win": r.get("p_win"),
            "ref": r.get("ref"),
        })

    out = pd.DataFrame(rows, columns=["game_id","market","side","line","book","odds","p_win","ref"])
    # drop rows without usable odds
    out = out[out["odds"].notna()].reset_index(drop=True)
    return out

def main():
    df_lines = load_lines()   # your function that reads db/market_lines.csv
    edges = build_edges(df_lines)
    OUT.write_text("")  # ensure fresh write on Windows if locked
    edges.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Wrote {len(edges):,} rows -> {OUT}")

if __name__ == "__main__":
    main()




