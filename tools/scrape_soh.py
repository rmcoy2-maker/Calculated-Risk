import os, re, time, requests
import numpy as np
import pandas as pd

OUT_DIR = r"C:\Projects\edge-finder\exports"
MASTER  = os.path.join(OUT_DIR, "soh_edges_1999_2016.csv")
os.makedirs(OUT_DIR, exist_ok=True)

def american_to_prob(o):
    try:
        o = int(str(o).replace(",", "").strip())
    except:
        return np.nan
    if o > 0:  return 100.0/(o+100.0)
    if o < 0:  return abs(o)/(abs(o)+100.0)
    return np.nan

def find_odds_table(html_tables):
    """
    Given list of dataframes from pd.read_html, pick the one that looks like
    the NFL schedule/odds (must have visitor+home columns).
    """
    for df in html_tables:
        cols = [str(c).strip().lower() for c in df.columns]
        if any("visitor" in c or "away" in c for c in cols) and any("home" in c for c in cols):
            return df
    return None

def pick_col(cols, *cands):
    for cand in cands:
        if cand in cols:
            return cand
    return None

def to_int_ml(x):
    s = str(x).strip().lower().replace(",", "")
    if s in {"", "nan", "pk", "pick"}: return np.nan
    if re.fullmatch(r"[+-]?\d+", s):
        try: return int(s)
        except: return np.nan
    return np.nan

def parse_season(year, sleep=0.8, save_raw=True):
    url = f"https://www.sportsoddshistory.com/nfl-game-odds/?y={year}"
    print(f"[SOH] {year} -> {url}")
    r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()

    # parse every table; pick likely odds table
    tables = pd.read_html(r.text)
    if not tables:
        print(f"[SOH] {year}: no tables found")
        return pd.DataFrame()

    df = find_odds_table(tables)
    if df is None:
        print(f"[SOH] {year}: no suitable odds table (no Visitor/Home columns)")
        return pd.DataFrame()

    if save_raw:
        raw_path = os.path.join(OUT_DIR, f"soh_raw_{year}.csv")
        df.to_csv(raw_path, index=False)

    df.columns = [str(c).strip().lower() for c in df.columns]
    cols = df.columns.tolist()

    # likely column names (SOH varies by season)
    wk_col  = pick_col(cols, "week", "wk")
    vis_col = pick_col(cols, "visitor", "away", "team")
    hom_col = pick_col(cols, "home")
    # moneylines for visitor/home
    vml_col = pick_col(cols, "visitor ml", "vis ml", "away ml", "ml", "moneyline", "line ml", "ml1")
    hml_col = pick_col(cols, "home ml", "ml2", "moneyline2", "home moneyline")

    # some seasons put ML into a single column—if so, we can't split home/away reliably
    if vml_col is None and hml_col is None:
        # try to infer from any column that looks like an ML for two teams—skip if unclear
        # you still get spread-only seasons (we skip those for ML edges)
        pass

    # drop repeated header rows (table sometimes includes header in body)
    drop_mask = pd.Series(False, index=df.index)
    for c in (hom_col, vis_col):
        if c is not None:
            drop_mask |= df[c].astype(str).str.contains("home", case=False, na=False)
            drop_mask |= df[c].astype(str).str.contains("visitor|away", case=False, na=False)
    df = df[~drop_mask].copy()

    # a small helper to coerce week
    def norm_week(x):
        s = str(x).strip()
        m = re.search(r"\d+", s)
        return int(m.group()) if m else np.nan

    out = []
    for _, row in df.iterrows():
        home = str(row.get(hom_col, "")).strip()
        away = str(row.get(vis_col, "")).strip()
        if not home or not away or home.lower()=="nan" or away.lower()=="nan":
            continue

        week = norm_week(row.get(wk_col, np.nan)) if wk_col else np.nan
        ml_home = to_int_ml(row.get(hml_col, np.nan)) if hml_col else np.nan
        ml_away = to_int_ml(row.get(vml_col, np.nan)) if vml_col else np.nan

        # emit two ML edges if present
        if not np.isnan(ml_home):
            out.append({
                "season": year,
                "week": week,
                "market": "moneyline",
                "odds": int(ml_home),
                "p_win": american_to_prob(ml_home),
                "team": home,
                "opponent": away,
                "ref": f"{year}-{home}-{away}-W{week}"
            })
        if not np.isnan(ml_away):
            out.append({
                "season": year,
                "week": week,
                "market": "moneyline",
                "odds": int(ml_away),
                "p_win": american_to_prob(ml_away),
                "team": away,
                "opponent": home,
                "ref": f"{year}-{away}-{home}-W{week}"
            })

    if not out:
        print(f"[SOH] {year}: parsed 0 ML rows. Columns seen: {cols}")
    else:
        print(f"[SOH] {year}: parsed {len(out)} ML rows. Columns: {cols}")
    time.sleep(sleep)
    return pd.DataFrame(out)

def main():
    years = list(range(1999, 2017))
    if os.path.exists(MASTER):
        os.remove(MASTER)
    all_rows = []
    for y in years:
        try:
            df = parse_season(y)
            if not df.empty:
                # save per-season for debug
                per_path = os.path.join(OUT_DIR, f"soh_edges_{y}.csv")
                df.to_csv(per_path, index=False)
                all_rows.append(df)
        except Exception as e:
            print(f"[SOH] {y}: ERROR {e}")

    if not all_rows:
        print("No season produced ML rows. Check the per-season raw CSVs and column logs above.")
        return
    big = pd.concat(all_rows, ignore_index=True)
    big.to_csv(MASTER, index=False)
    print(f"Wrote {MASTER} with {len(big)} rows.")

if __name__ == "__main__":
    main()

