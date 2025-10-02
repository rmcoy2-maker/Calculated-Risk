import argparse, datetime as dt, re
from pathlib import Path
import pandas as pd

PATTERNS_WEEK = [
    re.compile(r'(?i)\bREG(?:ULAR)?\s*[-_ ]?(\d{1,2})\b'),
    re.compile(r'(?i)\bW(?:EEK)?\s*[-_ ]?(\d{1,2})\b'),
    re.compile(r'(?i)[_-]W?(\d{1,2})[_-]'),              # ...-12-... or ...-W3-...
]
PATTERN_YEAR = re.compile(r'\b(19\d{2}|20\d{2})\b')

def pick_first(patterns, text):
    if not isinstance(text, str): return None
    for pat in patterns:
        m = pat.search(text)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
    return None

def infer_season(row):
    # priority: season -> game_id -> ts/placed_at year
    season = row.get("season")
    if pd.notna(season):
        s = str(season).strip()
        if PATTERN_YEAR.fullmatch(s):
            return s
    gid = row.get("game_id")
    if isinstance(gid, str):
        m = PATTERN_YEAR.search(gid)
        if m: return m.group(1)
    for date_col in ("ts", "placed_at"):
        if date_col in row and pd.notna(row[date_col]):
            try:
                d = pd.to_datetime(row[date_col], errors="coerce")
                if pd.notna(d): return str(int(d.year))
            except Exception:
                pass
    return None

def infer_week(row):
    # priority: explicit week -> game_id -> ref -> market
    wk = row.get("week")
    try:
        wk_num = int(wk)
        if 1 <= wk_num <= 22: return wk_num
    except Exception:
        pass
    for col in ("game_id", "ref", "market"):
        if col in row:
            wk_num = pick_first(PATTERNS_WEEK, str(row[col]))
            if wk_num is not None:
                return max(1, min(22, wk_num))
    return None

def fix_file(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        print(f"SKIP: {path.name} (missing/empty)")
        return
    print(f"LOAD: {path}")
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    before_missing = df.get("week").isna().sum() if "week" in df.columns else len(df)
    # Ensure columns exist for uniform operations
    for c in ("season","week","game_id","ref","market","ts","placed_at"):
        if c not in df.columns:
            df[c] = None

    # infer
    df["season"] = df.apply(infer_season, axis=1)
    df["week"]   = df.apply(infer_week,   axis=1)

    # clamp/clean
    df["week"] = pd.to_numeric(df["week"], errors="coerce").clip(1,22)
    df["week"] = df["week"].astype("Int64")
    df["season"] = df["season"].astype(str).where(df["season"].notna(), None)

    after_missing = df["week"].isna().sum()
    fixed = int(before_missing) - int(after_missing)
    print(f"   rows: {len(df):>6} | week filled: {fixed:>5} | still missing: {after_missing:>5}")

    # Backup + save
    bkpdir = path.parent / "backup"
    bkpdir.mkdir(exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path.rename(bkpdir / f"{path.stem}.{ts}.bak.csv")
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"   wrote: {path}\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-d", "--dir", default=".", help="exports directory")
    args = ap.parse_args()
    d = Path(args.dir)
    for name in ("edges.csv","bets_log.csv","parlays.csv"):
        fix_file(d / name)

if __name__ == "__main__":
    main()




