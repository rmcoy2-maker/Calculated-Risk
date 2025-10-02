import pandas as pd, numpy as np, pathlib as p

src = p.Path("exports/scores_unified.csv")
dst = p.Path("exports/games.csv")
if not src.exists():
    raise SystemExit(f"Missing {src}")

df  = pd.read_csv(src)

need = ["season","week","date","home","away","home_score","away_score","game_id_unified"]
missing = [c for c in need if c not in df.columns]
if missing:
    raise SystemExit(f"{src} missing {missing}")

out = (df[need].rename(columns={"game_id_unified":"game_id"})).copy()
out["season"] = pd.to_numeric(out["season"], errors="coerce").astype("Int64")
out["week"]   = pd.to_numeric(out["week"],   errors="coerce").astype("Int64")
out["date"]   = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")
out["home_score"] = pd.to_numeric(out["home_score"], errors="coerce")
out["away_score"] = pd.to_numeric(out["away_score"], errors="coerce")

dst.parent.mkdir(parents=True, exist_ok=True)
out.to_csv(dst, index=False)
print(f"Wrote {dst} with {len(out):,} rows")

