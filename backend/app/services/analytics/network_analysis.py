"""
Criminal Network Analysis Service (§4).
Deterministic graph algorithms — the LLM narrates results, never computes them.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

import networkx as nx
import structlog

from app.core.graph_db import cached_graph_query, graph_db
from app.services.graph_sync_service import GraphSyncService

log = structlog.get_logger(__name__)


class NetworkAnalysisService:
    """
    All methods return structured data contracts consumed by the force-directed graph widget.
    None of these methods generate free-form text — that is the LLM's job.
    """

    def __init__(self) -> None:
        self.graph_sync = GraphSyncService()

    @cached_graph_query("ego_network")
    async def get_ego_network(
        self, person_id: str, depth: int = 2
    ) -> Dict[str, Any]:
        """Person ego network for force-directed graph widget."""
        return await self.graph_sync.get_person_network(person_id, depth)

    async def compute_centrality(self, graph_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Compute PageRank (operational leader) + betweenness (broker) centrality.
        Returns {person_id: {pagerank, betweenness}}.
        """
        G = self._build_networkx(graph_data)
        pagerank = nx.pagerank(G, alpha=0.85)
        betweenness = nx.betweenness_centrality(G, normalized=True)

        result = {}
        for node_id in G.nodes:
            result[node_id] = {
                "pagerank": round(pagerank.get(node_id, 0.0), 6),
                "betweenness": round(betweenness.get(node_id, 0.0), 6),
            }
        return result

    @cached_graph_query("communities")
    async def detect_communities(self) -> List[Dict[str, Any]]:
        """
        Run Louvain community detection via Neo4j GDS.
        Returns [{person_id, community_id}].
        """
        return await self.graph_sync.run_community_detection(algorithm="louvain")

    @cached_graph_query("cooffending_network")
    async def get_cooffending_network(
        self,
        district_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Bipartite accused↔incident projection into person-person co-offending network (§4).
        """
        filters = []
        params: Dict[str, Any] = {}
        if district_id:
            filters.append("i.district_id = $district_id")
            params["district_id"] = district_id
        if date_from:
            filters.append("i.date_reported >= $date_from")
            params["date_from"] = date_from
        if date_to:
            filters.append("i.date_reported <= $date_to")
            params["date_to"] = date_to

        where = f"WHERE {' AND '.join(filters)}" if filters else ""

        query = f"""
        MATCH (a:Person)-[:ACCUSED_IN]->(i:Incident)<-[:ACCUSED_IN]-(b:Person)
        {where}
        WHERE id(a) < id(b)
        RETURN a.id AS person_a, b.id AS person_b, count(i) AS shared_incidents
        ORDER BY shared_incidents DESC
        LIMIT 500
        """
        results = await graph_db.execute_query(query, params)
        return {"edges": results, "type": "co_offending"}

    @cached_graph_query("predicted_links")
    async def get_link_predictions(
        self, person_id: str, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Surface plausible-but-unconfirmed connections (§4).
        Returns predicted links with confidence — always labeled as PREDICTED, never confirmed.
        """
        query = """
        MATCH (p:Person {id: $person_id})-[r:PREDICTED_LINK]-(other:Person)
        RETURN other.id AS predicted_person_id, other.name AS name,
               r.confidence AS confidence, r.source_tool AS source_tool
        ORDER BY r.confidence DESC
        LIMIT $top_k
        """
        return await graph_db.execute_query(query, {"person_id": person_id, "top_k": top_k})

    @cached_graph_query("multi_jurisdiction_offenders")
    async def get_multi_jurisdiction_offenders(self) -> List[Dict[str, Any]]:
        """
        Persons whose cases span multiple police unit jurisdictions (§3.3 — organized crime signal).
        """
        query = """
        MATCH (p:Person)-[:ACCUSED_IN]->(i:Incident)
        WITH p, collect(DISTINCT i.unit_id) AS units
        WHERE size(units) > 1
        RETURN p.id AS person_id, p.name AS name, size(units) AS jurisdiction_count, units
        ORDER BY jurisdiction_count DESC
        LIMIT 100
        """
        return await graph_db.execute_query(query, {})

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_networkx(graph_data: Dict[str, Any]) -> nx.Graph:
        G = nx.Graph()
        for node in graph_data.get("nodes", []):
            G.add_node(node["id"], **node.get("properties", {}))
        for edge in graph_data.get("edges", []):
            G.add_edge(edge["from"], edge["to"], type=edge["type"])
        return G
