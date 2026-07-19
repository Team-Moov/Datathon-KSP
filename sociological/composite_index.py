"""
composite_index.py
===================
Combines district-level socio-economic indicators (literacy, unemployment,
urbanization, sex ratio) into one composite index per district-year,
instead of showing four separate noisy indicators side by side. Two
methods, matching the real India-context precedent (the NDAP/Census-2011/
NFHS-4 district development index study used both):

  - percentile_rank (default): average of each indicator's percentile rank
    across districts, with unemployment inverted (lower = better rank).
    Simple, robust to outliers, easy to explain to a judge.
  - pca: first principal component of the standardized indicators. Can
    capture correlated structure percentile-ranking misses, but the sign
    and exact loading aren't guaranteed to point the "intuitive" direction
    without manual inspection -- that's checked and corrected below by
    orienting the component to correlate positively with literacy.

Writes to district_composite_index (versioned, append-only) -- NOT to
district_socioeconomic.composite_stress_index, which is a separate,
generator-baked value. Re-running this after real NDAP data replaces the
placeholder indicators produces a new row, not a silent overwrite.
"""

import argparse

import numpy as np
import psycopg2
import psycopg2.extras


def load_indicators(conn, year=None):
    cur = conn.cursor()
    query = """SELECT district_id, year, literacy_pct, unemployment_pct, urbanization_pct, sex_ratio
               FROM district_socioeconomic"""
    params = []
    if year is not None:
        query += " WHERE year = %s"
        params.append(year)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def percentile_rank_method(rows):
    def ranks(values, invert=False):
        vals = [-v for v in values] if invert else list(values)
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        r = [0.0] * len(vals)
        for rank, idx in enumerate(order):
            r[idx] = rank / (len(vals) - 1) if len(vals) > 1 else 0.5
        return r

    literacy = [float(r[2]) for r in rows]
    unemployment = [float(r[3]) for r in rows]
    urbanization = [float(r[4]) for r in rows]

    lit_r = ranks(literacy)
    unemp_r = ranks(unemployment, invert=True)  # lower unemployment -> better rank
    urb_r = ranks(urbanization)

    return [(lit_r[i] + unemp_r[i] + urb_r[i]) / 3 for i in range(len(rows))]


def pca_method(rows):
    X = np.array([[float(r[2]), float(r[3]), float(r[4]), float(r[5])] for r in rows])
    X_std = (X - X.mean(axis=0)) / X.std(axis=0)

    cov = np.cov(X_std, rowvar=False)
    eigvals, eigvecs = np.linalg.eigh(cov)
    top_component = eigvecs[:, np.argmax(eigvals)]

    scores = X_std @ top_component

    # orient so higher score = higher literacy (the intuitive "better socio-
    # economic position" direction) -- PCA sign is arbitrary otherwise
    literacy_col = X_std[:, 0]
    if np.corrcoef(scores, literacy_col)[0, 1] < 0:
        scores = -scores

    # rescale to 0-1 to be comparable with the percentile-rank method
    scores = (scores - scores.min()) / (scores.max() - scores.min() + 1e-9)
    return scores.tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    ap.add_argument("--method", choices=["percentile_rank", "pca", "both"], default="both")
    ap.add_argument("--year", type=int, default=None)
    args = ap.parse_args()

    conn = psycopg2.connect(args.dsn)
    rows = load_indicators(conn, year=args.year)
    print(f"Loaded {len(rows)} district-year rows")

    methods = ["percentile_rank", "pca"] if args.method == "both" else [args.method]
    all_out_rows = []
    for method in methods:
        scores = percentile_rank_method(rows) if method == "percentile_rank" else pca_method(rows)
        for (district_id, year, *_), score in zip(rows, scores):
            all_out_rows.append((district_id, year, method, float(score)))
        print(f"\n{method}: top 5 districts")
        ranked = sorted(zip([r[0] for r in rows], scores), key=lambda x: -x[1])
        for d, s in ranked[:5]:
            print(f"  {d}: {s:.3f}")

    cur = conn.cursor()
    psycopg2.extras.execute_values(
        cur,
        "INSERT INTO district_composite_index (district_id, year, method, composite_value) VALUES %s",
        all_out_rows,
    )
    conn.commit()
    print(f"\nWrote {len(all_out_rows)} rows to district_composite_index")

    if args.method == "both":
        # quick agreement check between the two methods -- if they wildly
        # disagree, that's worth knowing before picking one for the demo
        from scipy.stats import spearmanr
        pr_scores = [r[3] for r in all_out_rows if r[2] == "percentile_rank"]
        pca_scores = [r[3] for r in all_out_rows if r[2] == "pca"]
        rho, p = spearmanr(pr_scores, pca_scores)
        print(f"\nAgreement between methods (Spearman rank correlation): rho={rho:.3f}, p={p:.4f}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()