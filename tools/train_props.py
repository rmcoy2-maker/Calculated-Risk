#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
train_props.py — minimal, dependency-light trainer for player props.

Inputs (CSV):
- Required-ish columns (the script is forgiving):
  season (int)
  market (str)         e.g., pass_yds, rush_yds, rec_yds, pass_tds, etc.
  selection (str)      "over" or "under" (case-insensitive)
  line (float)         closing/opening/mixed — whatever you choose
  result (W/L/1/0)     optional; if missing, we try to compute from actual+line+selection
  actual (float)       optional; if present, lets us compute wins and line_bias
  player_id (str/int)  optional

Artifacts:
- models/props/hitrate.csv     (market, selection, line_bin, n, wins, hit_rate)
- models/props/line_bias.csv   (market, n, mean_bias, std_bias)  # when 'actual' exists
- models/props/metadata.json
- models/props/version.txt
"""
import argparse
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd


def coerce_lower(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower()


def safe_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = {c: c.strip() for c in df.columns}
    df = df.rename(columns=cols)
    # common aliases
    alias = {
        "prop_market": "market",
        "bet_type": "market",
        "pick": "selection",
        "side": "selection",
        "stake_side": "selection",
        "prob_selection": "selection",
        "outcome": "result",
    }
    for a, b in alias.items():
        if a in df.columns and b not in df.columns:
            df = df.rename(columns={a: b})
    return df


def ensure_result(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure a binary 'win' column exists.
    Priority:
      1) 'result' (W/L/1/0/True/False)
      2) derive from 'actual', 'line', 'selection'
    """
    win = pd.Series([np.nan] * len(df), index=df.index, dtype="float64")

    # case 1: explicit result
    if "result" in df.columns:
        r = coerce_lower(df["result"])
        win = np.where(r.isin(["w", "win", "1", "true", "t"]), 1.0,
                       np.where(r.isin(["l", "loss", "0", "false", "f"]), 0.0, np.nan))

    # case 2: compute from actual vs line & selection
    has_needed = {"actual", "line", "selection"}.issubset(df.columns)
    if has_needed:
        actual = safe_numeric(df["actual"])
        line = safe_numeric(df["line"])
        sel = coerce_lower(df["selection"])
        can_score = actual.notna() & line.notna() & sel.isin(["over", "under"])

        over = (sel == "over") & can_score
        under = (sel == "under") & can_score

        # push outcome where result is NaN
        comp = pd.Series(np.nan, index=df.index, dtype="float64")
        comp[over] = (actual[over] > line[over]).astype(float)
        comp[under] = (actual[under] < line[under]).astype(float)
        win = np.where(pd.isna(win), comp, win)

    df["win"] = win
    return df


def bin_lines(x: pd.Series, width: float = 5.0, precision: int = 1) -> pd.Series:
    """Bin numeric prop lines for empirical rate estimates."""
    x = safe_numeric(x)
    edges = np.floor(x / width) * width
    # label like "240–245"
    labels = edges.map(lambda v: f"{v:.{precision}f}–{v+width:.{precision}f}")
    labels[x.isna()] = np.nan
    return labels


def summarize_hitrate(df: pd.DataFrame) -> pd.DataFrame:
    need = ["market", "selection", "line", "win"]
    if not set(need).issubset(df.columns):
        return pd.DataFrame(columns=["market", "selection", "line_bin", "n", "wins", "hit_rate"])

    work = df.copy()
    work["market"] = coerce_lower(work["market"])
    work["selection"] = coerce_lower(work["selection"])
    work["line_bin"] = bin_lines(work["line"], width=5.0, precision=1)
    work = work.dropna(subset=["market", "selection", "line_bin", "win"])

    g = work.groupby(["market", "selection", "line_bin"], dropna=False)
    out = g["win"].agg(n="count", wins="sum").reset_index()
    out["hit_rate"] = out["wins"] / out["n"]
    return out.sort_values(["market", "selection", "line_bin"]).reset_index(drop=True)


def summarize_line_bias(df: pd.DataFrame) -> pd.DataFrame:
    if not {"actual", "line", "market"}.issubset(df.columns):
        return pd.DataFrame(columns=["market", "n", "mean_bias", "std_bias"])
    work = df.copy()
    work["market"] = coerce_lower(work["market"])
    work["bias"] = safe_numeric(work["actual"]) - safe_numeric(work["line"])
    work = work.dropna(subset=["market", "bias"])
    out = (work.groupby("market")["bias"]
           .agg(n="count", mean_bias="mean", std_bias="std")
           .reset_index())
    return out.sort_values(["market"]).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True,
                    help="CSV of props records. Must include at least: season, market, selection, line "
                         "and either result or (actual+line+selection).")
    ap.add_argument("--out", required=True, help="Output directory (e.g., models\\props)")
    ap.add_argument("--props-stats-since", type=int, default=2017,
                    help="Earliest season to include for training (stats/outcomes only is fine)")
    args = ap.parse_args()

    features_path = Path(args.features)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(features_path)
    df = normalize_columns(df)

    # season filter
    if "season" in df.columns:
        df = df[pd.to_numeric(df["season"], errors="coerce").fillna(0).astype(int) >= int(args.props_stats_since)]

    # ensure 'win'
    df = ensure_result(df)

    # Summaries
    hitrate = summarize_hitrate(df)
    line_bias = summarize_line_bias(df)

    # Save
    hitrate.to_csv(out_dir / "hitrate.csv", index=False)
    line_bias.to_csv(out_dir / "line_bias.csv", index=False)

    meta = {
        "records": int(len(df)),
        "hitrate_rows": int(len(hitrate)),
        "line_bias_rows": int(len(line_bias)),
        "required_cols_present": sorted(list(set(["season", "market", "selection", "line"]) & set(df.columns))),
        "win_filled_rate": float(df["win"].notna().mean()) if "win" in df.columns else 0.0,
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    (out_dir / "version.txt").write_text("props_trainer_v1\n")

    print(f"[ok] props model artifacts at {out_dir} "
          f"| records={len(df)} hitrate={len(hitrate)} line_bias={len(line_bias)}")


if __name__ == "__main__":
    main()

