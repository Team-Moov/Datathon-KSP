"""
Validates FinancialCrimeService against the ground truth written by
seed_financial_transactions.py. This is the evidence for the demo slide --
and, per the earlier "isn't this overfitting" discussion, this number proves
the pipeline is wired correctly against patterns it was designed to catch,
NOT that it generalizes to laundering patterns it wasn't tuned to. Say that
out loud in the demo if asked.

DROP-IN LOCATION: backend/scripts/validate_financial_crime.py
RUN: python -m scripts.validate_financial_crime   (from backend/, after seeding)

Reads via the normal AsyncSessionFactory (app_runtime, RLS-restricted role) --
unlike the seeder, this only touches FinancialTransaction, which has no RLS
policy applied (only case_master and person_case_role do), so the restricted
role sees every row with no special connection needed.
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.core.database import AsyncSessionFactory
from app.models.financial import FinancialTransaction
from app.services.analytics.financial_crime import FinancialCrimeService

GROUND_TRUTH_PATH = Path(__file__).parent / "financial_ground_truth.json"


async def evaluate() -> None:
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text())  # txn_id -> typology

    async with AsyncSessionFactory() as session:
        svc = FinancialCrimeService(session)

        rows = (await session.execute(select(FinancialTransaction))).scalars().all()
        accounts = sorted({r.from_account for r in rows} | {r.to_account for r in rows})

        alerts = []
        for acct in accounts:
            s = await svc.detect_structuring(acct)
            if s:
                alerts.append(s)
            f = await svc.detect_funnel_account(acct)
            if f:
                alerts.append(f)
        alerts.extend(await svc.detect_cycles_in_graph())

    report = {}
    for typology in ["structuring", "funnel_account", "layering"]:
        detected_txns = set()
        for a in alerts:
            if a["typology"] != typology:
                continue
            trail = a["evidence_trail"].get("transaction_ids", [])
            detected_txns.update(trail)

        gt_key = {"funnel_account": "funnel"}.get(typology, typology)
        true_txns = {txn for txn, t in ground_truth.items() if t == gt_key}

        tp = len(detected_txns & true_txns)
        fp = len(detected_txns - true_txns)
        fn = len(true_txns - detected_txns)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

        report[typology] = {
            "true_positives": tp, "false_positives": fp, "false_negatives": fn,
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        }

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(evaluate())
