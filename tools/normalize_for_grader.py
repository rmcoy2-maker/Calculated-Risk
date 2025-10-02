import argparse, pandas as pd, numpy as np

def load_csv(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def to_str(s):
    return s.astype(str).str.strip()

def ensure_week_num_str(df, week_col_prefer="week_num", week_text_fallback="week"):
    df = df.copy()
    # start with week_num if present
    if week_col_prefer in df.columns:
        w = pd.to_numeric(df[week_col_prefer], errors="coerce")
    else:
        w = pd.Series([np.nan]*len(df))
    # try derive from 'week' text like "Week 1", "Preseason Week 2", etc.
    if week_text_fallback in df.columns:
        wk = df[week_text_fallback].astype(str).str.strip()
        digits = wk.str.extract(r"(\d+)", expand=False)
        w = w.fillna(pd.to_numeric(digits, errors="coerce"))
    # cast to nullable int then to string; blanks for NA
    w = w.astype("Int64")
    df["week_num"] = w.astype(str).replace({"<NA>":"", "nan":""})
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", required=True)
    ap.add_argument("--scores", required=True)
    ap.add_argument("--out-edges", required=True)
    ap.add_argument("--out-scores", required=True)
    args = ap.parse_args()

    edges  = load_csv(args.edges)
    scores = load_csv(args.scores)

    # normalize keys to strings
    for col in ["season","home","away"]:
        if col in edges:  edges[col]  = to_str(edges[col]).str.upper()
        if col in scores: scores[col] = to_str(scores[col]).str.upper()

    # crucial: force week_num to be a string on BOTH sides
    edges  = ensure_week_num_str(edges)
    scores = ensure_week_num_str(scores)

    edges.to_csv(args.out_edges, index=False)
    scores.to_csv(args.out_scores, index=False)

if __name__ == "__main__":
    main()

