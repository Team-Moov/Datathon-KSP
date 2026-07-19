"""
Financial Crime Detection Service (§9).
Reuses graph toolkit — typologies are shapes in a transaction graph, not single-tx properties.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.graph_db import graph_db
from app.models.enums import FinancialAlertType

log = structlog.get_logger(__name__)

# India ₹10 lakh Cash Transaction Report threshold (§9.2)
CTR_THRESHOLD_INR = 1_000_000.0


class FinancialCrimeService:
    """
    Detects money-laundering typologies from transaction graph.
    Output is shaped like a real STR (§9.5) — not an invented alert format.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def detect_structuring(
        self,
        account: str,
        window_days: int = 30,
    ) -> Optional[Dict[str, Any]]:
        """
        Detect smurfing/structuring: multiple deposits just under ₹10 lakh threshold.
        """
        cutoff = date.today() - timedelta(days=window_days)
        stmt = text("""
            SELECT to_account, SUM(amount) AS total, COUNT(*) AS txn_count,
                   MAX(amount) AS max_single
            FROM financial_transaction
            WHERE (from_account = :acct OR to_account = :acct)
              AND transaction_date >= :cutoff
            GROUP BY to_account
        """)
        # asyncpg binds DATE columns natively — it expects an actual date object
        # and errors opaquely (missing .toordinal()) if handed a string instead.
        result = await self.db.execute(stmt, {"acct": account, "cutoff": cutoff})
        rows = result.fetchall()

        alerts = []
        for row in rows:
            total = float(row.total or 0)
            max_single = float(row.max_single or 0)
            # Structuring: total exceeds threshold but individual txns stay below it
            if total >= CTR_THRESHOLD_INR and max_single < CTR_THRESHOLD_INR:
                alerts.append(
                    self._build_str_alert(
                        typology=FinancialAlertType.STRUCTURING,
                        accounts=[account, row.to_account],
                        evidence={
                            "total_amount": total,
                            "txn_count": row.txn_count,
                            "max_single_txn": max_single,
                            "window_days": window_days,
                            "ctr_threshold": CTR_THRESHOLD_INR,
                        },
                        confidence=0.80,
                    )
                )

        return alerts[0] if alerts else None

    async def detect_funnel_account(self, account: str) -> Optional[Dict[str, Any]]:
        """
        Funnel/mule: dormant account suddenly receives from many sources then empties.
        """
        stmt = text("""
            SELECT
                COUNT(DISTINCT from_account) AS sources,
                SUM(CASE WHEN to_account = :acct THEN amount ELSE 0 END) AS inflow,
                SUM(CASE WHEN from_account = :acct THEN amount ELSE 0 END) AS outflow
            FROM financial_transaction
            WHERE from_account = :acct OR to_account = :acct
        """)
        result = await self.db.execute(stmt, {"acct": account})
        row = result.fetchone()
        if not row:
            return None

        sources = int(row.sources or 0)
        inflow = float(row.inflow or 0)
        outflow = float(row.outflow or 0)

        # Funnel: many sources + outflow ≈ inflow (money transits quickly)
        if sources >= 5 and inflow > 0 and outflow / inflow > 0.8:
            return self._build_str_alert(
                typology=FinancialAlertType.FUNNEL_ACCOUNT,
                accounts=[account],
                evidence={"source_count": sources, "inflow": inflow, "outflow": outflow},
                confidence=0.75,
            )
        return None

    async def detect_cycles_in_graph(self, max_depth: int = 6) -> List[Dict[str, Any]]:
        """
        Layering detection: find cycles in TRANSACTED_WITH graph (§9.3).
        Cycle = money looping back toward source through intermediaries.
        """
        query = """
        MATCH path = (a:Person)-[:TRANSACTED_WITH*2..{depth}]->(a)
        WHERE LENGTH(path) >= 3
        RETURN [n IN nodes(path) | n.id] AS cycle_members,
               LENGTH(path) AS cycle_length
        LIMIT 50
        """.replace("{depth}", str(max_depth))

        results = await graph_db.execute_query(query, {})
        alerts = []
        for r in results:
            alerts.append(
                self._build_str_alert(
                    typology=FinancialAlertType.LAYERING,
                    accounts=r.get("cycle_members", []),
                    evidence={"cycle_length": r.get("cycle_length")},
                    confidence=0.70,
                )
            )
        return alerts

    @staticmethod
    def _build_str_alert(
        typology: FinancialAlertType,
        accounts: List[str],
        evidence: Dict[str, Any],
        confidence: float,
    ) -> Dict[str, Any]:
        """
        Produces an alert object shaped like a real STR (§9.5).
        Recognizable to how investigators already work.
        """
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
