#!/usr/bin/env python
import argparse, re, sys, math, time, random
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
import requests

# ---------- Team normalization ----------
NFL_ALIASES = {
    "49ers": ["49ers","san francisco","sf","sfo","niners"],
    "Bears": ["bears","chicago","chi"],
    "Bengals": ["bengals","cincinnati","cin"],
    "Bills": ["bills","buffalo","buf"],
    "Broncos": ["broncos","denver","den"],
    "Browns": ["browns","cleveland","cle"],
    "Buccaneers": ["buccaneers","bucs","tampa bay","tb","tampa"],
    "Cardinals": ["cardinals","arizona","ari","cards"],
    "Chargers": ["chargers","los angeles chargers","la chargers","lac","san diego chargers","sd"],
    "Chiefs": ["chiefs","kansas city","kc"],
    "Colts": ["colts","indianapolis","ind"],
    "Commanders": ["commanders","washington","wsh","was","redskins"],
    "Cowboys": ["cowboys","dallas","dal"],
    "Dolphins": ["dolphins","miami","mia"],
    "Eagles": ["eagles","philadelphia","phi"],
    "Falcons": ["falcons","atlanta","atl"],
    "Giants": ["giants","new york giants","nyg"],
    "Jaguars": ["jaguars","jags","jacksonville","jax"],
    "Jets": ["jets","new york jets","nyj"],
    "Lions": ["lions","detroit","det"],
    "Packers": ["packers","green bay","gb"],
    "Panthers": ["panthers","carolina","car"],
    "Patriots": ["patriots","new england","ne","nwe"],
    "Raiders": ["raiders","las vegas","lv","oakland","oak"],
    "Rams": ["rams","los angeles rams","la rams","lar","st. louis rams","st louis rams"],
    "Ravens": ["ravens","baltimore","bal"],
    "Saints": ["saints","new orleans","no","nor"],
    "Seahawks": ["seahawks","seattle","sea"],
    "Steelers": ["steelers","pittsburgh","pit"],
    "Texans": ["texans","houston","hou"],
    "Titans": ["titans","tennessee","ten"],
    "Vikings": ["vikings","minnesota","min"],
}
ALIAS_TO_TEAM = {a: canon for canon, aliases in NFL_ALIASES.items() for a in aliases}

def _teamify(txt: str):
    t = (txt or "").strip().lower()
    if not t: return None
    hits = [ALIAS_TO_TEAM[a] for a in ALIAS_TO_TEAM if a in t]
    if len(set(hits)) == 1:
        return hits[0]
    # fallback to word-boundary exact alias
    for canon, aliases in NFL_ALIASES.items():
        for a in aliases:
            if re.search(rf"\b{re.escape(a)}\b", t):
                return canon
    return None

# ---------- Fetch with browser-like headers ----------
def fetch(url: str) -> str:
    ses = requests.Session()
    ses.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
        "Cache-Control": "no-cache",
    })
    last = None
    for i in range(5):
        r = ses.get(url, timeout=30)
        last = r
        if r.status_code == 200:
            return r.text
        if r.status_code in (403, 429):
            time.sleep(2 + i + random.random())
            continue
        r.raise_for_status()
    raise requests.HTTPError(f"{last.status_code} fetching {url}")

# ---------- Helpers ----------
MATCH_RE = re.compile(r"(?P<a>[A-Za-z\.\s'\-]+?)\s+(?P<sep>at|@|vs\.?|v\.)\s+(?P<h>[A-Za-z\.\s'\-]+)", re.IGNORECASE)
SPREAD_RE = re.compile(r"(?:open(?:ing)?\s*)?(?:line|spread)[:\s]*([+-]?\d+(?:\.\d+)?)", re.IGNORECASE)
PK_RE = re.compile(r"\bP(?:K|ick)\b", re.IGNORECASE)

def _to_float(x):
    try: return float(x)
    except: return None

def _estimate_ml_from_spread(home_spread: float):
    if home_spread is None: return (None, None)
    s = abs(home_spread)
    p = 1/(1+math.exp(-(s-3.0)/1.6))
    p = 0.5 + (p-0.5) * 1.15
    p_home = p if home_spread < 0 else 1-p
    def prob_to_ml(q):
        q = max(min(q, 0.995), 0.005)
        return (-round(100*q/(1-q))) if q >= 0.5 else (round(100*(1-q)/q))
    return prob_to_ml(p_home), prob_to_ml(1-p_home)

def _season_from_url(url: str):
    m = re.search(r"/(20\d{2})-", url)
    return int(m.group(1)) if m else None

def _week_from_text(txt: str):
    m = re.search(r"week\s+(\d{1,2})", txt, re.IGNORECASE)
    return int(m.group(1)) if m else None

