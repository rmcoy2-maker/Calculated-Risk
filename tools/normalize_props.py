import pandas as pd, os, sys, math
src = r'exports\tmp\props_latest.csv'
dst = r'exports\tmp\props_latest_std.csv'
if not os.path.exists(src):
    raise SystemExit(f'[skip] missing {src}')
df = pd.read_csv(src)

alias = {
    'asof_ts': ['asof_ts','scraped_at','fetched_at','retrieved_at','ts','captured_at'],
    'book': ['book','sportsbook','site','bookmaker','sports_book'],
    'event_id': ['event_id','game_id','match_id','eventId','fixture_id'],
    'season': ['season','year'],
    'kickoff_ts': ['kickoff_ts','commence_time','start_time','game_time','kickoff'],
    'market': ['market','prop','prop_market','category','bet_type','betType','market_key'],
    'selection': ['selection','pick','side','choice','over_under','bet_selection'],
    'player_id': ['player_id','playerId','athlete_id','pid'],
    'line': ['line','value','handicap','points','total'],
    'price': ['price','odds','american_odds','american','us_odds','decimal_odds','decimal'],
}

def pick(target):
    for c in alias[target]:
        if c in df.columns: return c
    return None

cols = {t: pick(t) for t in alias if pick(t)}
need = ['asof_ts','book','event_id','season','kickoff_ts','market','selection','player_id','line','price']
work = pd.DataFrame({t: (df[cols[t]] if t in cols else pd.NA) for t in need})

for c in ['asof_ts','kickoff_ts']:
    work[c] = pd.to_datetime(work[c], errors='coerce', utc=True)
if work['season'].isna().all() and work['kickoff_ts'].notna().any():
    work['season'] = work['kickoff_ts'].dt.year

for c in ['book','market','selection']:
    work[c] = work[c].astype(str).str.strip()
work['selection'] = work['selection'].str.lower().map({'o':'over','over':'over','u':'under','under':'under'}).fillna(work['selection'])
work['line'] = pd.to_numeric(work['line'], errors='coerce')

price_raw = df[cols['price']] if 'price' in cols else pd.Series(pd.NA, index=df.index)
def dec_to_american(d):
    try: d = float(d)
    except: return pd.NA
    if not math.isfinite(d) or d <= 1.0: return pd.NA
    return 100*(d-1) if d >= 2.0 else -100/(d-1)
is_decimal = pd.to_numeric(price_raw, errors='coerce')
if is_decimal.notna().any() and ((is_decimal.between(1.01,20).mean() > 0.6) or is_decimal.between(1.01,20).all()):
    work['price'] = is_decimal.map(dec_to_american)
else:
    work['price'] = pd.to_numeric(price_raw, errors='coerce')

if work['player_id'].isna().all() and 'player' in df.columns:
    work['player_id'] = df['player'].astype(str).apply(lambda s: abs(hash(s)) % (10**9))

req = need
ok = pd.Series(True, index=work.index)
for r in req: ok &= work[r].notna()
out = work[ok].copy()

os.makedirs(os.path.dirname(dst), exist_ok=True)
out.to_csv(dst, index=False)
print(f'[ok] normalized -> {dst} rows={len(out)} of {len(df)}')

