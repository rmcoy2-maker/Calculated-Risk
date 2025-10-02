from __future__ import annotations
import os
import pandas as pd
from . import io_paths
from . import schemas
from . import enrich
ENC = 'utf-8-sig'

def _read_csv_safe(path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(path, low_memory=False, encoding=ENC)
    except Exception:
        return pd.DataFrame()

def _shape(df: pd.DataFrame, required: list[str], filler=None) -> pd.DataFrame:
    return schemas.ensure_cols(df, required, fill=filler)

def load_edges() -> pd.DataFrame:
    root = io_paths.find_exports_dir()
    path = os.path.join(root, io_paths.EDGES_FILENAME)
    df = _read_csv_safe(path)
    df = schemas.add_missing_defaults_edges(df)
    df = enrich.add_probs_and_ev(df)
    if 'market' in df.columns:
        df['market'] = df['market'].map(enrich.norm_market)
    return df

def load_live() -> pd.DataFrame:
    root = io_paths.find_exports_dir()
    path = os.path.join(root, io_paths.LIVE_FILENAME)
    df = _read_csv_safe(path)
    df = _shape(df, schemas.LIVE_COLS_REQ)
    return df

def load_scores() -> pd.DataFrame:
    root = io_paths.find_exports_dir()
    path = os.path.join(root, io_paths.SCORES_FILENAME)
    df = _read_csv_safe(path)
    df = _shape(df, schemas.SCORE_COLS_REQ)
    return df

def load_betlog() -> pd.DataFrame:
    root = io_paths.find_exports_dir()
    path = os.path.join(root, io_paths.BETLOG)
    df = _read_csv_safe(path)
    df = _shape(df, schemas.BETLOG_COLS_REQ)
    return df

def load_parlays() -> pd.DataFrame:
    root = io_paths.find_exports_dir()
    path = os.path.join(root, io_paths.PARLAYS)
    df = _read_csv_safe(path)
    df = _shape(df, schemas.PARLAY_COLS_REQ)
    return df