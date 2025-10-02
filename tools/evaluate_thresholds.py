import argparse, json, joblib
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score, precision_recall_curve

def make_time_split(df: pd.DataFrame):
    if "season" in df.columns:
        seasons = pd.to_numeric(df["season"], errors="coerce").dropna().unique()
        if len(seasons) >= 2:
            last = np.nanmax(seasons)
            tr = pd.to_numeric(df["season"], errors="coerce") < last
            va = pd.to_numeric(df["season"], errors="coerce") == last
            if tr.any() and va.any(): return tr, va
    n = len(df); cut = max(1, int(n*0.8))
    tr = pd.Series([True]*cut + [False]*(n-cut), index=df.index)
    va = ~tr
    return tr, va

def f3(x):
    try:
        if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
            return "nan"
        return f"{float(x):.3f}"
    except Exception:
        return "nan"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    model = joblib.load(Path(args.model_dir) / "parlay_model.joblib")
    meta  = json.load(open(Path(args.model_dir) / "meta.json", "r", encoding="utf-8"))
    num_cols = meta.get("num_cols", []) or []
    cat_cols = meta.get("cat_cols", []) or []

    df = pd.read_csv(args.edges)
    df.columns = [c.strip().lower() for c in df.columns]

    # labels
    y = None
    if "result" in df.columns:
        s = df["result"].astype(str).str.strip().str.lower()
        map_win  = {"win":1,"w":1,"1":1,"true":1,"t":1,"yes":1,"y":1}
        map_lose = {"lose":0,"l":0,"0":0,"false":0,"f":0,"no":0,"n":0}
        y = s.map({**map_win, **map_lose}).where(lambda v: v.isin([0,1]))

    # build X
    for c in num_cols:
        if c not in df.columns: df[c] = np.nan
    for c in cat_cols:
        if c not in df.columns: df[c] = ""
    X = df[num_cols + cat_cols] if (num_cols or cat_cols) else df.copy()

    # preds
    p = model.predict_proba(X)[:,1]
    df["_score"] = p

    tr, va = make_time_split(df)
    if y is None or not y.notna().any():
        raise SystemExit("No labels available for threshold evaluation.")
    yt, yv = y[tr].dropna(), y[va].dropna()
    pt, pv = df.loc[yt.index, "_score"], df.loc[yv.index, "_score"]

    # AUC for reference
    try: auc_t = roc_auc_score(yt, pt)
    except: auc_t = np.nan
    try: auc_v = roc_auc_score(yv, pv)
    except: auc_v = np.nan

    # precision-recall on validation
    prec, rec, thr = precision_recall_curve(yv, pv)
    prec, rec = prec[:-1], rec[:-1]  # align with thr

    # practical cuts
    cuts = np.linspace(0.50, 0.95, 10)
    rows = []
    base = float(yv.mean()) if len(yv) else np.nan
    for cut in cuts:
        sel = pv >= cut
        n = int(sel.sum())
        if n > 0:
            wr = float(yv[sel].mean())
            prec_c = wr  # precision = win rate of selected
            rec_c = float((yv[sel]==1).sum()) / float((yv==1).sum()) if (yv==1).sum() else np.nan
        else:
            wr = prec_c = rec_c = np.nan
        rows.append({"score_cut": round(float(cut), 3), "n": n, "win_rate": wr, "precision": prec_c, "recall": rec_c, "baseline": base})
    out = pd.DataFrame(rows)

    out_path = Path(args.out) if args.out else Path(args.edges).parent / "parlay_thresholds.csv"
    out.to_csv(out_path, index=False)
    print(f"Train AUC={f3(auc_t)}  Valid AUC={f3(auc_v)}")
    print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()

# --- extra helper ---
def find_cut_for_target(pv, yv, target=0.83):
    import numpy as np
    cuts = np.linspace(0.50, 0.99, 100)
    best = None
    for cut in cuts:
        sel = pv >= cut
        if sel.sum() < 10:  # skip tiny samples
            continue
        wr = float(yv[sel].mean())
        if wr >= target:
            best = (cut, wr, int(sel.sum()))
            break
    return best

