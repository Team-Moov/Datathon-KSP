"""
Criminal Network Analysis Service (§4).
Deterministic graph algorithms — the LLM narrates results, never computes them.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

import networkx as nx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.graph_db import cached_graph_query, graph_db
from app.services.graph_sync_service import GraphSyncService

log = structlog.get_logger(__name__)

# Whitelisted before being interpolated into Cypher text — Neo4j has no way to
# bind labels/relationship types as query parameters, so anything reaching
# the query string has to be validated against a fixed set first.
_ALLOWED_NODE_LABELS = {"Person", "Incident", "Account"}
_ALLOWED_EDGE_TYPES = {"ACCUSED_IN", "VICTIM_IN", "WITNESSED", "ASSOCIATED_WITH", "TRANSACTED_WITH", "PREDICTED_LINK"}


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
        Louvain community detection over the co-offending network.

        Computed in networkx from the co-offending edges rather than Neo4j GDS:
        GDS isn't available on every Neo4j tier (e.g. Aura Free) and its projection
        was brittle when an edge type had zero instances. networkx.louvain runs
        anywhere and needs only the co-offending edges we already derive.
        Returns [{person_id, community_id}].
        """
        from networkx.algorithms.community import louvain_communities

        cooffending = await self.get_cooffending_network()
        graph = nx.Graph()
        for edge in cooffending.get("edges", []):
            graph.add_edge(edge["person_a"], edge["person_b"], weight=edge.get("shared_incidents", 1))

        if graph.number_of_nodes() == 0:
            return []

        communities = louvain_communities(graph, weight="weight", seed=42)
        return [
            {"person_id": person_id, "community_id": community_id}
            for community_id, members in enumerate(communities)
            for person_id in members
        ]

    async def get_communities_graph(self) -> Dict[str, Any]:
        """
        Louvain community assignments merged with the co-offending edges they
        were computed over, as a {nodes, edges} force-directed-graph payload
        (nodes carry community_id + name in `properties`).

        detect_communities() alone returns a flat [{person_id, community_id}]
        list — correct for counting/storage, but not renderable by the
        force-directed-graph widget without the edge structure, which this
        adds back in.
        """
        assignments = await self.detect_communities()
        if not assignments:
            return {"nodes": [], "edges": []}

        community_by_person = {a["person_id"]: a["community_id"] for a in assignments}
        person_ids = list(community_by_person.keys())

        names_query = "MATCH (p:Person) WHERE p.id IN $ids RETURN p.id AS id, p.name AS name"
        name_rows = await graph_db.execute_query(names_query, {"ids": person_ids})
        name_by_person = {row["id"]: row["name"] for row in name_rows}

        cooffending = await self.get_cooffending_network()

        nodes = [
            {
                "id": person_id,
                "properties": {"community_id": community_id, "name": name_by_person.get(person_id)},
            }
            for person_id, community_id in community_by_person.items()
        ]
        edges = [
            {
                "id": f"{edge['person_a']}-{edge['person_b']}",
                "from": edge["person_a"],
                "to": edge["person_b"],
                "type": "ACCUSED_IN",
            }
            for edge in cooffending.get("edges", [])
            if edge["person_a"] in community_by_person and edge["person_b"] in community_by_person
        ]
        return {"nodes": nodes, "edges": edges}

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

    async def query_graph_subset(
        self,
        db: Optional[AsyncSession] = None,
        node_labels: Optional[List[str]] = None,
        edge_types: Optional[List[str]] = None,
        district_id: Optional[int] = None,
        crime_no_contains: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        center_person_id: Optional[str] = None,
        depth: int = 1,
        limit: int = 300,
    ) -> Dict[str, Any]:
        """
        General-purpose filtered subgraph query — the data source behind the
        global graph explorer's filter controls, and also registered as the
        get_graph_subset LLM tool, so a free-text question like "show accused
        persons in district 3 connected by financial transactions" resolves
        to this exact same deterministic query rather than a separate path.

        Deliberately NOT LLM-generated Cypher: the model only ever supplies
        these structured filter arguments — the same "plan the call, don't
        write the query" pattern every other tool in this codebase follows.
        Letting a model generate raw Cypher against a live graph would be a
        real injection/DoS risk every other tool here was designed to avoid.
        """
        selected_edge_types = [t for t in (edge_types or []) if t in _ALLOWED_EDGE_TYPES] or list(_ALLOWED_EDGE_TYPES)
        selected_node_labels = [label for label in (node_labels or []) if label in _ALLOWED_NODE_LABELS] or None

        # district_id isn't a graph property (Incident nodes only carry
        # crime_no/date_reported) — resolved via Postgres first, then applied
        # as a graph-side id filter. This is the cross-store routing step:
        # relational answers "which incidents are in this district", graph
        # answers "how are they connected" — one call, two stores.
        allowed_incident_ids: Optional[set] = None
        if district_id is not None and db is not None:
            from sqlalchemy import text as sql_text

            rows = (
                await db.execute(sql_text("SELECT id FROM case_master WHERE district_id = :d"), {"d": district_id})
            ).all()
            allowed_incident_ids = {str(row[0]) for row in rows}
            if not allowed_incident_ids:
                return {"nodes": [], "edges": []}

        if center_person_id:
            raw = await self.get_ego_network(center_person_id, depth)
        else:
            rel_pattern = "|".join(selected_edge_types)
            query = f"""
            MATCH (a)-[r:{rel_pattern}]-(b)
            RETURN [a, b] AS nodes, [r] AS rels
            LIMIT $fetch_limit
            """
            # Fetch generously, then filter/truncate in Python below — simple
            # and correct, rather than one query trying to express every
            # filter combination (label sets, district, date range) at once.
            results = await graph_db.execute_query(query, {"fetch_limit": max(limit * 6, 1500)})
            raw = self.graph_sync._serialize_graph(results)

        def node_passes(node: Dict[str, Any]) -> bool:
            labels = set(node.get("labels", []))
            if selected_node_labels and not (labels & set(selected_node_labels)):
                return False
            if "Incident" in labels:
                props = node.get("properties", {})
                if allowed_incident_ids is not None and node["id"] not in allowed_incident_ids:
                    return False
                if crime_no_contains and crime_no_contains.lower() not in str(props.get("crime_no", "")).lower():
                    return False
                date_reported = props.get("date_reported")
                if date_from and (not date_reported or date_reported < date_from):
                    return False
                if date_to and (not date_reported or date_reported > date_to):
                    return False
            return True

        kept_nodes = [n for n in raw.get("nodes", []) if node_passes(n)][:limit]
        kept_ids = {n["id"] for n in kept_nodes}
        kept_edges = [
            e
            for e in raw.get("edges", [])
            if e["from"] in kept_ids and e["to"] in kept_ids and e.get("type") in selected_edge_types
        ]
        return {"nodes": kept_nodes, "edges": kept_edges}

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_networkx(graph_data: Dict[str, Any]) -> nx.Graph:
        G = nx.Graph()
        for node in graph_data.get("nodes", []):
            G.add_node(node["id"], **node.get("properties", {}))
        for edge in graph_data.get("edges", []):
            G.add_edge(edge["from"], edge["to"], type=edge["type"])
        return G
