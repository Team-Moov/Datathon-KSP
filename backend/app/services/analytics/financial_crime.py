"""
Financial Crime Detection Service (§9) -- drop-in replacement for
backend/app/services/analytics/financial_crime.py.

Changes from the original stub:
  - detect_structuring: proper per-(from_account,to_account) rolling 7-day
    window (was: flat 30-day window summed across every counterparty touching
    the account, which both misses subtle structuring and over-flags unrelated
    activity lumped onto one account).
  - detect_funnel_account: adds the dormancy check that's the actual defining
    signal of this typology (§9.2: "a *previously dormant* account suddenly
    receives..."). The original only checked source-count + in/out ratio,
    which would false-positive on any normally busy account.
  - detect_organized_clusters: NEW. Community detection over the account-level
    TRANSACTED_WITH graph, restricted to already-flagged accounts -- the third
    graph technique the design doc names (§9.3: "cycle detection, in/out-degree
    ratio, community detection") that had no implementation at all.
  - detect_cycles_in_graph: unchanged logic, but now queries Account nodes
    instead of Person nodes -- see the architecture note in
    seed_financial_transactions.py._sync_to_neo4j for why (TRANSACTED_WITH
    between accounts is what actually exists; Person-Person edges are a
    separate, weaker inferred layer).

DROP-IN LOCATION: backend/app/services/analytics/financial_crime.py
"""

from datetime import timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

import networkx as nx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.graph_db import graph_db
from app.models.enums import FinancialAlertType
from app.models.financial import FinancialTransaction

log = structlog.get_logger(__name__)

CTR_THRESHOLD_INR = 1_000_000.0
STRUCTURING_WINDOW_DAYS = 7
FUNNEL_DORMANCY_DAYS = 60
FUNNEL_BURST_WINDOW_DAYS = 2
FUNNEL_WITHDRAWAL_WINDOW_DAYS = 5
FUNNEL_MIN_SOURCES = 5
FUNNEL_RATIO_MIN = 0.80