def _rows_from_table(df: pd.DataFrame, season_hint):
    rows = []
    lower = {c.lower(): c for c in df.columns}
    # Guess columns
    a_col = lower.get("away") or lower.get("team") or next(iter(lower.values()))
    h_col = lower.get("home") or (list(lower.values())[1] if len(lower)>1 else None)
    spread_col = None
    for cand in ["open","opening","open spread","opening spread","spread","line"]:
        if cand in lower: spread_col = lower[cand]; break
    for _, r in df.iterrows():
        a = _teamify(str(r.get(a_col, "")))
        h = _teamify(str(r.get(h_col, ""))) if h_col else None
        if not a or not h: continue
        sp = _to_float(r.get(spread_col)) if spread_col else None
        if sp is not None and sp > 0:
            sp = -sp  # make home perspective (negative = home favored)
        rows.append({"season": season_hint, "away": a, "home": h, "spread_open": sp})
    return rows

def parse_html(html: str, src_name="(html)", estimate_ml=False):
    out = []
    soup = BeautifulSoup(html, "html.parser")

    # 1) Tables first
    try:
        tables = pd.read_html(html)
        for t in tables:
            out += _rows_from_table(t, season_hint=None)
    except Exception:
        pass

    # 2) Text fallback
    text = soup.get_text(" ", strip=True)
    blocks = re.split(r"\s{2,}", text)
    for blk in blocks:
        m = MATCH_RE.search(blk)
        if not m: continue
        a = _teamify(m.group("a")); h = _teamify(m.group("h"))
        if not a or not h: continue
        sp = None
        msp = SPREAD_RE.search(blk)
        if msp: sp = _to_float(msp.group(1))
        elif PK_RE.search(blk): sp = 0.0
        if sp is not None:
            away_pos = blk.lower().find(m.group("a").lower())
            if away_pos >= 0 and "+" in blk[away_pos:away_pos+40] and sp > 0:
                sp = -sp
        out.append({"season": None, "away": a, "home": h, "spread_open": sp})

    # Attach week/season if text hints exist
    week_hint = _week_from_text(text)
    season_hint = None
    m = re.search(r"(20\d{2})", text)
    if m: season_hint = int(m.group(1))
    for r in out:
        r["week"] = week_hint
        r["season"] = r["season"] or season_hint

    if estimate_ml:
        for r in out:
            hml, aml = _estimate_ml_from_spread(r.get("spread_open"))
            r["ml_home_est"] = hml
            r["ml_away_est"] = aml

    df = pd.DataFrame(out)
    if df.empty:
        return []
    df["key_swha"] = df["season"].astype("Int64").astype(str) + "|" + df["week"].astype("Int64").astype(str) + "|" + df["home"] + "|" + df["away"]
    df = df.sort_values(["season","week","home","away"]).drop_duplicates(subset=["key_swha"])
    return df.to_dict("records")

def parse_url(url: str, estimate_ml=False):
    html = fetch(url)
    # Prefer season from URL when present
    season_hint = _season_from_url(url)
    rows = parse_html(html, src_name=url, estimate_ml=estimate_ml)
    if season_hint is not None:
        for r in rows:
            r["season"] = r["season"] or season_hint
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", nargs="+", help="One or more TheLines URLs")
    ap.add_argument("--files", nargs="+", help="Local HTML files saved from TheLines")
    ap.add_argument("--estimate-ml", action="store_true", help="Estimate moneylines from spread")
    args = ap.parse_args()

    sources = []
    if args.urls:  sources += [("url", u) for u in args.urls]
    if args.files: sources += [("file", f) for f in args.files]
    if not sources:
        ap.error("Provide --urls and/or --files")

    all_rows = []
    for typ, src in sources:
        try:
            if typ == "url":
                rows = parse_url(src, estimate_ml=args.estimate_ml)
            else:
                html = Path(src).read_text(encoding="utf-8", errors="ignore")
                rows = parse_html(html, src_name=src, estimate_ml=args.estimate_ml)
            print(f"[ok] {src} rows={len(rows)}")
            all_rows += rows
        except Exception as e:
            print(f"[err] {src} -> {e}", file=sys.stderr)

    if not all_rows:
        print("[warn] No rows parsed.")
        sys.exit(0)

    out = pd.DataFrame(all_rows)
    out["season"] = pd.to_numeric(out["season"], errors="coerce").astype("Int64")
    out["week"]   = pd.to_numeric(out["week"], errors="coerce").astype("Int64")

    exports = Path("exports"); exports.mkdir(parents=True, exist_ok=True)
    dest = exports / "historical_odds_thelines.csv"
    if dest.exists():
        old = pd.read_csv(dest)
        out = pd.concat([old, out], ignore_index=True)
    out = out.drop_duplicates(subset=["key_swha"]).sort_values(["season","week","home","away"])
    out.to_csv(dest, index=False)
    print(f"[write] {dest} rows={len(out)}")

if __name__ == "__main__":
    main()

