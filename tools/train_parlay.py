import argparse, json, os, sys
from pathlib import Path

import numpy as np
import pandas as pd

# Keep dependencies modest and common
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from joblib import dump


def american_to_decimal(a: pd.Series) -> pd.Series:
    """Convert American odds to decimal; handle non-finite and bad values."""
    a = pd.to_numeric(a, errors="coerce")
    dec = pd.Series(np.nan, index=a.index, dtype="float64")
    # positive american
    pos = a >= 100
    dec[pos] = 1.0 + (a[pos] / 100.0)
    # negative american
    neg = a <= -100
    dec[neg] = 1.0 + (100.0 / a[neg].abs())
    # guard
    dec = dec.where(np.isfinite(dec) & (dec > 1.0))
    return dec


def pick_first_present(df: pd.DataFrame, candidates):
    """Return the first column name from candidates that exists in df, else None."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def prepare_dataframe(df: pd.DataFrame, min_season: int) -> pd.DataFrame:
    # Season filter if present
    if "season" in df.columns:
        df = df[pd.to_numeric(df["season"], errors="coerce").fillna(-1).astype(int) >= int(min_season)].copy()

    # Normalize result -> binary
    res = df.get("result")
    if res is None:
        # Sometimes graded column is named 'grade' or 'outcome'
        res = df.get("grade", df.get("outcome"))

    if res is None:
        # Create a neutral target; training will quickly exit
        df["result_bin"] = np.nan
    else:
        s = res.astype(str).str.lower().str.strip()
        map_ = {"win": 1, "won": 1, "w": 1, "loss": 0, "lose": 0, "lost": 0, "l": 0}
        df["result_bin"] = s.map(map_)
        # Exclude pushes / ungraded rows
        df = df[df["result_bin"].isin([0, 1])].copy()

    # Decimal odds detection
    dec_col = pick_first_present(df, ["decimal_odds", "dec_odds", "price_dec", "price", "odds_dec"])
    if dec_col is None:
        # Try American odds
        am_col = pick_first_present(df, ["american_odds", "odds", "price_am", "am_odds"])
        if am_col is not None:
            df["price_dec"] = american_to_decimal(df[am_col])
        else:
            df["price_dec"] = np.nan
        dec_col = "price_dec"

    # Implied probability
    prob_col = pick_first_present(df, ["prob", "p", "model_prob", "win_prob"])
    if prob_col is None:
        # If we have decimal odds, 1/dec is a crude baseline; better if you already store model probs
        df["implied_prob"] = 1.0 / pd.to_numeric(df[dec_col], errors="coerce")
        df.loc[~np.isfinite(df["implied_prob"]) | (df["implied_prob"] <= 0) | (df["implied_prob"] >= 1), "implied_prob"] = np.nan
        prob_col = "implied_prob"

    # Candidate features — we’ll auto-select what exists & is numeric
    candidates = [
        "edge", "ev", "kelly", "clv", "line_diff", "close_diff", "spread_used", "total_used",
        "market_edge", "price_edge", "proj_diff", "model_edge", prob_col, dec_col
    ]
    present = [c for c in candidates if c in df.columns]
    # keep only numeric
    num_present = []
    for c in present:
        try:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            num_present.append(c)
        except Exception:
            pass

    # Minimal set: if somehow only prob is there, keep it; otherwise we need at least 2 cols for stability
    if not num_present:
        # Create a dummy column to avoid crashing; training will likely short-circuit
        df["dummy_zero"] = 0.0
        num_present = ["dummy_zero"]

    df_features = df[num_present].copy()
    df_features = df_features.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    df_out = df_features.copy()
    df_out["result_bin"] = df.get("result_bin").values
    return df_out, num_present


def train(df: pd.DataFrame, out_dir: Path, feature_cols):
    X = df[feature_cols].values
    y = df["result_bin"].values

    # Guard: need at least some 0s and 1s
    uniq = pd.unique(y[~pd.isna(y)])
    if len(uniq) < 2:
        print("[train_parlay] Not enough class variety to train (need wins & losses). Exiting gracefully.")
        return None

    model = LogisticRegression(max_iter=2000, n_jobs=None)  # n_jobs in newer sklearn; if error, it will be ignored
    model.fit(X, y)

    # Simple fit metrics
    try:
        proba = model.predict_proba(X)[:, 1]
        acc = accuracy_score(y, (proba >= 0.5).astype(int))
        ll  = log_loss(y, np.clip(proba, 1e-6, 1-1e-6))
    except Exception:
        proba = None
        acc = None
        ll = None

    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "parlay_model.joblib"
    dump(model, model_path)

    meta = {
        "feature_cols": feature_cols,
        "train_size": int(len(df)),
        "accuracy_in_sample": None if acc is None else float(acc),
        "logloss_in_sample": None if ll is None else float(ll),
        "columns_available": list(df.columns),
        "version": "1.0.0",
    }
    (out_dir / "parlay_model.meta.json").write_text(json.dumps(meta, indent=2))
    print(f"[train_parlay] Saved model to: {model_path}")
    print(f"[train_parlay] Meta: {out_dir / 'parlay_model.meta.json'}")
    if acc is not None:
        print(f"[train_parlay] In-sample acc={acc:.3f} logloss={ll:.4f}")
    return str(model_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", required=True, help="Path to edges_graded.csv")
    ap.add_argument("--out", required=True, help="Output directory for models")
    ap.add_argument("--min-season", type=int, default=2017)
    args = ap.parse_args()

    edges_path = Path(args.edges)
    out_dir = Path(args.out)

    if not edges_path.exists():
        print(f"[train_parlay] ERROR: edges file not found: {edges_path}", file=sys.stderr)
        sys.exit(2)

    df = pd.read_csv(edges_path)
    if df.empty:
        print(f"[train_parlay] ERROR: edges file is empty: {edges_path}", file=sys.stderr)
        sys.exit(3)

    df_prepped, feats = prepare_dataframe(df, args.min_season)

    # Need labeled rows
    df_prepped = df_prepped.dropna(subset=["result_bin"])
    if df_prepped.empty:
        print("[train_parlay] No labeled (win/loss) rows after filtering; nothing to train.")
        sys.exit(0)

    model_path = train(df_prepped, out_dir, feats)
    if model_path is None:
        sys.exit(0)


if __name__ == "__main__":
    main()

