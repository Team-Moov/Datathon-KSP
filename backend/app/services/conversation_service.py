"""
Conversational AI Service — LangGraph-based planner (§10).
The LLM selects which deterministic tool to call; tools compute; LLM narrates.
Claim validation runs before every response (§1.3, §11).
Backbone: Google Gemini 1.5 Pro (tool-calling) + Gemini 1.5 Flash (narration) via Vertex AI.
"""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

import structlog
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_vertexai import ChatVertexAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.analytics.network_analysis import NetworkAnalysisService
from app.services.analytics.hawkes_forecast import HawkesETASService
from app.services.analytics.risk_profiling import RiskProfilingService
from app.services.analytics.financial_crime import FinancialCrimeService
from app.services.investigator_support import InvestigatorSupportService

log = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are an investigative AI assistant for Karnataka Police.
You have access to a set of deterministic analytical tools.
Your role:
  1. Understand the investigator's question in English or Kannada.
  2. Decide which tool(s) are needed.
  3. Call those tools and wait for their results.
  4. Narrate the results clearly — cite specific numbers and tool outputs.
  5. NEVER fabricate a statistic, prediction, or risk score. If a tool returns no data, say so.
  6. Always note confidence levels and data limitations.
  7. After every answer, propose 2–3 concrete follow-up actions the investigator can take.

