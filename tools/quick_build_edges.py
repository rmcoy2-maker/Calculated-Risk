# tools/quick_build_edges.py
from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "db"
EXPORTS = ROOT / "exports"
EXPORTS.mkdir(parents=True, exist_ok=True)

SRC = DB / "odds_books.csv"      # <-- your seed odds file
OUT = EXPORTS / "edges.csv"

def to_int_odds(x):
    try:
        s = str(x).strip().replace("+","")
        return int(round(float(s)))
    except Exception:
        return None

def build_edges(df_src: pd.DataFrame) -> pd.DataFrame:
    d = df_src.copy()
    d.columns = [c.lower() for c in d.columns]
    ren = {
        "sportsbook":"book","book_name":"book","bookmaker":"book","site":"book",
        "american":"odds","price":"odds",
        "bet_type":"market","market_type":"market","wager_type":"market",
        "selection":"side","team":"side","competitor":"side",
        "total":"line","points":"line","threshnew":"line",
        "prob":"p_win","probability":"p_win","implied_prob":"p_win",
        "note":"ref","id":"ref",
        "event_time":"start_time","datetime":"start_time","kickoff":"start_time",
        "home":"home_team","away":"away_team",
        "home_team_name":"home_team","away_team_name":"away_team",
        "participant":"player","athlete":"player","player_name":"player",
        "outcome_name":"outcome","result":"outcome",
    }
    d.rename(columns={k:v for k,v in ren.items() if k in d.columns}, inplace=True)
    for col in ["game_id","book","market","side","player","line","odds","p_win","ref",
                "home_team","away_team","start_time","outcome"]:
        if col not in d.columns: d[col] = None

    def mk_game_id(r):
        if pd.notna(r.get("game_id")) and str(r.get("game_id")).strip():
            return str(r["game_id"])
        ht, at = r.get("home_team"), r.get("away_team")
        dt = str(r.get("start_time") or "")
        if pd.notna(ht) and pd.notna(at):
            return f"{dt[:10]}-{str(at)[:3]}@{str(ht)[:3]}".replace(" ","")
        return None

    rows = []

    # Moneyline (includes H2H)
    ml_mask = d["market"].astype(str).str.contains(r"\b(ml|moneyline|h2h)\b", case=False, na=False)
    for _, r in d[ml_mask].iterrows():
        rows.append({"game_id": mk_game_id(r), "market":"Moneyline", "side":r.get("side"),
                     "line":None, "book":r.get("book"), "odds":to_int_odds(r.get("odds")),
                     "p_win":r.get("p_win"), "ref":r.get("ref")})

    # Spread
    sp = d[d["market"].astype(str).str.contains("spread", case=False, na=False)]
    for _, r in sp.iterrows():
        rows.append({"game_id": mk_game_id(r), "market":"Spread", "side":r.get("side"),
                     "line":r.get("line"), "book":r.get("book"), "odds":to_int_odds(r.get("odds")),
                     "p_win":r.get("p_win"), "ref":r.get("ref")})

    # Totals (Over/Under)
    tot = d[d["market"].astype(str).str.contains("total", case=False, na=False)]
    for _, r in tot.iterrows():
        ou = (r.get("outcome") or r.get("side") or "").strip().title()
        if ou not in ("Over","Under"):
            s = str(r.get("side") or "")
            ou = "Over" if "o" in s.lower() else ("Under" if "u" in s.lower() else "Over")
        rows.append({"game_id": mk_game_id(r), "market":"Total", "side":ou,
                     "line":r.get("line"), "book":r.get("book"), "odds":to_int_odds(r.get("odds")),
                     "p_win":r.get("p_win"), "ref":r.get("ref")})

    # Props (if present)
    prop_mask = d["market"].astype(str).str.contains("prop", case=False, na=False) | d.columns.to_list().__contains__("player")
    pr = d[prop_mask]
    for _, r in pr.iterrows():
        m = str(r.get("market") or "")
        ptype = m.split(":",1)[-1].strip() if ":" in m.lower() else (m if "prop" in m.lower() else "Prop")
        ou = (r.get("outcome") or r.get("side") or "").strip().title()
        if ou not in ("Over","Under"): ou = "Over"
        side = f"{ou} {str(r.get('player') or r.get('side') or '').strip()}".strip()
        rows.append({"game_id": mk_game_id(r), "market":f"Prop: {ptype}", "side":side,
                     "line":r.get("line"), "book":r.get("book"), "odds":to_int_odds(r.get("odds")),
                     "p_win":r.get("p_win"), "ref":r.get("ref")})

    out = pd.DataFrame(rows, columns=["game_id","market","side","line","book","odds","p_win","ref"])
    out = out[out["odds"].notna()].reset_index(drop=True)
    return out

def main():
    if not SRC.exists() or SRC.stat().st_size <= 5:
        raise SystemExit(f"Missing or empty source: {SRC}")
    df = pd.read_csv(SRC)
    edges = build_edges(df)
    edges.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Wrote {len(edges):,} rows -> {OUT}")

if __name__ == "__main__":
    main()




