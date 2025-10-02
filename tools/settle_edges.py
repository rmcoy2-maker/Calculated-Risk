# tools/settle_edges.py
import pandas as pd
from pathlib import Path
from lib_settlement import settle_bets, _autoload_edges, _autoload_scores

edges = pd.read_csv(_autoload_edges(), low_memory=False)
scores = pd.read_csv(_autoload_scores(), low_memory=False)
settled = settle_bets(edges, scores)
out = Path("exports/edges_settled.csv")
settled.to_csv(out, index=False, encoding="utf-8-sig")
print(f"Saved → {out}")

