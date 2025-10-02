import argparse
import warnings
import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

def _coerce_numeric_expected(pipe, df: pd.DataFrame) -> pd.DataFrame:
    """Make sure numeric block columns are numeric, so median imputer won't choke."""
    try:
        pre = pipe.named_steps.get("pre") or pipe.named_steps.get("ct")
    except Exception:
        pre = None
    num_cols = []
    if pre is not None and hasattr(pre, "transformers_"):
        for name, trans, cols in pre.transformers_:
            if name in ("num", "numeric", "num_pipe"):
                num_cols = list(cols)
                break
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def infer_label(df: pd.DataFrame):
    """Try to find a binary result label."""
    for candidate in ("result", "result_str", "outcome", "win_flag", "label"):
        if candidate in df.columns:
            y = df[candidate].astype(str).str.lower().map({
                "win": 1, "won": 1, "1": 1, "true": 1,
                "loss": 0, "lost": 0, "0": 0, "false": 0
            })
            if y.notna().sum() >= 100 and y.dropna().nunique() == 2:
                return y.fillna(0).astype(int)
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--model-file", default="parlay_model.joblib")
    args = ap.parse_args()

    df = pd.read_csv(args.edges, low_memory=False)
    df.columns = [c.strip().lower() for c in df.columns]

    model_path = f"{args.model_dir.rstrip('/\\')}/{args.model_file}"
    pipe = joblib.load(model_path)

    df = _coerce_numeric_expected(pipe, df)
    proba = pipe.predict_proba(df)[:, 1]

    # Optional AUC if we have a label
    y = infer_label(df)
    if y is not None and y.nunique() == 2:
        try:
            auc = roc_auc_score(y, proba)
            print(f"[evaluate_parlay] AUC={auc:.3f} on {len(y):,} rows")
        except Exception as e:
            print("[evaluate_parlay] Could not compute AUC:", e)
    else:
        print("[evaluate_parlay] No binary label found; skipping AUC.")

    # quick distribution
    qs = np.quantile(pd.Series(proba), [0, .25, .5, .75, .9, .95, .99, 1])
    print("[evaluate_parlay] proba quantiles:",
          dict(zip(["min","25%","50%","75%","90%","95%","99%","max"],
                   [round(float(x), 3) for x in qs])))

if __name__ == "__main__":
    main()
