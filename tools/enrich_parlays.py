import argparse, numpy as np, pandas as pd

def american_to_dec(o):
    try: o = float(o)
    except: return np.nan
    if np.isnan(o): return np.nan
    if o > 0: return 1 + o/100.0
    if o < 0: return 1 + 100.0/abs(o)
    return np.nan

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", required=True)
    args = ap.parse_args()

    p = args.edges
    df = pd.read_csv(p)
    df.columns = [c.strip().lower() for c in df.columns]

    if "parlay_id" in df.columns:
        if "dec_leg" not in df.columns:
            df["dec_leg"] = df.get("odds", np.nan).apply(american_to_dec)
        g = df.groupby("parlay_id", dropna=False)
        df["legs"] = g["dec_leg"].transform("count")
        dec_prod = g["dec_leg"].transform(lambda s: np.prod(s.dropna()) if s.notna().any() else np.nan)
        df["dec_comb"] = np.where(df["legs"]>1, dec_prod, df["dec_leg"])
    else:
        # single-leg fallback
        if "legs" not in df.columns:
            df["legs"] = 1
        if "dec_comb" not in df.columns and "odds" in df.columns:
            df["dec_comb"] = df["odds"].apply(american_to_dec)

    df.to_csv(p, index=False)
    print(f"Enriched {p} with legs/dec_comb.")
if __name__ == "__main__":
    main()