class FinancialCrimeService:
    """Detects money-laundering typologies from transaction data + graph shape.
    Output is shaped like a real STR (§9.5) -- not an invented alert format."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # The connective lookup: person -> accounts. Lets a caller (chat tool or
    # REST) start from a person_id (which entity resolution/search already
    # produces) instead of needing an opaque account string upfront -- that's
    # the missing link that made the other detectors uncallable from a plain
    # "give me financial info on X" question with no account number in hand.
    # ------------------------------------------------------------------ #
    async def get_accounts_for_person(self, person_id: UUID) -> List[Dict[str, Any]]:
        stmt = select(
            FinancialTransaction.from_account,
            FinancialTransaction.to_account,
            FinancialTransaction.alert_type,
        ).where(FinancialTransaction.linked_person_id == person_id)
        rows = (await self.db.execute(stmt)).all()

        accounts: Dict[str, Dict[str, Any]] = {}
        for from_account, to_account, alert_type in rows:
            for account in (from_account, to_account):
                if not account:
                    continue
                entry = accounts.setdefault(account, {"account": account, "txn_count": 0, "flagged": False})
                entry["txn_count"] += 1
                if alert_type is not None:
                    entry["flagged"] = True
        return sorted(accounts.values(), key=lambda a: (-a["txn_count"], a["account"]))

    # ------------------------------------------------------------------ #
    # Structuring: fan-out from one source, legs under CTR threshold,
    # summing over it inside a rolling window -- per (from, to) pair, not
    # blended across every counterparty of the account.
    # ------------------------------------------------------------------ #
    async def detect_structuring(
        self, account: str, window_days: int = STRUCTURING_WINDOW_DAYS
    ) -> Optional[Dict[str, Any]]:
        stmt = (
            select(FinancialTransaction)
            .where(
                (FinancialTransaction.from_account == account)
                | (FinancialTransaction.to_account == account)
            )
            .order_by(FinancialTransaction.transaction_date)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        if not rows:
            return None

        by_pair: Dict[tuple, list] = {}
        for txn in rows:
            key = (txn.from_account, txn.to_account)
            by_pair.setdefault(key, []).append(txn)

        for (source, dest), legs in by_pair.items():
            legs = sorted(legs, key=lambda t: t.transaction_date)
            window: list = []
            for leg in legs:
                window.append(leg)
                window = [
                    w for w in window
                    if (leg.transaction_date - w.transaction_date).days <= window_days
                ]
                total = sum(float(w.amount) for w in window)
                all_under = all(float(w.amount) < CTR_THRESHOLD_INR for w in window)

                if total >= CTR_THRESHOLD_INR and all_under and len(window) >= 3:
                    return self._build_str_alert(
                        typology=FinancialAlertType.STRUCTURING,
                        accounts=[source, dest],
                        evidence={
                            "total_amount": total,
                            "leg_count": len(window),
                            "window_days": window_days,
                            "ctr_threshold": CTR_THRESHOLD_INR,
                            "transaction_ids": [str(w.id) for w in window],
                        },
                        confidence=min(0.99, 0.6 + 0.05 * len(window)),
                    )

        return None

    # ------------------------------------------------------------------ #
    # Funnel/mule: dormant-then-active account -- fan-in from many sources
    # within a short window, then rapid near-total withdrawal.
    # ------------------------------------------------------------------ #
    async def detect_funnel_account(self, account: str) -> Optional[Dict[str, Any]]:
        stmt = (
            select(FinancialTransaction)
            .where(
                (FinancialTransaction.from_account == account)
                | (FinancialTransaction.to_account == account)
            )
            .order_by(FinancialTransaction.transaction_date)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        if not rows:
            return None

        inflows = [t for t in rows if t.to_account == account]
        outflows = [t for t in rows if t.from_account == account]
        if not inflows or not outflows:
            return None

        for spike in inflows:
            window_start = spike.transaction_date
            window_end = window_start + timedelta(days=FUNNEL_BURST_WINDOW_DAYS)

            # Dormancy check -- the defining signal (§9.2), previously missing.
            # No inbound or outbound activity in the FUNNEL_DORMANCY_DAYS
            # immediately before the burst.
            dormancy_start = window_start - timedelta(days=FUNNEL_DORMANCY_DAYS)
            prior_activity = [
                t for t in rows
                if dormancy_start <= t.transaction_date < window_start
            ]
            if prior_activity:
                continue  # account wasn't dormant -- not this typology

            burst = [
                t for t in inflows
                if window_start <= t.transaction_date <= window_end
            ]
            source_count = len({t.from_account for t in burst})
            if source_count < FUNNEL_MIN_SOURCES:
                continue

            total_in = sum(float(t.amount) for t in burst)
            withdrawal_end = window_end + timedelta(days=FUNNEL_WITHDRAWAL_WINDOW_DAYS)
            rapid_out = [
                t for t in outflows
                if window_start <= t.transaction_date <= withdrawal_end
            ]
            total_out = sum(float(t.amount) for t in rapid_out)
            if total_in == 0 or total_out / total_in < FUNNEL_RATIO_MIN:
                continue

            return self._build_str_alert(
                typology=FinancialAlertType.FUNNEL_ACCOUNT,
                accounts=[account],
                evidence={
                    "source_count": source_count,
                    "inflow": total_in,
                    "outflow": total_out,
                    "dormancy_days_checked": FUNNEL_DORMANCY_DAYS,
                    "transaction_ids": [str(t.id) for t in burst + rapid_out],
                },
                confidence=min(0.99, 0.5 + 0.03 * source_count),
            )

        return None

    # ------------------------------------------------------------------ #
    # Layering: cycles in the ACCOUNT-level TRANSACTED_WITH graph.
    # ------------------------------------------------------------------ #
    async def detect_cycles_in_graph(self, max_depth: int = 6) -> List[Dict[str, Any]]:
        # Also collects each relationship's transaction_id -- the other three
        # detectors all put transaction_ids in evidence_trail (that's what
        # validate_financial_crime.py and anything else measuring precision/
        # recall actually keys off), but this one previously only returned
        # cycle_length/cycle_members, so every cycle it found was invisible
        # to anything checking evidence_trail["transaction_ids"] -- confirmed
        # live: Neo4j had real cycles, this method just never surfaced them
        # in a comparable shape.
        query = """
        MATCH path = (a:Account)-[:TRANSACTED_WITH*2..{depth}]->(a)
        WHERE LENGTH(path) >= 3
        RETURN [n IN nodes(path) | n.account_no] AS cycle_members,
               [r IN relationships(path) | r.transaction_id] AS transaction_ids,
               LENGTH(path) AS cycle_length
        LIMIT 50
        """.replace("{depth}", str(max_depth))

        results = await graph_db.execute_query(query, {})
        return [
            self._build_str_alert(
                typology=FinancialAlertType.LAYERING,
                accounts=r.get("cycle_members", []),
                evidence={
                    "cycle_length": r.get("cycle_length"),
                    "transaction_ids": r.get("transaction_ids", []),
                },
                confidence=0.70,
            )
            for r in results
        ]

    # ------------------------------------------------------------------ #
    # Organized clusters: community detection over already-flagged accounts
    # -- the third graph technique from §9.3, previously unimplemented.
    # Done in Python (networkx) rather than Neo4j GDS to avoid depending on
    # the GDS plugin being present in whatever Neo4j image the team deploys.
    # ------------------------------------------------------------------ #
    async def detect_organized_clusters(
        self, flagged_accounts: List[str]
    ) -> List[Dict[str, Any]]:
        if len(flagged_accounts) < 2:
            return []

        query = """
        MATCH (a:Account)-[r:TRANSACTED_WITH]->(b:Account)
        WHERE a.account_no IN $accounts AND b.account_no IN $accounts
        RETURN a.account_no AS source, b.account_no AS dest, r.amount AS amount
        """
        edges = await graph_db.execute_query(query, {"accounts": flagged_accounts})
        if not edges:
            return []

        g = nx.Graph()
        for e in edges:
            g.add_edge(e["source"], e["dest"], weight=float(e.get("amount") or 1.0))

        communities = nx.algorithms.community.louvain_communities(g, weight="weight", seed=42)

        clusters = []
        for community in communities:
            if len(community) < 2:
                continue
            clusters.append(
                self._build_str_alert(
                    typology=FinancialAlertType.ORGANIZED_CLUSTER,
                    accounts=sorted(community),
                    evidence={"cluster_size": len(community)},
                    confidence=min(0.95, 0.4 + 0.05 * len(community)),
                )
            )
        return clusters

    async def run_full_scan(self, accounts: List[str]) -> List[Dict[str, Any]]:
        """Convenience: run all detectors + organized-cluster pass over a
        given account list, for the demo/API to call in one shot."""
        alerts: List[Dict[str, Any]] = []
        for acct in accounts:
            structuring = await self.detect_structuring(acct)
            if structuring:
                alerts.append(structuring)
            funnel = await self.detect_funnel_account(acct)
            if funnel:
                alerts.append(funnel)

        alerts.extend(await self.detect_cycles_in_graph())

        flagged = sorted({a for alert in alerts for a in alert["accounts_involved"]})
        alerts.extend(await self.detect_organized_clusters(flagged))

        return alerts

    @staticmethod
    def _build_str_alert(
        typology: FinancialAlertType,
        accounts: List[str],
        evidence: Dict[str, Any],
        confidence: float,
    ) -> Dict[str, Any]:
        """Produces an alert object shaped like a real STR (§9.5)."""
        return {
            "typology": typology.value,
            "accounts_involved": accounts,
            "evidence_trail": evidence,
            "confidence": confidence,
            "recommended_action": "Review and file STR with FIU-IND if confirmed",
            "disclaimer": (
                "This is a system-generated lead based on transaction patterns. "
                "Analyst review and sign-off required before any action."
            ),
        }
