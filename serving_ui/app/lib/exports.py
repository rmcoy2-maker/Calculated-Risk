from pathlib import Path
from typing import Iterable, Optional, Tuple, List
import pandas as pd
HERE = Path(__file__).resolve()
ROOT = HERE
while ROOT and (not ((ROOT / 'serving').exists() and (ROOT / 'serving_ui').exists())):
    ROOT = ROOT.parent
ROOT = ROOT if ROOT and ROOT.exists() else HERE.parents[3]
REPO = ROOT
SU = REPO / 'serving_ui'
APP = SU / 'app'
SEARCH_ROOTS: Tuple[Path, ...] = (REPO / 'exports', SU / 'exports', APP / 'exports')
PATTERNS: Tuple[str, ...] = ('edges*.csv', 'picks*.csv')

def find_latest_export(roots: Iterable[Path]=SEARCH_ROOTS) -> Optional[Path]:
    files: List[Path] = []
    for r in roots:
        if not r.exists():
            continue
        for pat in PATTERNS:
            files.extend(r.glob(pat))
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]

def read_latest_export() -> pd.DataFrame:
    p = find_latest_export()
    if not p:
        return pd.DataFrame()
    try:
        return pd.read_csv(p)
    except Exception:
        return pd.DataFrame()