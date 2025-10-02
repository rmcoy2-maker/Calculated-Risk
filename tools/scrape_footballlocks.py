import re, time, json, hashlib, math
from pathlib import Path
from typing import Optional, Tuple, List
import requests
from bs4 import BeautifulSoup
import pandas as pd

BASE = "https://www.footballlocks.com"
WEEK_PATHS = [f"/nfl_odds_week_{w}.html" for w in range(1,18)]  # regular season

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

TEAM_FIX = {
    "St. Louis Rams":"Los Angeles Rams","LA Rams":"Los Angeles Rams",
    "San Diego Chargers":"Los Angeles Chargers","LA Chargers":"Los Angeles Chargers",
    "Washington Redskins":"Washington Commanders","Washington Football Team":"Washington Commanders",
    "Oakland Raiders":"Las Vegas Raiders","Phoenix Cardinals":"Arizona Cardinals","Tennessee Oilers":"Tennessee Titans",
}

def norm_team(x:str)->str:
    s = re.sub(r"\s+"," ", str(x or "").strip())
    return TEAM_FIX.get(s, s)

def session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Referer": BASE + "/",
    })
    return s

def fetch_with_fallback(s: requests.Session, path: str) -> Tuple[str, str]:
    """Return (html, source_url). Try live site variations, then Wayback."""
    variants = [
        path,                       # /nfl_odds_week_1.html
        path.rstrip(".html") + "/", # /nfl_odds_week_1/
        path.rstrip(".html"),       # /nfl_odds_week_1
    ]
    last_err = None
    for v in variants:
        url = BASE + v
        try:
            r = s.get(url, timeout=20)
            if r.status_code == 200 and "Las Vegas NFL Odds" in r.text:
                return r.text, url
            last_err = f"{r.status_code} {r.reason}"
        except Exception as e:
            last_err = str(e)

    # Wayback fallback via CDX
    cdx_url = ("https://web.archive.org/cdx/search/cdx"
               f"?url=www.footballlocks.com{path}"
               "&output=json&filter=statuscode:200&collapse=digest&limit=1&from=2005&to=2025")
    try:
        cj = s.get(cdx_url, timeout=20, headers={"User-Agent": UA}).text
        data = json.loads(cj)
        # data[0] is header; pick first record if present
        if len(data) >= 2:
            # header may be ["timestamp","original",...]; we only requested timestamp,original by default order
            ts, orig = data[1][0], data[1][1]
            wb = f"https://web.archive.org/web/{ts}/{orig}"
            r = s.get(wb, timeout=25, headers={"User-Agent": UA})
            if r.status_code == 200:
                return r.text, wb
    except Exception as e:
        last_err = f"Wayback fail: {e}"

    raise RuntimeError(f"Could not fetch {path} (last_err={last_err})")

money_re = re.compile(r"([+-]?)\$\s*([0-9]+)")
def parse_ml(tok:str) -> Optional[int]:
    if not tok: return None
    m = money_re.search(tok.replace("−","-"))
    if not m: return None
    sign = -1 if m.group(1) == "-" else 1
    return sign * int(m.group(2))

