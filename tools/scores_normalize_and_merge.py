import os, re, sys, pandas as pd
pd.options.mode.copy_on_write = True
repo = r"C:\Projects\edge-finder"; exports = os.path.join(repo,"exports"); os.makedirs(exports, exist_ok=True)
out  = os.path.join(exports,"scores.csv")

# Target abbreviations used by edges
TARGET = {'ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET','GB','HOU','IND','JAC','KC','LV','LAC','LAR','MIA','MIN','NE','NO','NYG','NYJ','PHI','PIT','SEA','SF','TB','TEN','WSH'}

# Aliases (codes -> target)
ALIAS = {
  # legacy/alt codes
  'ARZ':'ARI','NWE':'NE','NEP':'NE','NOR':'NO','NOS':'NO','TAM':'TB','TBB':'TB',
  'KAN':'KC','KCC':'KC','SFO':'SF','SFN':'SF','GNB':'GB','STL':'LAR','SD':'LAC','SDG':'LAC',
  'OAK':'LV','RAI':'LV','WAS':'WSH','WFT':'WSH','LVR':'LV','JAX':'JAC','CLV':'CLE',
  # odd dataset codes
  'LA':'LAR','HOU TEXANS':'HOU','BAL RAVENS':'BAL'
}

# Full-name -> target abbr
NAME = {
 'ARIZONA CARDINALS':'ARI','ATLANTA FALCONS':'ATL','BALTIMORE RAVENS':'BAL','BUFFALO BILLS':'BUF',
 'CAROLINA PANTHERS':'CAR','CHICAGO BEARS':'CHI','CINCINNATI BENGALS':'CIN','CLEVELAND BROWNS':'CLE',
 'DALLAS COWBOYS':'DAL','DENVER BRONCOS':'DEN','DETROIT LIONS':'DET','GREEN BAY PACKERS':'GB','GREEN BAY':'GB','PACKERS':'GB',
 'HOUSTON TEXANS':'HOU','INDIANAPOLIS COLTS':'IND','JACKSONVILLE JAGUARS':'JAC','JAGUARS':'JAC',
 'KANSAS CITY CHIEFS':'KC','LAS VEGAS RAIDERS':'LV','OAKLAND RAIDERS':'LV','RAIDERS':'LV',
 'LOS ANGELES CHARGERS':'LAC','SAN DIEGO CHARGERS':'LAC','CHARGERS':'LAC',
 'LOS ANGELES RAMS':'LAR','ST LOUIS RAMS':'LAR','SAINT LOUIS RAMS':'LAR','RAMS':'LAR',
 'MIAMI DOLPHINS':'MIA','MINNESOTA VIKINGS':'MIN','NEW ENGLAND PATRIOTS':'NE','PATRIOTS':'NE',
 'NEW ORLEANS SAINTS':'NO','SAINTS':'NO','NEW YORK GIANTS':'NYG','GIANTS':'NYG','NEW YORK JETS':'NYJ','JETS':'NYJ',
 'PHILADELPHIA EAGLES':'PHI','PITTSBURGH STEELERS':'PIT','SEATTLE SEAHAWKS':'SEA',
 'SAN FRANCISCO 49ERS':'SF','49ERS':'SF','TAMPA BAY BUCCANEERS':'TB','BUCCANEERS':'TB','BUCS':'TB',
 'TENNESSEE TITANS':'TEN','WASHINGTON COMMANDERS':'WSH','WASHINGTON FOOTBALL TEAM':'WSH','WASHINGTON REDSKINS':'WSH','COMMANDERS':'WSH'
}

