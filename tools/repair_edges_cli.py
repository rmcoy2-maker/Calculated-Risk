# tools/repair_edges_cli.py
# Make a clean edges file with game_id (date_away_AT_home) and safe SW fallback.

from pathlib import Path
import pandas as pd

# --- paths ---
ROOT = Path(r"C:\Projects\edge-finder")
EDGES_IN  = ROOT / "exports" / "edges_graded_full_normalized_std.csv"
SCORES_IN = ROOT / "exports" / "scores_normalized.csv"        # works even if it's "one long column"
EDGES_OUT = ROOT / "exports" / "edges_repaired.csv"

EDGES_OUT.parent.mkdir(parents=True, exist_ok=True)

# --- load edges ---
edges = pd.read_csv(EDGES_IN, low_memory=False, encoding="utf-8-sig")
edges.columns = [c.strip().lower() for c in edges.columns]

# --- load scores, robust to "single-column" CSV ---
try:
    scores = pd.read_csv(SCORES_IN, sep=",", encoding="utf-8-sig")
    if scores.shape[1] == 1:
        raise ValueError("scores parsed as single column")
except Exception:
    raw = pd.read_csv(SCORES_IN, header=None, encoding="utf-8-sig")
    header = raw.iloc[0, 0].split(",")
    data   = raw.iloc[1:, 0].str.split(",", expand=True)
    scores = pd.DataFrame(data.values, columns=[h.strip().lower() for h in header])

scores.columns = [c.strip().lower() for c in scores.columns]

# --- normalize key types for joins ---
for df in (edges, scores):
    if "season" in df: df["season"] = df["season"].astype(str)
    if "week"   in df: df["week"]   = df["week"].astype(str)

# --- build nick & date on scores ---
def _nickify(x: str) -> str:
    ALIAS = {
        "REDSKINS":"COMMANDERS","WASHINGTON":"COMMANDERS","FOOTBALL":"COMMANDERS","WFT":"COMMANDERS",
        "OAKLAND":"RAIDERS","LV":"RAIDERS","LVR":"RAIDERS","LAS":"RAIDERS","VEGAS":"RAIDERS",
        "SD":"CHARGERS","SAN":"CHARGERS","DIEGO":"CHARGERS","LA":"CHARGERS","LOS":"CHARGERS","ANGELES":"CHARGERS",
        "ST":"RAMS","LOUIS":"RAMS","NINERS":"49ERS","NO":"SAINTS","NOLA":"SAINTS","JAX":"JAGUARS",
        "NE":"PATRIOTS","N.E.":"PATRIOTS","NYJ":"JETS","NYG":"GIANTS","TB":"BUCCANEERS","TBAY":"BUCCANEERS","KC":"CHIEFS",
        "S.D.":"CHARGERS","L.A.":"RAMS",
    }
    x = (str(x) or "").strip().upper()
    if not x: return ""
    last = x.split()[-1]
    return ALIAS.get(last, last)

scores["_home_nick"] = scores["home_team"].astype(str).map(_nickify)
scores["_away_nick"] = scores["away_team"].astype(str).map(_nickify)
scores["_date_iso"]  = pd.to_datetime(scores["date"], errors="coerce").dt.date.astype("string")

# --- merge Season+Week to “steal” nicks & date (avoid suffix traps) ---
steal = scores[["season","week","_home_nick","_away_nick","_date_iso"]].drop_duplicates()
repaired = edges.merge(steal, on=["season","week"], how="left", suffixes=("", "_sc"))
if "_date_iso_sc" in repaired:
    repaired["_date_iso"] = repaired["_date_iso_sc"]
    repaired = repaired.drop(columns=["_date_iso_sc"])

# --- build stable game_id (use date when present, else SW surrogate) ---
def make_gid(r):
    date = str(r.get("_date_iso") or "").strip()
    away = str(r.get("_away_nick") or "").strip()
    home = str(r.get("_home_nick") or "").strip()
    if date and date.upper() not in {"NA","<NA>"}:
        return f"{date}_{away}_AT_{home}"
    season = str(r.get("season") or "").strip()
    week   = str(r.get("week") or "").strip()
    sw = f"SW-{season}-{week}" if season and week else "SW-NA-NA"
    return f"{sw}_{away}_AT_{home}"

repaired["game_id"] = repaired.apply(make_gid, axis=1)

# --- save ---
repaired.to_csv(EDGES_OUT, index=False, encoding="utf-8-sig")
print("✅ Wrote repaired file to:", EDGES_OUT)
print(repaired[["_date_iso","_away_nick","_home_nick","game_id"]].head(10))

