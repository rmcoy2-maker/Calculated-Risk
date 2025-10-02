import argparse
import warnings
import pandas as pd
import joblib

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

def _coerce_numeric_expected(pipe, df: pd.DataFrame) -> pd.DataFrame:
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--model-file", default="parlay_model.joblib")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.edges, low_memory=False)
    df.columns = [c.strip().lower() for c in df.columns]

    model_path = f"{args.model_dir.rstrip('/\\')}/{args.model_file}"
    pipe = joblib.load(model_path)

    df = _coerce_numeric_expected(pipe, df)
    df["parlay_proba"] = pipe.predict_proba(df)[:, 1]

    df.to_csv(args.out, index=False)
    print(f"[predict_parlay_score] wrote {args.out} with {len(df):,} rows and column 'parlay_proba'")

if __name__ == "__main__":
    main()