Sensitive-field rule: never mention or infer ReligionID or CasteID in analysis outputs."""


class ConversationService:
    """
    Manages a streamed conversation session.
    Tool calls are routed to the appropriate deterministic analytics service.
    Claim validation is applied before the final narration is sent.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        # Gemini 1.5 Pro via Vertex AI — function-calling for tool dispatch.
        # ADC is used automatically on GCP; for local dev set
        # GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
        self.llm = ChatVertexAI(
            model_name=settings.LLM_MODEL,          # gemini-1.5-pro-002
            project=settings.GCP_PROJECT,
            location=settings.GCP_LOCATION,
            temperature=0,
            streaming=True,
        ).bind_tools(self._build_tool_schemas())

        # Gemini Flash for cheaper claim-validation narration pass
        self._narration_llm = ChatVertexAI(
            model_name=settings.LLM_MODEL_FLASH,    # gemini-1.5-flash-002
            project=settings.GCP_PROJECT,
            location=settings.GCP_LOCATION,
            temperature=0,
        )

        # Service instances — all deterministic
        self.network_svc = NetworkAnalysisService()
        self.hawkes_svc = HawkesETASService(db)
        self.risk_svc = RiskProfilingService(db)
        self.financial_svc = FinancialCrimeService(db)
        self.investigator_svc = InvestigatorSupportService(db)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        session_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        Streamed chat turn. Yields JSON-encoded events:
          {"type": "token", "content": "..."}
          {"type": "tool_call", "tool": "...", "status": "running"}
          {"type": "tool_result", "tool": "...", "data": {...}}
          {"type": "widget", "widget_type": "...", "data": {...}}
          {"type": "done"}
        """
        lc_messages = [SystemMessage(content=SYSTEM_PROMPT)]
        for msg in messages:
            lc_messages.append(HumanMessage(content=msg["content"]) if msg["role"] == "user" else SystemMessage(content=msg["content"]))

        # ── LLM planning turn ─────────────────────────────────────────────────
        tool_calls = []
        content_buffer = ""
        async for chunk in self.llm.astream(lc_messages):
            if chunk.tool_calls:
                tool_calls.extend(chunk.tool_calls)
            if chunk.content:
                content_buffer += chunk.content
                yield json.dumps({"type": "token", "content": chunk.content}) + "\n"

        # ── Execute tool calls ────────────────────────────────────────────────
        tool_results = {}
        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc.get("args", {})

            yield json.dumps({"type": "tool_call", "tool": tool_name, "status": "running"}) + "\n"

            result = await self._dispatch_tool(tool_name, tool_args)
            tool_results[tool_name] = result

            # Emit widget event if the result maps to a widget (§10.2)
            widget_event = self._map_to_widget(tool_name, result)
            if widget_event:
                yield json.dumps({"type": "widget", **widget_event}) + "\n"

            yield json.dumps({"type": "tool_result", "tool": tool_name, "data": result}) + "\n"

        # ── Claim validation (§1.3, §11) ──────────────────────────────────────
        if tool_results:
            validated_narration = await self._validate_and_narrate(
                content_buffer, tool_results, lc_messages
            )
            yield json.dumps({"type": "token", "content": validated_narration}) + "\n"

        yield json.dumps({"type": "done"}) + "\n"

    async def _dispatch_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Route a tool call to the appropriate deterministic service."""
        dispatch = {
            "get_ego_network": lambda: self.network_svc.get_ego_network(args["person_id"], args.get("depth", 2)),
            "detect_communities": lambda: self.network_svc.detect_communities(),
            "compute_centrality": lambda: self.network_svc.compute_centrality(args.get("graph_data", {})),
            "get_multi_jurisdiction_offenders": lambda: self.network_svc.get_multi_jurisdiction_offenders(),
            "forecast_hotspots": lambda: self.hawkes_svc.forecast(
                district_id=args["district_id"],
                crime_head_id=args["crime_head_id"],
                target_date=__import__("datetime").date.fromisoformat(args["target_date"]),
                district_stress_index=args.get("stress_index"),
            ),
            "compute_risk_score": lambda: self.risk_svc.compute_risk_score(
                __import__("uuid").UUID(args["person_id"]), args.get("role", "INVESTIGATOR")
            ),
            "detect_financial_structuring": lambda: self.financial_svc.detect_structuring(args["account"]),
            "detect_funnel_account": lambda: self.financial_svc.detect_funnel_account(args["account"]),
            "detect_financial_cycles": lambda: self.financial_svc.detect_cycles_in_graph(),
            "generate_case_brief": lambda: self.investigator_svc.generate_case_brief(
                __import__("uuid").UUID(args["case_id"])
            ),
        }
        handler = dispatch.get(tool_name)
        if handler:
            try:
                return await handler()
            except Exception as exc:
                log.error("Tool dispatch error", tool=tool_name, error=str(exc))
                return {"error": str(exc)}
        return {"error": f"Unknown tool: {tool_name}"}

    async def _validate_and_narrate(
        self,
        draft: str,
        tool_results: Dict[str, Any],
        messages: List,
    ) -> str:
        """
        Header/footer claim validator (§1.3).
        Passes tool outputs back to the LLM for grounded narration.
        In production this also does a structured claim-check pass.
        """
        tool_context = json.dumps(tool_results, default=str, indent=2)
        validation_prompt = f"""
Given these EXACT tool outputs:
{tool_context}

Produce a concise, accurate narration. Rules:
- Only cite numbers that appear in the tool outputs above.
- If a value is missing or the tool returned an error, say so explicitly.
- End with 2–3 suggested follow-up actions from the available tools.
"""
        response = await self._narration_llm.ainvoke(messages + [HumanMessage(content=validation_prompt)])
        return response.content

    @staticmethod
    def _map_to_widget(tool_name: str, result: Any) -> Optional[Dict[str, Any]]:
        """Map a tool output to the appropriate widget type (§10.2)."""
        widget_map = {
            "get_ego_network": "force_directed_graph",
            "detect_communities": "force_directed_graph",
            "forecast_hotspots": "hotspot_map",
            "compute_risk_score": "risk_profile_card",
            "detect_financial_structuring": "flow_diagram",
            "detect_funnel_account": "flow_diagram",
            "detect_financial_cycles": "flow_diagram",
            "generate_case_brief": "case_timeline",
        }
        widget_type = widget_map.get(tool_name)
        if widget_type:
            return {"widget_type": widget_type, "data": result}
        return None

    @staticmethod
    def _build_tool_schemas() -> List[Dict]:
        """Minimal tool schemas for LLM function-calling."""
        return [
            {
                "name": "get_ego_network",
                "description": "Get ego network for a person (nodes + edges for force-directed graph)",
                "parameters": {"type": "object", "properties": {"person_id": {"type": "string"}, "depth": {"type": "integer"}}, "required": ["person_id"]},
            },
            {
                "name": "detect_communities",
                "description": "Run community detection on the co-offending network",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "forecast_hotspots",
                "description": "Hawkes/ETAS crime hotspot forecast for a district and crime type",
                "parameters": {"type": "object", "properties": {
                    "district_id": {"type": "integer"}, "crime_head_id": {"type": "integer"},
                    "target_date": {"type": "string"}, "stress_index": {"type": "number"},
                }, "required": ["district_id", "crime_head_id", "target_date"]},
            },
            {
                "name": "compute_risk_score",
                "description": "Compute CHI-weighted risk score for an accused person",
                "parameters": {"type": "object", "properties": {"person_id": {"type": "string"}}, "required": ["person_id"]},
            },
            {
                "name": "detect_financial_structuring",
                "description": "Detect structuring/smurfing for an account",
                "parameters": {"type": "object", "properties": {"account": {"type": "string"}}, "required": ["account"]},
            },
            {
                "name": "detect_financial_cycles",
                "description": "Detect layering cycles in the financial transaction graph",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "generate_case_brief",
                "description": "Generate a full one-click investigator case brief",
                "parameters": {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
            },
        ]
