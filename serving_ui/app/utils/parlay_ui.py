# -*- coding: utf-8 -*-
"""
Drop-in UI helpers for parlay selection tables.

Place this file at:
    serving_ui/app/utils/parlay_ui.py

Pages expect:
    from app.utils.parlay_ui import selectable_odds_table

This implementation:
- Shows a checkbox column to pick rows
- Optionally constrains multiple picks from the same game/market
- Writes selections to a CSV "parlay_cart.csv" in the repo's `exports/` folder
- If app.utils.parlay_cart.add_to_cart is available, uses it instead of the CSV fallback
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List

import numpy as np
import pandas as pd

try:
    import streamlit as st
except Exception as _e:
    # Allow import by non-Streamlit contexts (tests, tools)
    class _Dummy:
        def __getattr__(self, k): 
            def _noop(*a, **kw): 
                return None
            return _noop
    st = _Dummy()  # type: ignore

# -------- cart integration (optional dependency) --------
_CART_FN = None
_READ_CART = None
_CLEAR_CART = None
try:
    from app.utils.parlay_cart import add_to_cart as _CART_FN  # type: ignore
    from app.utils.parlay_cart import read_cart as _READ_CART  # type: ignore
    from app.utils.parlay_cart import clear_cart as _CLEAR_CART  # type: ignore
except Exception:
    _CART_FN = None

def _repo_root() -> Path:
    env = os.environ.get("EDGE_FINDER_ROOT", "").strip()
    if env and Path(env).exists():
        return Path(env)
    here = Path(__file__).resolve()
    for up in [here] + list(here.parents):
        if (up / "exports").exists():
            return up
    return Path.cwd()

def _exports_dir() -> Path:
    p = _repo_root() / "exports"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _cart_csv() -> Path:
    return _exports_dir() / "parlay_cart.csv"

def _write_cart_fallback(rows: pd.DataFrame) -> None:
    """Append rows to exports/parlay_cart.csv with basic de-duplication."""
    path = _cart_csv()
    out = rows.copy()
    # Ensure consistent column order and string-safe types
    for c in out.columns:
        if pd.api.types.is_object_dtype(out[c]):
            out[c] = out[c].astype("string")
    if path.exists() and path.stat().st_size > 0:
        try:
            cur = pd.read_csv(path, low_memory=False)
        except Exception:
            cur = pd.DataFrame()
        allc = pd.concat([cur, out], ignore_index=True)
        # de-dup on a broad key if present
        keys = [c for c in ["game_id", "_date_iso", "_home_nick", "_away_nick", "market", "_market_norm", "side", "line", "book", "price", "odds"] if c in allc.columns]
        if keys:
            allc = allc.drop_duplicates(keys + [c for c in ["commence_time"] if c in allc.columns], keep="first")
        allc.to_csv(path, index=False, encoding="utf-8-sig")
    else:
        out.to_csv(path, index=False, encoding="utf-8-sig")

def _maybe_add_to_cart(rows: pd.DataFrame) -> None:
    if rows is None or rows.empty:
        return
    if _CART_FN is not None:
        try:
            _CART_FN(rows)  # type: ignore[arg-type]
            return
        except Exception:
            pass
    _write_cart_fallback(rows)

def _norm_market(m) -> str:
    m = (str(m) or "").strip().lower()
    if m in {"h2h", "ml", "moneyline", "money line"}:
        return "H2H"
    if m.startswith("spread") or m in {"spread", "spreads"}:
        return "SPREADS"
    if m.startswith("total") or m in {"total", "totals"}:
        return "TOTALS"
    return m.upper()

def _ensure_market_norm(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if "_market_norm" not in df.columns:
        src = "market" if "market" in df.columns else None
        if src:
            df = df.copy()
            df["_market_norm"] = df[src].map(_norm_market)
    return df

def _pref_cols(df: pd.DataFrame) -> List[str]:
    """Preferred display/order columns if present."""
    pref = [
        "game_id","_date_iso","commence_time",
        "_away_nick","_home_nick","away","home",
        "_market_norm","market","side","line",
        "price","odds","book","p_win","_ev_per_$1",
    ]
    return [c for c in pref if c in df.columns]

def selectable_odds_table(
    cand: pd.DataFrame,
    page_key: str,
    page_name: str,
    allow_same_game: bool = False,
    one_per_market_per_game: bool = True,
) -> None:
    """
    Render a selectable table of odds/edges and add picks to a parlay cart.

    Parameters
    ----------
    cand : DataFrame
        Candidate rows to display (edges or live odds).
    page_key : str
        Unique key per page instance (for Streamlit widget keys).
    page_name : str
        A label stored alongside rows for traceability.
    allow_same_game : bool, default False
        If False, multiple selections from the same game will be reduced to one.
    one_per_market_per_game : bool, default True
        If True, only one selection per (game_id, market) is kept.
    """
    import streamlit as st  # runtime import for safety in non-UI contexts

    if cand is None or len(cand) == 0:
        st.info("No rows to add.")
        return

    work = cand.copy()
    work = _ensure_market_norm(work)

    # reorder columns for display
    cols = _pref_cols(work) + [c for c in work.columns if c not in _pref_cols(work)]
    work = work[cols]

    # Selection column
    sel_col = "_select"
    work.insert(0, sel_col, False)

    edited = st.data_editor(
        work,
        key=f"editor_{page_key}",
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
    )

    picked = edited[edited[sel_col] == True].drop(columns=[sel_col], errors="ignore")  # noqa: E712
    st.caption(f"Selected: **{len(picked):,}** row(s)")

    # Constraints
    if not allow_same_game and "game_id" in picked.columns:
        picked = picked.drop_duplicates(["game_id"])
    if one_per_market_per_game:
        keys = [k for k in ["game_id", "_market_norm"] if k in picked.columns]
        if keys:
            picked = picked.drop_duplicates(keys)

    # minimal provenance
    picked = picked.copy()
    picked["_page"] = page_name

    # UX buttons
    colA, colB = st.columns([1, 1])
    with colA:
        add = st.button("➕ Add selected to Cart", type="primary", key=f"add_{page_key}")
    with colB:
        clear = st.button("🗑️ Clear selection", key=f"clear_{page_key}")

    if add and not picked.empty:
        _maybe_add_to_cart(picked)
        st.success(f"Added {len(picked):,} row(s) to cart.")
    if clear:
        # re-render with all False
        st.session_state[f"editor_{page_key}"] = {"edited_rows": {}, "added_rows": [], "deleted_rows": []}
        st.rerun()