def parse_week_html(html: str) -> List[dict]:
    # We parse from raw text; FootballLOCKS varies markup across years.
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    # Identify season blocks:
    blocks = list(re.finditer(r"Closing\s+Las Vegas NFL Odds From Week\s+(\d+),\s+(\d{4})", text, re.I))
    if not blocks:
        return []
    rows = []
    # find chunk ranges
    ends = [blocks[i+1].start() if i+1 < len(blocks) else len(text) for i in range(len(blocks))]
    for (m, end) in zip(blocks, ends):
        wk = int(m.group(1)); yr = int(m.group(2))
        chunk = text[m.end():end]

        # Typical lines (examples):
        # 9/8 1:03 ET At Cleveland -5.5 Tennessee 44.5 -$255 +$215
        # 9/6 8:20 ET At Philadelphia  PK  Atlanta 44 -$110 -$110
        line_re = re.compile(
            r"(?P<md>\d{1,2}/\d{1,2})\s+\d{1,2}:\d{2}\s*ET\s+"
            r"(?P<fav_at>At\s+)?(?P<fav>[A-Za-z\.\s]+?)\s+"
            r"(?P<spread>[-+]?\d+(?:\.\d+)?|PK|PICK)\s+"
            r"(?P<dog_at>At\s+)?(?P<dog>[A-Za-z\.\s]+?)\s+"
            r"(?P<total>\d+(?:\.\d+)?)\s+"
            r"(?P<ml_fav>[+-]?\$\s*\d+)\s+(?P<ml_dog>[+-]?\$\s*\d+)",
            re.I
        )

        for ln in chunk.splitlines():
            ln = ln.strip()
            m2 = line_re.search(ln)
            if not m2:
                continue
            md = m2.group("md")
            fav = m2.group("fav").strip()
            dog = m2.group("dog").strip()
            fav_at = bool(m2.group("fav_at"))
            dog_at = bool(m2.group("dog_at"))
            sp_raw = m2.group("spread").upper()
            tot_raw = m2.group("total")
            ml_f = parse_ml(m2.group("ml_fav"))
            ml_d = parse_ml(m2.group("ml_dog"))

            # Determine home/away from "At" marker
            if fav_at and not dog_at:
                home, away = fav, dog
                ml_home, ml_away = ml_f, ml_d
                spread = 0.0 if sp_raw in ("PK","PICK") else float(sp_raw)
                spread_home = -abs(spread)  # home is favorite
            elif dog_at and not fav_at:
                home, away = dog, fav
                ml_home, ml_away = ml_d, ml_f
                spread = 0.0 if sp_raw in ("PK","PICK") else float(spread := float(sp_raw))
                spread_home = abs(float(sp_raw))  # home is dog
            else:
                # ambiguous: assume first team is home favorite
                home, away = fav, dog
                ml_home, ml_away = ml_f, ml_d
                spread_home = 0.0 if sp_raw in ("PK","PICK") else -abs(float(sp_raw))

            total_close = float(tot_raw) if tot_raw else None
            # construct date using season year
            try:
                m_, d_ = [int(x) for x in md.split("/")]
                date_iso = f"{yr:04d}-{m_:02d}-{d_:02d}"
            except Exception:
                date_iso = None

            rows.append({
                "season": yr, "week": wk, "date": date_iso,
                "home": norm_team(home), "away": norm_team(away),
                "spread_close": spread_home, "total_close": total_close,
                "ml_home": ml_home, "ml_away": ml_away
            })
    return rows

def main():
    s = session()
    all_rows = []
    for path in WEEK_PATHS:
        try:
            html, src = fetch_with_fallback(s, path)
            parsed = parse_week_html(html)
            if parsed:
                all_rows.extend(parsed)
                print(f"[ok] {path} -> {len(parsed)} rows  ({src})")
            else:
                print(f"[warn] {path} -> 0 rows  ({src})")
            time.sleep(0.8)
        except Exception as e:
            print(f"[skip] {path}: {e}")

    if not all_rows:
        raise SystemExit("No rows scraped (both live and Wayback failed).")

    df = pd.DataFrame(all_rows).dropna(subset=["date","home","away"])
    df["game_id_unified"] = df.apply(
        lambda r: hashlib.md5(f"{r['date']}|{r['home']}|{r['away']}|NFL".encode()).hexdigest()[:12], axis=1
    )
    df = df.sort_values(["season","week","date","home","away"]).drop_duplicates("game_id_unified")

    out = Path("exports/historical_odds_footballlocks.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    df.to_csv("exports/historical_odds.csv", index=False)  # for your filler
    print(f"[done] wrote {out} and updated exports/historical_odds.csv; rows={len(df):,}")

if __name__ == "__main__":
    main()

