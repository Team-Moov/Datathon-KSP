"""
severity_history.py
====================
Sum of CHI-style severity weights across a person's accused offenses,
with exponential recency decay -- a recent serious offense should count
for more than an old one. This is a general-purpose, "as of any given
date" feature: re-run periodically (like risk_score itself) and it
should be versioned the same way if written anywhere persistent, not
treated as a fixed label.

decay weight = exp(-ln(2) / half_life_days * days_since_offense)
  -- an offense exactly half_life_days old counts for half its raw
  severity_weight; twice that old, a quarter; etc. half_life_days=180
  is a judgment call (there's no Hawkes-forecasting decay rate to reuse
  here -- that tool was cut from this build's scope), tune it if the
  demo needs offenses to matter for longer or shorter.

IMPORTANT -- why this is NOT currently wired into train_survival.py:
  The survival model's label is time from a person's FIRST recorded
  offense to their second. "Severity history prior to the index offense"
  is, by construction, always zero at that point -- there is nothing
  before someone's first offense. Plugging this feature into the current
  model as "prior history" would just be a constant 0 for every person:
  zero variance, worse than useless as a predictor.

  What train_survival.py uses instead (the index offense's own severity)
  is actually the more sensible choice for THAT specific label. This
  module is for two other, real uses:
    1. A standalone "how severe has this person's history been, as of
       today" dashboard figure -- useful on its own, no survival model
       needed.
    2. The natural input if the survival model is later upgraded from
       single-event to recurrent-events (predicting time to a 3rd, 4th
       offense using accumulated history up to that point) -- at that
       point "prior severity history" stops being trivially zero and
       this function is exactly what that model would call.
"""

import argparse
import math
from datetime import date

import psycopg2


def compute_severity_history(conn, as_of_date: date | None = None, half_life_days: int = 180) -> dict[str, float]:
    cur = conn.cursor()
    query = """
        SELECT cpr.person_id, o.severity_weight, i.date_occurred
        FROM case_person_role cpr
        JOIN incident i ON i.incident_id = cpr.incident_id
        JOIN offense o ON o.incident_id = i.incident_id
        WHERE cpr.role = 'accused' AND o.severity_weight IS NOT NULL
    """
    params = []
    if as_of_date is not None:
        query += " AND i.date_occurred <= %s"
        params.append(as_of_date)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()

    if as_of_date is None:
        as_of_date = max(d for _, _, d in rows) if rows else date.today()

    decay_rate = math.log(2) / half_life_days
    scores: dict[str, float] = {}
    for person_id, severity, date_occurred in rows:
        days_since = max((as_of_date - date_occurred).days, 0)
        weight = math.exp(-decay_rate * days_since)
        scores[person_id] = scores.get(person_id, 0.0) + float(severity) * weight
    return scores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    ap.add_argument("--as-of-date", default=None, help="YYYY-MM-DD, defaults to latest incident date in the data")
    ap.add_argument("--half-life-days", type=int, default=180)
    args = ap.parse_args()

    as_of = date.fromisoformat(args.as_of_date) if args.as_of_date else None
    conn = psycopg2.connect(args.dsn)
    scores = compute_severity_history(conn, as_of_date=as_of, half_life_days=args.half_life_days)

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    print(f"Computed severity history for {len(scores)} persons (half_life_days={args.half_life_days})")
    print("Top 5 by decayed severity-weighted history:")
    for person_id, score in ranked[:5]:
        print(f"  {person_id}: {score:.1f}")

    conn.close()


if __name__ == "__main__":
    main()
