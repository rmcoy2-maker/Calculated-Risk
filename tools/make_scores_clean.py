import os, re, pandas as pd
from datetime import datetime

exports = os.path.join("exports")
srcs = [
    os.path.join(exports, "2017-2025_scores.csv"),
    os.path.join(exports, "scores.csv"),
]
src = next((p for p in srcs if os.path.exists(p)), None)
if not src:
    raise SystemExit("No scores source found in exports/")

df = pd.read_csv(src, low_memory=False)

# Normalize column names
df.columns = [re.sub(r"[\s,]+", "_", str(c)).strip("_") for c in df.columns]

# Two common schemas:
# A) Season, Week, HomeTeam, AwayTeam, HomeScore, AwayScore, Date(MM/DD)
# B) week, home_team, away_team, home_score, away_score (already “clean”, may be missing season)
# Handle both.

def to_full(thing:str)->str:
    s = str(thing).strip().upper()
    # Map tails (VIKINGS -> MINNESOTA VIKINGS, RAMS -> LOS ANGELES RAMS, etc.)
    tails = {
        "CARDINALS":"ARIZONA CARDINALS","FALCONS":"ATLANTA FALCONS","RAVENS":"BALTIMORE RAVENS","BILLS":"BUFFALO BILLS",
        "PANTHERS":"CAROLINA PANTHERS","BEARS":"CHICAGO BEARS","BENGALS":"CINCINNATI BENGALS","BROWNS":"CLEVELAND BROWNS",
        "COWBOYS":"DALLAS COWBOYS","BRONCOS":"DENVER BRONCOS","LIONS":"DETROIT LIONS","PACKERS":"GREEN BAY PACKERS",
        "TEXANS":"HOUSTON TEXANS","COLTS":"INDIANAPOLIS COLTS","JAGUARS":"JACKSONVILLE JAGUARS","CHIEFS":"KANSAS CITY CHIEFS",
        "CHARGERS":"LOS ANGELES CHARGERS","RAMS":"LOS ANGELES RAMS","RAIDERS":"LAS VEGAS RAIDERS",
        "DOLPHINS":"MIAMI DOLPHINS","VIKINGS":"MINNESOTA VIKINGS","PATRIOTS":"NEW ENGLAND PATRIOTS","SAINTS":"NEW ORLEANS SAINTS",
        "GIANTS":"NEW YORK GIANTS","JETS":"NEW YORK JETS","EAGLES":"PHILADELPHIA EAGLES","STEELERS":"PITTSBURGH STEELERS",
        "SEAHAWKS":"SEATTLE SEAHAWKS","49ERS":"SAN FRANCISCO 49ERS","BUCCANEERS":"TAMPA BAY BUCCANEERS",
        "TITANS":"TENNESSEE TITANS","COMMANDERS":"WASHINGTON COMMANDERS",
        # legacy/older city names for historical data:
        "REDSKINS":"WASHINGTON COMMANDERS","WASHINGTON FOOTBALL TEAM":"WASHINGTON COMMANDERS",
        "OAKLAND RAIDERS":"OAKLAND RAIDERS","SAN DIEGO CHARGERS":"SAN DIEGO CHARGERS","ST LOUIS RAMS":"ST LOUIS RAMS",
    }
    # If already full, keep; else tail-map:
    return tails.get(s, s)

