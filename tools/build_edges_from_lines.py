# tools/build_edges_from_lines.py
from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "db"
EXPORTS = ROOT / "exports"
EXPORTS.mkdir(parents=True, exist_ok=True)
OUT = EXPORTS / "edges.csv"

CANDIDATES = [
    DB / "market_lines_2025.csv",  # produced by build_market_lines.py
    DB / "market_lines.csv",       # generic name your loader uses
]

def _read_lines() -> pd.DataFrame:
    for p in CANDIDATES:
        if p.exists() and p.stat().st_size > 5:
            return pd.read_csv(p)
    raise SystemExit("No market lines file found (looked for market_lines_2025.csv / market_lines.csv).")

REN = {
    "sportsbook":"book","book_name":"book","bookmaker":"book","site":"book",
    "american":"odds","price":"odds",
    "bet_type":"market","market_type":"market","wager_type":"market",
    "selection":"side","team":"side","competitor":"side",
    "total":"line","points":"line","threshnew":"line",
    "prob":"p_win","probability":"p_win","implied_prob":"p_win",
    "note":"ref","id":"ref",
}

def _std(df: pd.DataFrame) -> pd.DataFrame:
    d = df.rename(columns={c: c.lower() for c in df.columns}).copy()
    for k,v in REN.items():
        if k in d.columns: d.rename(columns={k:v}, inplace=True)
    for col in ["game_id","book","market","side","player","line","odds","p_win","ref","home_team","away_team","start_time","outcome"]:
        if col not in d.columns: d[col] = None
    return d

def _mk_game_id(r) -> str | None:
    if pd.notna(r.get("game_id")) and str(r.get("game_id")).strip():
        return str(r["game_id"])
    ht, at = r.get("home_team"), r.get("away_team")
    dt = str(r.get("start_time") or "")
    if pd.notna(ht) and pd.notna(at):
        return f"{dt[:10]}-{str(at)[:3]}@{str(ht)[:3]}".replace(" ","")
    return None

def _to_int_odds(x):
    try:
        s = str(x).strip().replace("+","")
        return int(round(float(s)))
    except Exception:
        return None

def build_edges(df_src: pd.DataFrame) -> pd.DataFrame:
    d = _std(df_src)
    rows = []

    # Moneyline
    ml = d[d["market"].astype(str).str.contains(r"\b(ml|moneyline|h2h)\b", case=False, na=False)]
    for _, r in ml.iterrows():
        rows.append({"game_id": _mk_game_id(r), "market":"Moneyline", "side":r.get("side"),
                     "line":None, "book":r.get("book"), "odds":_to_int_odds(r.get("odds")),
                     "p_win":r.get("p_win"), "ref":r.get("ref")})

    # Spread
    sp = d[d["market"].astype(str).str.contains("spread", case=False, na=False)]
    for _, r in sp.iterrows():
        rows.append({"game_id": _mk_game_id(r), "market":"Spread", "side":r.get("side"),
                     "line":r.get("line"), "book":r.get("book"), "odds":_to_int_odds(r.get("odds")),
                     "p_win":r.get("p_win"), "ref":r.get("ref")})

    # Total (Over/Under)
    tot = d[d["market"].astype(str).str.contains("total", case=False, na=False)]
    for _, r in tot.iterrows():
        ou = (r.get("outcome") or r.get("side") or "").title()
        if ou not in ("Over","Under"):
            s = str(r.get("side") or "")
            ou = "Over" if "o" in s.lower() else ("Under" if "u" in s.lower() else "Over")
        rows.append({"game_id": _mk_game_id(r), "market":"Total", "side":ou,
                     "line":r.get("line"), "book":r.get("book"), "odds":_to_int_odds(r.get("odds")),
                     "p_win":r.get("p_win"), "ref":r.get("ref")})

    # Props (basic)
    prop_mask = d["market"].astype(str).str.contains("prop", case=False, na=False) | d.columns.to_list().__contains__("player")
    pr = d[prop_mask]
    for _, r in pr.iterrows():
        m = str(r.get("market") or "")
        ptype = m.split(":",1)[-1].strip() if ":" in m.lower() else (m if "prop" in m.lower() else "Prop")
        ou = (r.get("outcome") or r.get("side") or "").title()
        if ou not in ("Over","Under"): ou = "Over"
        side = f"{ou} {str(r.get('player') or r.get('side') or '').strip()}".strip()
        rows.append({"game_id": _mk_game_id(r), "market":f"Prop: {ptype}", "side":side,
                     "line":r.get("line"), "book":r.get("book"), "odds":_to_int_odds(r.get("odds")),
                     "p_win":r.get("p_win"), "ref":r.get("ref")})

    out = pd.DataFrame(rows, columns=["game_id","market","side","line","book","odds","p_win","ref"])
    out = out[out["odds"].notna()].reset_index(drop=True)
    return out

def main():
    df = _read_lines()
    edges = build_edges(df)
    edges.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Wrote {len(edges):,} rows -> {OUT}")

if __name__ == "__main__":
    main()




