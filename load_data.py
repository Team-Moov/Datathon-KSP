"""
Loads generate_synthetic_data.py's CSV output into the Postgres schema
defined in schema.sql. Respects foreign-key order (districts and persons
before incidents, incidents before offenses, etc.).

Usage:
    python load_data.py --data-dir ./output --dsn "postgresql://crimeportal:crimeportal@localhost/crimeportal"
"""

import argparse
import csv

import psycopg2


def load_csv(cur, path, insert_sql, row_to_tuple):
    with open(path) as f:
        reader = csv.DictReader(f)
        rows = [row_to_tuple(r) for r in reader]
    if rows:
        psycopg2.extras.execute_values(cur, insert_sql, rows)
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="./output")
    ap.add_argument("--dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    args = ap.parse_args()

    import psycopg2.extras

    conn = psycopg2.connect(args.dsn)
    cur = conn.cursor()
    d = args.data_dir

    counts = {}

    # districts (dedup across the year rows -- only one district row needed)
    with open(f"{d}/district_socioeconomic.csv") as f:
        rows = list(csv.DictReader(f))
    seen = set()
    district_rows = []
    for r in rows:
        if r["district_id"] not in seen:
            seen.add(r["district_id"])
            district_rows.append((r["district_id"], r["district_name"]))
    psycopg2.extras.execute_values(
        cur, "INSERT INTO district (district_id, district_name) VALUES %s", district_rows
    )
    counts["district"] = len(district_rows)

    counts["district_socioeconomic"] = load_csv(
        cur, f"{d}/district_socioeconomic.csv",
        """INSERT INTO district_socioeconomic
           (district_id, year, literacy_pct, unemployment_pct, urbanization_pct, sex_ratio, composite_stress_index)
           VALUES %s""",
        lambda r: (r["district_id"], r["year"], r["literacy_pct"], r["unemployment_pct"],
                   r["urbanization_pct"], r["sex_ratio"], r["composite_stress_index"]),
    )

    counts["crime_stat_aggregate"] = load_csv(
        cur, f"{d}/crime_stat_aggregate.csv",
        "INSERT INTO crime_stat_aggregate (district_id, year, crime_head, count) VALUES %s",
        lambda r: (r["district_id"], r["year"], r["crime_head"], r["count"]),
    )

    counts["person"] = load_csv(
        cur, f"{d}/persons.csv",
        "INSERT INTO person (person_id, name, age, sex, district_id, address_text) VALUES %s",
        lambda r: (r["person_id"], r["name"], r["age"], r["sex"], r["district_id"], r["address_text"]),
    )

    counts["incident"] = load_csv(
        cur, f"{d}/incidents.csv",
        """INSERT INTO incident (incident_id, fir_number, district_id, date_occurred, date_reported, status)
           VALUES %s""",
        lambda r: (r["incident_id"], r["fir_number"], r["district_id"], r["date_occurred"],
                   r["date_reported"], r["status"]),
    )

    counts["offense"] = load_csv(
        cur, f"{d}/offenses.csv",
        """INSERT INTO offense (offense_id, incident_id, crime_head, mo_text, mo_signature, severity_weight)
           VALUES %s""",
        lambda r: (r["offense_id"], r["incident_id"], r["crime_head"], r["mo_text"],
                   r["mo_signature"], r["severity_weight"]),
    )

    counts["case_person_role"] = load_csv(
        cur, f"{d}/case_person_role.csv",
        "INSERT INTO case_person_role (incident_id, person_id, role) VALUES %s",
        lambda r: (r["incident_id"], r["person_id"], r["role"]),
    )

    counts["mo_linkage_series"] = load_csv(
        cur, f"{d}/mo_linkage_series.csv",
        """INSERT INTO mo_linkage_series (series_id, incident_id, offense_id, true_offender_person_id)
           VALUES %s""",
        lambda r: (r["series_id"], r["incident_id"], r["offense_id"], r["true_offender_person_id"]),
    )

    counts["financial_transaction"] = load_csv(
        cur, f"{d}/financial_transactions.csv",
        """INSERT INTO financial_transaction
           (transaction_id, from_account, to_account, amount, tx_date, linked_person_id, synthetic_pattern)
           VALUES %s""",
        lambda r: (r["transaction_id"], r["from_account"], r["to_account"], r["amount"],
                   r["date"], r["linked_person_id"] or None, r["synthetic_pattern"]),
    )

    conn.commit()
    print("Loaded:")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()