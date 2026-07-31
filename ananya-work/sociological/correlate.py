"""
correlate.py
============
Correlates the district composite socio-economic index against crime,
using CHI-weighted severity sums rather than raw incident counts -- the
whole point of reusing the Crime Harm Index here is that a district's
"crime problem" measured in harm-weighted severity can tell a genuinely
different story than the same district measured in raw counts. This
script checks that claim empirically rather than just asserting it, by
reporting both correlations side by side.

DELIBERATE SIMPLIFICATION, stated plainly: this reports ONE statewide
coefficient, not a geographically-weighted regression with a
locally-varying coefficient per district. GWR (via mgwr) was cut from
this build's scope for hackathon-timeline stability -- see the earlier
scope discussion. A single Pearson r / OLS slope can't tell you "this
relationship is stronger in district X than district Y," which is a real
limitation, not an oversight. If GWR gets added back later, this script's
output is what it would be compared against as the naive baseline.

ALSO NEVER JOINS TO Person OR Case_Person_Role -- this stays a strictly
district-level, aggregate analysis. See the ecological-fallacy note in
the original design docs for why that firewall matters: a district-level
correlation says nothing about any individual within it, and treating it
that way is the same fairness failure mode the risk-score model was
built to avoid.
"""

import argparse

import numpy as np
import psycopg2
from scipy.stats import pearsonr


def load_district_chi_weighted_crime(conn, year=None):
    cur = conn.cursor()
    query = """
        SELECT i.district_id, EXTRACT(YEAR FROM i.date_occurred)::int AS year,
               SUM(o.severity_weight) AS chi_weighted_sum, COUNT(*) AS raw_count
        FROM incident i JOIN offense o ON o.incident_id = i.incident_id
    """
    params = []
    if year is not None:
        query += " WHERE EXTRACT(YEAR FROM i.date_occurred) = %s"
        params.append(year)
    query += " GROUP BY i.district_id, EXTRACT(YEAR FROM i.date_occurred)"
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    return {(r[0], r[1]): (float(r[2] or 0), int(r[3])) for r in rows}


def load_composite_index(conn, method="percentile_rank"):
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT ON (district_id, year) district_id, year, composite_value
        FROM district_composite_index WHERE method = %s
        ORDER BY district_id, year, computed_at DESC
    """, (method,))
    rows = cur.fetchall()
    cur.close()
    return {(r[0], r[1]): float(r[2]) for r in rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    ap.add_argument("--method", default="percentile_rank", choices=["percentile_rank", "pca"])
    args = ap.parse_args()

    conn = psycopg2.connect(args.dsn)
    crime = load_district_chi_weighted_crime(conn)
    composite = load_composite_index(conn, method=args.method)

    paired = []
    for key, comp_val in composite.items():
        if key in crime:
            chi_sum, raw_count = crime[key]
            paired.append((comp_val, chi_sum, raw_count))

    if len(paired) < 5:
        print(f"Only {len(paired)} matched district-year rows -- not enough to correlate meaningfully.")
        return

    comp_vals, chi_vals, count_vals = zip(*paired)

    r_chi, p_chi = pearsonr(comp_vals, chi_vals)
    r_count, p_count = pearsonr(comp_vals, count_vals)

    # simple OLS slope (one statewide coefficient -- see module docstring)
    slope_chi = np.polyfit(comp_vals, chi_vals, 1)[0]
    slope_count = np.polyfit(comp_vals, count_vals, 1)[0]

    print(f"Matched {len(paired)} district-year rows (composite index method: {args.method})\n")
    print("Composite index vs. CHI-weighted crime severity:")
    print(f"  Pearson r = {r_chi:.3f}  (p = {p_chi:.4f}), OLS slope = {slope_chi:.2f}")
    print("\nComposite index vs. raw incident count:")
    print(f"  Pearson r = {r_count:.3f}  (p = {p_count:.4f}), OLS slope = {slope_count:.2f}")

    gap = abs(r_chi) - abs(r_count)
    print(f"\n|r| difference (CHI-weighted minus raw count): {gap:+.3f}")
    if abs(gap) > 0.05:
        print("-> CHI-weighting and raw counts tell a meaningfully different story here, "
              "which is the actual justification for using CHI weighting at all rather "
              "than a cosmetic choice.")
    else:
        print("-> On this dataset, CHI-weighting and raw counts point the same direction to "
              "a similar degree -- worth noting honestly rather than overselling the CHI choice.")

    conn.close()


if __name__ == "__main__":
    main()