def abbr_to_full(s:str)->str:
    s = str(s).strip().upper()
    m = {
        "ARI":"ARIZONA CARDINALS","ATL":"ATLANTA FALCONS","BAL":"BALTIMORE RAVENS","BUF":"BUFFALO BILLS",
        "CAR":"CAROLINA PANTHERS","CHI":"CHICAGO BEARS","CIN":"CINCINNATI BENGALS","CLE":"CLEVELAND BROWNS",
        "DAL":"DALLAS COWBOYS","DEN":"DENVER BRONCOS","DET":"DETROIT LIONS","GB":"GREEN BAY PACKERS",
        "HOU":"HOUSTON TEXANS","IND":"INDIANAPOLIS COLTS","JAX":"JACKSONVILLE JAGUARS","KC":"KANSAS CITY CHIEFS",
        "LAC":"LOS ANGELES CHARGERS","LAR":"LOS ANGELES RAMS","LV":"LAS VEGAS RAIDERS",
        "MIA":"MIAMI DOLPHINS","MIN":"MINNESOTA VIKINGS","NE":"NEW ENGLAND PATRIOTS","NO":"NEW ORLEANS SAINTS",
        "NYG":"NEW YORK GIANTS","NYJ":"NEW YORK JETS","PHI":"PHILADELPHIA EAGLES","PIT":"PITTSBURGH STEELERS",
        "SEA":"SEATTLE SEAHAWKS","SF":"SAN FRANCISCO 49ERS","TB":"TAMPA BAY BUCCANEERS",
        "TEN":"TENNESSEE TITANS","WAS":"WASHINGTON COMMANDERS",
        "SD":"SAN DIEGO CHARGERS","STL":"ST LOUIS RAMS","OAK":"OAKLAND RAIDERS","WSH":"WASHINGTON COMMANDERS","JAC":"JACKSONVILLE JAGUARS",
    }
    return m.get(s, s)

if {"Season","Week","HomeTeam","AwayTeam","HomeScore","AwayScore"} <= set(df.columns):
    # Schema A (2017-2025_scores.csv)
    out = pd.DataFrame()
    out["season"] = pd.to_numeric(df["Season"], errors="coerce")
    # Parse "Week" like "Week 1", "Wild Card", "Preseason Week 1"
    def parse_week(w):
        s = str(w).upper()
        m = re.search(r"(\d+)", s)
        return int(m.group(1)) if m else None
    out["week"] = df["Week"].map(parse_week)
    # Teams may be tails ("Vikings") — map to full:
    out["home_team"] = df["HomeTeam"].map(to_full)
    out["away_team"] = df["AwayTeam"].map(to_full)
    out["home_score"] = pd.to_numeric(df["HomeScore"], errors="coerce")
    out["away_score"] = pd.to_numeric(df["AwayScore"], errors="coerce")
    # Make a real date if Date is MM/DD; use Season as year
    if "Date" in df.columns:
        def mkdate(md, yr):
            try:
                md = str(md).strip()
                if not md or md.lower()=="nan": return None
                m, d = md.split("/")
                # NFL season months: Aug-Jan (Jan is next calendar year)
                m = int(m); d = int(d); y = int(yr)
                if m==1: y = y+1
                return datetime(y, m, d).date()
            except Exception:
                return None
        out["date"] = [mkdate(md, yr) for md, yr in zip(df["Date"], out["season"])]
    out = out.dropna(subset=["home_team","away_team"]).reset_index(drop=True)

elif {"week","home_team","away_team","home_score","away_score"} <= set(df.columns):
    # Schema B (already cleaned but missing season + abbreviations)
    out = df.copy()
    # Expand abbreviations to full names
    out["home_team"] = out["home_team"].map(abbr_to_full)
    out["away_team"] = out["away_team"].map(abbr_to_full)
    # Keep week numeric if possible
    out["week"] = pd.to_numeric(out["week"], errors="coerce")
    # Try to infer 'season' from an optional 'season' column if present
    if "season" in out.columns and out["season"].notna().any():
        out["season"] = pd.to_numeric(out["season"], errors="coerce")
    else:
        out["season"] = pd.NA  # still useful for team-only joins

else:
    raise SystemExit(f"Unexpected schema in {src}; columns: {list(df.columns)}")

# Final polish
for c in ("home_team","away_team"):
    out[c] = out[c].astype(str).str.strip().str.upper()

keep = [c for c in ("season","week","date","home_team","away_team","home_score","away_score") if c in out.columns]
out = out[keep]
out.to_csv(os.path.join(exports, "scores_clean.csv"), index=False, encoding="utf-8-sig")
print(f"[ok] wrote exports/scores_clean.csv rows={len(out)} cols={list(out.columns)} from {os.path.basename(src)}")

