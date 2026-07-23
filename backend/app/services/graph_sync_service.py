from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog

from app.core.graph_db import graph_db, invalidate_graph_cache
from app.models.document import Document

log = structlog.get_logger(__name__)


class GraphSyncService:

    async def sync_document(
        self, extracted: Dict[str, Any], doc: Document
    ) -> None:
        case_id = extracted.get("case_id")
        persons = extracted.get("persons", [])

        if case_id:
            await self._upsert_incident_node(case_id, extracted)

        for person_data in persons:
            person_id = person_data.get("person_id")
            if person_id:
                await self._upsert_person_node(person_data)
                if case_id:
                    role = person_data.get("role", "accused")
                    await self._create_person_case_edge(person_id, case_id, role)

        await invalidate_graph_cache()

    async def upsert_predicted_link(
        self,
        person_a_id: str,
        person_b_id: str,
        confidence: float,
        model_version: str,
        source_tool: str,
        evidence: Optional[str] = None,
    ) -> None:
        query = """
        MERGE (a:Person {id: $a_id})
        MERGE (b:Person {id: $b_id})
        MERGE (a)-[r:PREDICTED_LINK]-(b)
        SET r.confidence = $confidence,
            r.model_version = $model_version,
            r.source_tool = $source_tool,
            r.evidence = $evidence,
            r.updated_at = datetime()
        """
        await graph_db.execute_query(
            query,
            {
                "a_id": person_a_id,
                "b_id": person_b_id,
                "confidence": confidence,
                "model_version": model_version,
                "source_tool": source_tool,
                "evidence": evidence,
            },
        )
        await invalidate_graph_cache()
        log.info(
            "Predicted link upserted",
            a=person_a_id,
            b=person_b_id,
            confidence=confidence,
        )

    async def upsert_financial_edge(
        self,
        from_person_id: str,
        to_person_id: str,
        transaction_id: str,
        amount: float,
    ) -> None:
        query = """
        MATCH (a:Person {id: $from_id}), (b:Person {id: $to_id})
        MERGE (a)-[r:TRANSACTED_WITH {transaction_id: $txn_id}]->(b)
        SET r.amount = $amount, r.updated_at = datetime()
        """
        await graph_db.execute_query(
            query,
            {
                "from_id": from_person_id,
                "to_id": to_person_id,
                "txn_id": transaction_id,
                "amount": amount,
            },
        )
        await invalidate_graph_cache()

    async def get_person_network(
        self, person_id: str, depth: int = 2
    ) -> Dict[str, Any]:
        query = """
        MATCH path = (p:Person {id: $person_id})-[*1..{depth}]-(n)
        RETURN nodes(path) as nodes, relationships(path) as rels
        """.replace("{depth}", str(depth))

        results = await graph_db.execute_query(query, {"person_id": person_id})
        return self._serialize_graph(results)

    async def run_community_detection(self, algorithm: str = "louvain") -> List[Dict[str, Any]]:
        await graph_db.execute_query(
            """
            CALL gds.graph.project(
                'co_offending',
                'Person',
                {ACCUSED_IN: {orientation: 'UNDIRECTED'}, ASSOCIATED_WITH: {orientation: 'UNDIRECTED'}}
            )
            """
        )
        results = await graph_db.execute_query(
            """
            CALL gds.louvain.stream('co_offending')
            YIELD nodeId, communityId
            RETURN gds.util.asNode(nodeId).id AS person_id, communityId
            ORDER BY communityId
            """
        )
        return results

    async def _upsert_incident_node(self, case_id: str, data: Dict[str, Any]) -> None:
        await graph_db.execute_query(
            """
            MERGE (i:Incident {id: $case_id})
            SET i.crime_no = $crime_no,
                i.date_reported = $date_reported,
                i.updated_at = datetime()
            """,
            {
                "case_id": case_id,
                "crime_no": data.get("crime_no", ""),
                "date_reported": str(data.get("date_reported", "")),
            },
        )

    async def _upsert_person_node(self, person_data: Dict[str, Any]) -> None:
        await graph_db.execute_query(
            """
            MERGE (p:Person {id: $person_id})
            SET p.name = $name,
                p.aliases = $aliases,
                p.updated_at = datetime()
            """,
            {
                "person_id": str(person_data.get("person_id")),
                "name": person_data.get("full_name", ""),
                "aliases": person_data.get("aliases", []),
            },
        )

    async def _create_person_case_edge(
        self, person_id: str, case_id: str, role: str
    ) -> None:
        rel_type = "ACCUSED_IN" if role == "accused" else "VICTIM_IN" if role == "victim" else "WITNESSED"
        await graph_db.execute_query(
            f"""
            MATCH (p:Person {{id: $person_id}}), (i:Incident {{id: $case_id}})
            MERGE (p)-[r:{rel_type}]->(i)
            SET r.updated_at = datetime()
            """,
            {"person_id": str(person_id), "case_id": str(case_id)},
        )

    @staticmethod
    def _json_safe_properties(props: Dict[str, Any]) -> Dict[str, Any]:
        safe: Dict[str, Any] = {}
        for key, value in props.items():
            isoformat = getattr(value, "isoformat", None)
            safe[key] = isoformat() if callable(isoformat) else value
        return safe

    @staticmethod
    def _serialize_graph(results: List[Dict]) -> Dict[str, Any]:
        nodes, edges = [], []
        seen_node_ids, seen_edge_ids = set(), set()
        for record in results:
            for node in record.get("nodes", []):
                nid = node.get("id") or str(node.element_id)
                if nid not in seen_node_ids:
                    seen_node_ids.add(nid)
                    nodes.append({
                        "id": nid,
                        "labels": list(node.labels),
                        "properties": GraphSyncService._json_safe_properties(dict(node)),
                    })
            for rel in record.get("rels", []):
                rid = str(rel.element_id)
                if rid not in seen_edge_ids:
                    seen_edge_ids.add(rid)
                    # Must key from/to the same way nodes are keyed above (the
                    # custom "id" property, falling back to element_id only if
                    # a node genuinely has none) — using rel.start_node/end_node's
                    # raw element_id here unconditionally meant edges pointed at
                    # an identifier space the nodes array never used, so no edge
                    # could ever resolve to a node. d3-force's forceLink throws
                    # on an unresolvable link id, and with no error boundary in
                    # the frontend that crash blanks the entire app.
                    start_props = dict(rel.start_node)
                    end_props = dict(rel.end_node)
                    edges.append({
                        "id": rid,
                        "type": rel.type,
                        "from": start_props.get("id") or str(rel.start_node.element_id),
                        "to": end_props.get("id") or str(rel.end_node.element_id),
                        "properties": GraphSyncService._json_safe_properties(dict(rel)),
                    })
        return {"nodes": nodes, "edges": edges}