def to_abbr(s):
    if pd.isna(s): return pd.NA
    x = str(s).upper().strip()
    x = x.replace('.', '').replace('-', ' ')
    x = re.sub(r'\s+', ' ', x)
    # direct hits
    if x in TARGET: return x
    if x in ALIAS:  return ALIAS[x]
    if x in NAME:   return NAME[x]
    # sometimes dataset uses city only
    CITY = {
      'ARIZONA':'ARI','ATLANTA':'ATL','BALTIMORE':'BAL','BUFFALO':'BUF','CAROLINA':'CAR',
      'CHICAGO':'CHI','CINCINNATI':'CIN','CLEVELAND':'CLE','DALLAS':'DAL','DENVER':'DEN',
      'DETROIT':'DET','GREEN BAY':'GB','HOUSTON':'HOU','INDIANAPOLIS':'IND','JACKSONVILLE':'JAC',
      'KANSAS CITY':'KC','LAS VEGAS':'LV','OAKLAND':'LV','SAN DIEGO':'LAC','LOS ANGELES CHARGERS':'LAC',
      'LOS ANGELES RAMS':'LAR','LOS ANGELES':'LAR','MIAMI':'MIA','MINNESOTA':'MIN','NEW ENGLAND':'NE',
      'NEW ORLEANS':'NO','NEW YORK GIANTS':'NYG','NEW YORK JETS':'NYJ','PHILADELPHIA':'PHI',
      'PITTSBURGH':'PIT','SEATTLE':'SEA','SAN FRANCISCO':'SF','TAMPA BAY':'TB','TENNESSEE':'TEN','WASHINGTON':'WSH'
    }
    if x in CITY: return CITY[x]
    # last resort: 3–4 letters keep, map common 3-letter to target
    if len(x) in (2,3,4):
        return ALIAS.get(x, x)
    return pd.NA

def read_flex(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx",".xls"):
        for eng in ("openpyxl", None):
            try: return pd.read_excel(path, engine=eng) if eng else pd.read_excel(path)
            except Exception: pass
        return pd.DataFrame()
    for kw in [dict(), dict(sep="\t"), dict(sep="|"), dict(sep=";")]:
        try: return pd.read_csv(path, low_memory=False, **kw)
        except Exception: pass
    return pd.DataFrame()

def lower_cols(df):
    df = df.copy(); df.columns = [c.strip().lower() for c in df.columns]; return df

def pick(df, cols):
    for c in cols:
        if c in df.columns: return df[c]
    return pd.Series([pd.NA]*len(df))

def to_int(s):
    return pd.to_numeric(pd.Series(s).astype(str).str.replace(r"[^\d-]","", regex=True), errors="coerce").astype("Int64")

def normalize(df):
    if df.empty: return df
    d = lower_cols(df)
    season = to_int(pick(d, ["season","year","yr"]))
    week   = to_int(pick(d, ["week","wk"]))
    h_raw  = pick(d, ["home_abbrev","home","home_team","hometeam","team home abbrev","home team"])
    a_raw  = pick(d, ["away_abbrev","away","away_team","awayteam","team away abbrev","away team"])
    hs     = to_int(pick(d, ["home_score","homesc","home_pts","team home score","home score","homescore"," team home score"]))
    as_    = to_int(pick(d, ["away_score","awaysc","away_pts","team away score","away score","awayscore"," team away score"]))
    kt     = pick(d, ["kickoff_ts","kickoff","game_date","start_time","gamedate","datetime","date","gameid","id"])
    home = h_raw.map(to_abbr)
    away = a_raw.map(to_abbr)
    dt   = pd.to_datetime(kt, errors="coerce")
    out = pd.DataFrame({"season":season,"week":week,"home":home,"away":away,"home_score":hs,"away_score":as_,"kickoff_ts":dt})
    out = out.dropna(subset=["season","week","home","away","home_score","away_score"])
    out["kickoff_ts"] = out["kickoff_ts"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    return out

# collect candidates under repo (any file with 2017..2025 & score/game in name)
frames = []
for root,_,files in os.walk(repo):
    for f in files:
        fn = f.lower()
        if ("score" in fn or "game" in fn):
            p = os.path.join(root,f)
            n = normalize(read_flex(p))
            if not n.empty:
                frames.append(n)

merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["season","week","home","away","home_score","away_score","kickoff_ts"])
if not merged.empty:
    merged["key"] = merged["season"].astype(str)+"|"+merged["week"].astype(str)+"|"+merged["home"]+"|"+merged["away"]
    merged["kt"]  = pd.to_datetime(merged["kickoff_ts"], errors="coerce")
    merged = (merged.sort_values(["key","kt"])
                    .groupby("key", as_index=False)
                    .tail(1)
                    .drop(columns=["key","kt"]))
    merged = merged.sort_values(["season","week","home","away"])
merged.to_csv(out, index=False)
print(f"[ok] scores.csv rows={len(merged)} -> {out}")

