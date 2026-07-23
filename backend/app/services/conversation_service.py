"""
Conversational AI Service — LangGraph-style planner (§10), now Gemini-backed.
The LLM selects which deterministic tool to call; tools compute; LLM narrates.
Claim validation runs before every response (§1.3, §11).
Backbone: Vertex AI Gemini — GEMINI_MODEL for tool-calling/planning,
GEMINI_MODEL_FAST for the cheaper narration/claim-validation pass.

The dispatch/widget-mapping architecture and the streamed event protocol
(token/tool_call/tool_result/widget/done) are provider-agnostic and unchanged
from the previous Groq-backed version — only the LLM binding is Gemini now.
"""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

import structlog
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.masking import mask_person_display_name
from app.core.permissions import Permission, role_has_permission
from app.core.vertex_ai_client import AiUnavailableError, get_genai_client, resilient_vertex_call
from app.models.user import User
from app.repositories.person_repository import PersonRepository
from app.services.analytics.network_analysis import NetworkAnalysisService
from app.services.analytics.hawkes_forecast import HawkesETASService
from app.services.analytics.risk_profiling import RiskProfilingService
from app.services.analytics.financial_crime import FinancialCrimeService
from app.services.analytics.socio_insights import SocioInsightsService
from app.services.investigator_support import InvestigatorSupportService

log = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are an investigative AI assistant for Karnataka Police.
You have access to a set of deterministic analytical tools.
Your role:
  1. Understand the investigator's question in English or Kannada.
  2. Decide which tool(s) are needed and call them. When you need data, call the
     tool directly — do NOT narrate your intention first ("Let me check…",
     "I'll now look up…"). Just call it. Save all prose for your final answer.
  3. You may call tools across several turns: read a tool's result, and if it
     unlocks a next step (e.g. search_persons returns an id you then feed to
     get_ego_network or compute_risk_score), call that next tool before answering.
  4. When you have everything you need, write ONE complete final answer that
     reasons over the tool results you just received.

Grounding rules (these make the platform's explainability guarantee real):
  - Cite ONLY numbers, names, and facts that appear in the tool outputs you
    received this turn. Never invent, round-guess, or recall a statistic,
    prediction, risk score, or relationship from memory.
  - If a tool returned no data, an empty result, or an error, say so plainly —
    do not paper over it with a plausible-sounding number.
  - Note confidence levels and data limitations where the tool output exposes them.
  - Distinguish predicted/unconfirmed links from confirmed records, the same way
    the tools do.
  - After the answer, propose 2–3 concrete follow-up actions, each naming a REAL
    tool from your toolset by its exact name — never invent a tool name.

Resolving people by name: almost every tool that takes a person_id needs the
internal UUID, not a name — investigators will always refer to people by name.
If the user names a person and you don't already know their person_id from
earlier in this conversation, call search_persons first to resolve the name
before calling any other person-scoped tool. Never invent or guess a
person_id. If search_persons returns zero matches, say so plainly rather than
proceeding. If it returns multiple plausibly-distinct matches (different
people who share a name, not near-duplicate spellings of the same one), list
them with distinguishing details (address, verification status) and ask the
investigator which one they mean instead of picking one yourself — the same
rule applies to any other ambiguous reference (which case, which district,
which time window): ask a short clarifying question rather than guessing when
more than one reasonable interpretation exists and the tool call would
otherwise be a guess.

Sensitive-field rule: never mention or infer ReligionID or CasteID in analysis outputs."""

# Gemini's OpenAPI-subset Schema uses an enum Type rather than JSON-schema's plain
# string, so the existing plain-dict tool schemas (kept as-is below, unchanged in
# shape) need a thin conversion at the point of binding — not a schema redesign.
_JSON_SCHEMA_TYPE_MAP = {
    "object": types.Type.OBJECT,
    "string": types.Type.STRING,
    "integer": types.Type.INTEGER,
    "number": types.Type.NUMBER,
    "boolean": types.Type.BOOLEAN,
    "array": types.Type.ARRAY,
}


def _json_schema_to_gemini_schema(schema: Dict[str, Any]) -> types.Schema:
    """Convert one of this module's plain JSON-schema dicts into a google-genai
    types.Schema, recursively (objects/arrays only need to nest one level deep
    for the tool schemas defined here, but recursion keeps this correct if that
    changes)."""
    kwargs: Dict[str, Any] = {"type": _JSON_SCHEMA_TYPE_MAP.get(schema.get("type", "object"), types.Type.OBJECT)}
    if "description" in schema:
        kwargs["description"] = schema["description"]
    if "properties" in schema:
        kwargs["properties"] = {
            key: _json_schema_to_gemini_schema(value) for key, value in schema["properties"].items()
        }
    if "required" in schema:
        kwargs["required"] = schema["required"]
    if "items" in schema:
        kwargs["items"] = _json_schema_to_gemini_schema(schema["items"])
    if "enum" in schema:
        kwargs["enum"] = schema["enum"]
    return types.Schema(**kwargs)


import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+")

# Proactive next-actions (§10.4): after a tool runs, offer 2–3 concrete follow-ups
# as clickable chips. Deterministic (keyed on the tool that just ran) so this adds
# ZERO extra LLM latency — the whole point of the streaming rewrite. Phrased in
# natural language ("that person/district") so the model re-resolves the referent
# from conversation history rather than us leaking a raw UUID into the chip label.
_FOLLOWUP_SUGGESTIONS: Dict[str, List[Dict[str, str]]] = {
    "search_persons": [
        {"label": "Show their network", "query": "Show the co-offending network for that person."},
        {"label": "Compute risk score", "query": "Compute the risk score for that person."},
        {"label": "Predicted links", "query": "Show plausible unconfirmed links for that person."},
    ],
    "get_ego_network": [
        {"label": "Compute risk score", "query": "Compute the risk score for that person."},
        {"label": "Predicted links", "query": "Show plausible unconfirmed links for that person."},
        {"label": "Multi-jurisdiction?", "query": "Does that person's activity span multiple jurisdictions?"},
    ],
    "get_graph_subset": [
        {"label": "Detect communities", "query": "Detect organized-crime communities in that network."},
        {"label": "Centrality", "query": "Who are the central figures (leaders and brokers) in that network?"},
    ],
    "detect_communities": [
        {"label": "Centrality", "query": "Compute centrality to find the leader and broker of each community."},
        {"label": "Multi-jurisdiction offenders", "query": "List offenders whose cases span multiple jurisdictions."},
    ],
    "compute_risk_score": [
        {"label": "Explain the score", "query": "Break down what drove that risk score."},
        {"label": "Show their network", "query": "Show the co-offending network for that person."},
    ],
    "forecast_hotspots": [
        {"label": "Socio-economic drivers", "query": "Show the socio-economic stress indicators for that district."},
        {"label": "GWR drivers", "query": "Which local factors predict crime harm most strongly in that district?"},
    ],
    "get_socio_indicators": [
        {"label": "GWR map", "query": "Show the statewide GWR map of crime-harm predictors."},
        {"label": "Forecast hotspots", "query": "Forecast crime hotspots for that district next week."},
    ],
    "get_case_workspace": [
        {"label": "Generate case brief", "query": "Generate a full case brief for that case."},
        {"label": "Similar past cases", "query": "Find similar past cases to that one."},
    ],
    "generate_case_brief": [
        {"label": "Open case workspace", "query": "Open the full case workspace for that case."},
    ],
    "run_financial_scan": [
        {"label": "Layering cycles", "query": "Detect layering cycles across the flagged accounts."},
        {"label": "Organized clusters", "query": "Group the flagged accounts into organized clusters."},
    ],
    "get_active_alerts": [
        {"label": "Organized groups only", "query": "Show only the organized-group alerts."},
        {"label": "Detect communities", "query": "Detect organized-crime communities in the network."},
        {"label": "Multi-jurisdiction offenders", "query": "List offenders whose cases span multiple jurisdictions."},
    ],
    "get_mo_linkage_clusters": [
        {"label": "Forecast hotspots", "query": "Forecast crime hotspots for this crime type next week."},
        {"label": "Detect communities", "query": "Detect organized-crime communities linked to these cases."},
    ],
}


def _build_followups(tools_used: List[str]) -> List[Dict[str, str]]:
    """Collect up to 3 de-duplicated follow-up chips from the tools that ran this
    turn, newest tool first (its follow-ups are the most contextually relevant)."""
    seen: set[str] = set()
    chips: List[Dict[str, str]] = []
    for tool_name in reversed(tools_used):
        for chip in _FOLLOWUP_SUGGESTIONS.get(tool_name, []):
            if chip["query"] in seen:
                continue
            seen.add(chip["query"])
            chips.append(chip)
            if len(chips) >= 3:
                return chips
    return chips


def _chunk_for_stream(text: str) -> List[str]:
    """Split a buffered final answer into sentence-ish chunks so the client
    renders it progressively (each yield flushes over the wire) instead of one
    late blob. '।' (danda) is included so Kannada/Devanagari sentences chunk too.
    Falls back to the whole string if there's nothing to split on."""
    if not text:
        return []
    chunks = [c for c in _SENTENCE_SPLIT.split(text) if c]
    # Re-attach the trailing space the lookbehind split consumed, so reassembled
    # text reads naturally on the client (which just concatenates the chunks).
    return [c if c.endswith(("\n",)) else c + " " for c in chunks] or [text]


class ConversationService:
    """
    Manages a streamed conversation session.
    Tool calls are routed to the appropriate deterministic analytics service.
    Claim validation is applied before the final narration is sent.
    """

    def __init__(self, db: AsyncSession, current_user: Optional[User] = None) -> None:
        self.db = db
        self.current_user = current_user
        self.client = get_genai_client()
        self._gemini_tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=schema["name"],
                        description=schema["description"],
                        parameters=_json_schema_to_gemini_schema(schema["parameters"]),
                    )
                    for schema in self._build_tool_schemas()
                ]
            )
        ]

        # Service instances — all deterministic
        self.person_repo = PersonRepository(db)
        self.network_svc = NetworkAnalysisService()
        self.hawkes_svc = HawkesETASService(db)
        self.risk_svc = RiskProfilingService(db)
        self.financial_svc = FinancialCrimeService(db)
        self.socio_svc = SocioInsightsService(db)
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
        # get_current_user already ran _apply_rls_session_context on self.db —
        # but chat's endpoint returns a StreamingResponse immediately, so
        # get_db()'s cleanup (session.commit()) fires as soon as the endpoint
        # function returns, before this generator's body actually executes.
        # Postgres's set_config(..., true) is transaction-local (SET LOCAL
        # semantics), so that commit silently resets app.current_role /
        # app.current_district_id — any RLS-protected table this generator
        # queries afterward (e.g. case_master, via get_case_workspace /
        # generate_case_brief) would otherwise see an empty/default context
        # and either over-restrict or (here) return zero rows. Re-applying it
        # fresh, inside the generator, is what actually makes it live for the
        # tool calls that follow.
        if self.current_user is not None:
            from app.core.security import _apply_rls_session_context

            await _apply_rls_session_context(self.db, self.current_user)

        # Gemini has no "system" role in contents — a language directive (e.g. the
        # "reply in Kannada" instruction chat.py prepends) folds into system_instruction
        # instead of being smuggled into the message list as the old Groq code did.
        system_instruction_parts = [SYSTEM_PROMPT]
        gemini_contents: List[types.Content] = []
        for msg in messages:
            if msg["role"] == "system":
                system_instruction_parts.append(msg["content"])
            elif msg["role"] == "user":
                gemini_contents.append(types.Content(role="user", parts=[types.Part(text=msg["content"])]))
            else:  # "assistant"
                gemini_contents.append(types.Content(role="model", parts=[types.Part(text=msg["content"])]))
        # Naming the real tool catalog in the system instruction is what stops the
        # model from inventing plausible-sounding tool names in its follow-up
        # suggestions — the grounding rule in SYSTEM_PROMPT references "your
        # toolset", and this is that toolset, spelled out once.
        tool_catalog = "\n".join(
            f"- {schema['name']}: {schema['description']}" for schema in self._build_tool_schemas()
        )
        system_instruction_parts.append("Your tools (use these exact names):\n" + tool_catalog)
        system_instruction = "\n\n".join(system_instruction_parts)

        # ── Multi-round tool-calling loop ───────────────────────────────────────
        # A single planning call can only see the tools it can call blind — it
        # can't chain a second call off the first one's result (e.g. resolve a
        # name via search_persons, then call get_ego_network with the id that
        # search just returned; or pull a case brief, then look up a lead's risk
        # score). That's exactly the "agent isn't getting enough context" failure
        # mode: Gemini would emit one tool call, never see its result, and then
        # narrate about tools that don't exist because it never got a real
        # second turn to reach for them. This loops — feeding each round's tool
        # results back as function_response parts — until the model stops
        # requesting tools on its own, capped so a confused model can't spin
        # forever (and so every DB this platform has a tool for — Postgres via
        # socio/risk/case tools, Neo4j via network tools, pgvector via
        # generate_case_brief's similar-case RAG — is reachable in one turn, not
        # walled off behind "only one tool call per question").
        # Every model turn is a single streaming call over the SAME growing
        # conversation. When a turn requests tools, we execute them, append the
        # function_response parts, and loop. When a turn requests no tools, its
        # text IS the final answer — and because that turn's context already
        # contains every function_response from this conversation, the model is
        # reasoning over its own tool outputs, not a cold JSON re-read by a
        # weaker second model (the old two-pass design). One thread, one voice.
        MAX_TOOL_ROUNDS = 6
        conversation: List[types.Content] = list(gemini_contents)
        tools_used: List[str] = []
        answered = False

        for round_index in range(MAX_TOOL_ROUNDS):
            round_tool_calls: List[Dict[str, Any]] = []
            round_model_parts: List[types.Part] = []
            round_text = ""
            try:
                response_stream = await self.client.aio.models.generate_content_stream(
                    model=settings.GEMINI_MODEL,
                    contents=conversation,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0,
                        tools=self._gemini_tools,
                    ),
                )
                # Text is still buffered per round — until the stream ends we
                # can't tell "intent filler emitted alongside a function_call"
                # from "the real final answer". But there is no longer a second
                # narration model downstream, so once a round turns out to be
                # tool-free, its buffered text is emitted immediately below
                # (sentence-chunked for a live feel), with no extra round-trip.
                async for chunk in response_stream:
                    for candidate in chunk.candidates or []:
                        if not candidate.content or not candidate.content.parts:
                            continue
                        for part in candidate.content.parts:
                            if part.function_call:
                                round_tool_calls.append(
                                    {"name": part.function_call.name, "args": dict(part.function_call.args or {})}
                                )
                                round_model_parts.append(part)
                            if part.text:
                                round_text += part.text
                                round_model_parts.append(part)
            except Exception as exc:
                log.error("Gemini planning stream failed", error=str(exc), round=round_index)
                if not tools_used:
                    # First round failed outright, nothing computed yet — a
                    # genuine "AI unavailable" turn, no partial results to protect.
                    yield json.dumps({
                        "type": "error",
                        "error": "ai_unavailable",
                        "message": "AI assistance is temporarily unavailable. Please retry shortly.",
                    }) + "\n"
                    yield json.dumps({"type": "done"}) + "\n"
                    return
                # A later round failed after tools already ran and their
                # results/widgets streamed — force one grounded narration below.
                break

            if not round_tool_calls:
                # Tool-free round: this text is the grounded final answer.
                for token_chunk in _chunk_for_stream(round_text):
                    yield json.dumps({"type": "token", "content": token_chunk}) + "\n"
                answered = True
                break

            conversation.append(types.Content(role="model", parts=round_model_parts))

            round_function_responses: List[types.Part] = []
            for tc in round_tool_calls:
                tool_name = tc["name"]
                tool_args = tc.get("args", {})

                yield json.dumps({"type": "tool_call", "tool": tool_name, "status": "running"}) + "\n"

                result = await self._dispatch_tool(tool_name, tool_args)
                tools_used.append(tool_name)

                widget_event = self._map_to_widget(tool_name, result)
                if widget_event:
                    yield json.dumps({"type": "widget", **widget_event}) + "\n"

                yield json.dumps({"type": "tool_result", "tool": tool_name, "data": result}) + "\n"

                # Struct/protobuf conversion inside from_function_response only
                # accepts JSON-primitive types — round-tripping through
                # json.dumps (default=str safety net) guarantees that regardless
                # of what a given tool returned, so a stray UUID/datetime/Decimal
                # can't crash the next round's request construction.
                json_safe_result = json.loads(json.dumps(result, default=str))
                round_function_responses.append(
                    types.Part.from_function_response(name=tool_name, response={"result": json_safe_result})
                )

            conversation.append(types.Content(role="user", parts=round_function_responses))

        # If the loop exhausted its rounds still requesting tools (or a later
        # round errored) without ever producing a tool-free answer, force one
        # final grounded narration with tools disabled so the turn always ends
        # in words — never in silence after the widgets already rendered.
        if not answered:
            try:
                final_answer = await self._forced_final_narration(conversation, system_instruction)
                for token_chunk in _chunk_for_stream(final_answer):
                    yield json.dumps({"type": "token", "content": token_chunk}) + "\n"
            except AiUnavailableError:
                yield json.dumps({
                    "type": "error",
                    "error": "ai_unavailable",
                    "message": "AI narration is temporarily unavailable — the tool results above are still valid.",
                }) + "\n"

        # Proactive next-actions (§10.4) — clickable chips, deterministic, no extra
        # LLM call. Only when tools actually ran (a pure conversational turn has no
        # meaningful next tool to suggest).
        followups = _build_followups(tools_used)
        if followups:
            yield json.dumps({"type": "suggestions", "items": followups}) + "\n"

        yield json.dumps({"type": "done"}) + "\n"

    async def _dispatch_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Route a tool call to the appropriate deterministic service."""
        dispatch = {
            "search_persons": lambda: self._search_persons_tool(args["query"], args.get("top_k", 10)),
            "get_graph_subset": lambda: self.network_svc.query_graph_subset(
                db=self.db,
                node_labels=args.get("node_labels"),
                edge_types=args.get("edge_types"),
                district_id=args.get("district_id"),
                crime_no_contains=args.get("crime_no_contains"),
                date_from=args.get("date_from"),
                date_to=args.get("date_to"),
                center_person_id=args.get("center_person_id"),
                depth=args.get("depth", 1),
                limit=args.get("limit", 300),
            ),
            "get_ego_network": lambda: self.network_svc.get_ego_network(args["person_id"], args.get("depth", 2)),
            "detect_communities": lambda: self.network_svc.get_communities_graph(),
            "get_predicted_links": lambda: self.network_svc.get_link_predictions(
                args["person_id"], args.get("top_k", 10)
            ),
            "compute_centrality": lambda: self.network_svc.compute_centrality(args.get("graph_data", {})),
            "get_multi_jurisdiction_offenders": lambda: self.network_svc.get_multi_jurisdiction_offenders(),
            "forecast_hotspots": lambda: self._forecast_hotspots_tool(
                district_id=args["district_id"],
                crime_head_id=args["crime_head_id"],
                target_date=__import__("datetime").date.fromisoformat(args["target_date"]),
                district_stress_index=args.get("stress_index"),
            ),
            "compute_risk_score": lambda: self._compute_risk_score_tool(
                args["person_id"], args.get("role", "INVESTIGATOR")
            ),
            "detect_financial_structuring": lambda: self.financial_svc.detect_structuring(args["account"]),
            "detect_funnel_account": lambda: self.financial_svc.detect_funnel_account(args["account"]),
            "detect_financial_cycles": lambda: self.financial_svc.detect_cycles_in_graph(),
            "detect_organized_clusters": lambda: self.financial_svc.detect_organized_clusters(
                args["flagged_accounts"]
            ),
            "run_financial_scan": lambda: self.financial_svc.run_full_scan(args["accounts"]),
            "get_socio_indicators": lambda: self.socio_svc.get_indicators(
                args["district_id"], args.get("year_from"), args.get("year_to")
            ),
            "get_crime_stats": lambda: self.socio_svc.get_crime_stats(
                args["district_id"], args.get("year"), args.get("crime_head_id")
            ),
            "get_gwr_coefficients": lambda: self.socio_svc.get_gwr_outputs(args["district_id"]),
            "get_gwr_map": lambda: self.socio_svc.get_all_districts_latest_gwr(),
            "get_case_workspace": lambda: self._get_case_workspace_tool(args["case_id"]),
            "extract_document_text": lambda: self._extract_document_text_tool(args["document_id"]),
            "extract_entities": lambda: self._extract_entities_tool(args["text"]),
            "generate_case_brief": lambda: self.investigator_svc.generate_case_brief(
                __import__("uuid").UUID(args["case_id"])
            ),
            "get_active_alerts": lambda: self._get_active_alerts_tool(
                args.get("alert_type"), args.get("limit", 20)
            ),
            "get_mo_linkage_clusters": lambda: self.hawkes_svc.get_mo_linkage_clusters(
                crime_head_id=args["crime_head_id"], min_similarity=args.get("min_similarity", 0.7)
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

    async def _forecast_hotspots_tool(
        self, district_id: int, crime_head_id: int, target_date, district_stress_index: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        hawkes_svc.forecast() returns a list of ForecastResult dataclasses
        (with a nested GridCell dataclass and a date field) — not JSON-
        serializable as-is. Mirrors the exact dict shape
        app/api/v1/endpoints/trends.py's /hotspots route already produces, so
        this stays a plain read with no duplicated computation logic.
        """
        results = await self.hawkes_svc.forecast(
            district_id=district_id,
            crime_head_id=crime_head_id,
            target_date=target_date,
            district_stress_index=district_stress_index,
        )
        return [
            {
                "lat_center": r.cell.lat_center,
                "lng_center": r.cell.lng_center,
                "predicted_rate": r.predicted_rate,
                "background_component": r.background_component,
                "near_repeat_component": r.near_repeat_component,
                "forecast_date": str(r.forecast_date),
            }
            for r in results
        ]

    async def _compute_risk_score_tool(self, person_id: str, role: str) -> Dict[str, Any]:
        """
        risk_svc.compute_risk_score() returns an unpersisted RiskScore ORM row
        (not JSON-serializable, and never written to the DB) — the REST route
        (app/api/v1/endpoints/risk.py) does the add/flush/refresh + dict
        serialization itself rather than in the service, so this replicates
        that exact persistence + shape rather than silently computing and
        discarding a score when reached through chat.
        """
        score = await self.risk_svc.compute_risk_score(UUID(person_id), role)
        if score is None:
            return {"error": "Risk score blocked — criminal history not human-verified, or person not found"}

        self.db.add(score)
        await self.db.flush()
        await self.db.refresh(score)

        from app.services.ml_registry import get_model_card

        return {
            "score_id": str(score.id),
            "person_id": person_id,
            "score": score.score,
            "model_version": score.model_version,
            "shap_decomposition": score.shap_decomposition,
            "model_card": get_model_card(score.model_version),
            "human_reviewed": score.human_reviewed,
            "computed_at": str(score.computed_at),
            "disclaimer": (
                "Risk score is for investigative attention only. "
                "Human sign-off required before any operational decision. "
                "Protected demographic attributes were not used as features."
            ),
        }

    async def _search_persons_tool(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        ILIKE name search, masked the same way GET /persons/search masks it
        for this same user's role (never leaks an unmasked name/address to a
        role that wouldn't see it via the REST endpoint either).
        """
        matches = await self.person_repo.search_by_name(query, limit=top_k)
        has_pii = self.current_user is not None and role_has_permission(self.current_user.role, Permission.VIEW_PII_UNMASKED)
        return [
            {
                "person_id": str(person.id),
                "name": mask_person_display_name(person.full_name, has_pii),
                "aliases": person.aliases,
                "human_verified": person.human_verified,
            }
            for person in matches
        ]

    async def _get_case_workspace_tool(self, case_id: str) -> Dict[str, Any]:
        """
        Reuses workspace_service.build_case_workspace — the exact same
        district-scoping + PII/religion/caste masking the REST workspace
        endpoint applies, keyed to whichever user is asking through chat
        (self.current_user), not a role string the LLM could pick itself.
        """
        from app.services.workspace_service import build_case_workspace

        if self.current_user is None:
            return {"error": "No authenticated user context for this tool call"}

        workspace = await build_case_workspace(self.db, UUID(case_id), self.current_user)
        if workspace is None:
            return {"error": "Case not found, or not visible to your district scope"}
        return workspace

    async def _extract_document_text_tool(self, document_id: str) -> Dict[str, Any]:
        """
        Tool variant of POST /documents/ocr — takes a document_id and resolves
        the blob via the storage provider + the existing Document row, rather
        than raw upload bytes (which an LLM tool call can't carry), so the
        assistant can OCR something already in the system without a re-upload.
        """
        from sqlalchemy import select

        from app.core.ocr import get_ocr_provider
        from app.core.storage import get_storage_provider
        from app.models.document import Document

        doc = (await self.db.execute(select(Document).where(Document.id == UUID(document_id)))).scalar_one_or_none()
        if doc is None:
            return {"error": "Document not found"}

        content = await get_storage_provider().get(doc.raw_file_ref)
        return await get_ocr_provider().extract_text(content, doc.original_filename)

    async def _extract_entities_tool(self, text: str) -> Dict[str, Any]:
        from app.core.nlp import get_nlp_provider

        entities = await get_nlp_provider().extract_entities(text)
        return {"entities": entities, "count": len(entities)}

    async def _get_active_alerts_tool(self, alert_type: Optional[str] = None, limit: int = 20) -> Any:
        """
        Read the standing early-warning alerts (capability #8) — repeat-offender and
        organized-group signals. Gated to the same permission the REST /alerts
        endpoints require, so chat never surfaces an alert a role couldn't see there.
        """
        from sqlalchemy import select

        from app.models.alert import Alert
        from app.models.enums import AlertStatus, AlertType

        if self.current_user is None or not role_has_permission(
            self.current_user.role, Permission.VIEW_NETWORK_ADVANCED
        ):
            return {"error": "Your role does not have access to early-warning alerts."}

        stmt = select(Alert).where(Alert.status != AlertStatus.DISMISSED)
        if alert_type:
            try:
                stmt = stmt.where(Alert.alert_type == AlertType(alert_type))
            except ValueError:
                return {"error": f"Unknown alert_type '{alert_type}'."}
        stmt = stmt.order_by(Alert.created_at.desc()).limit(min(limit, 100))

        alerts = (await self.db.execute(stmt)).scalars().all()
        return [
            {
                "id": str(a.id),
                "alert_type": a.alert_type.value,
                "severity": a.severity.value,
                "status": a.status.value,
                "title": a.title,
                "description": a.description,
                "confidence": a.confidence,
                "source_tool": a.source_tool,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ]

    async def _forced_final_narration(
        self,
        conversation: List[types.Content],
        system_instruction: str,
    ) -> str:
        """
        Fallback narration for the rare turn that exhausted MAX_TOOL_ROUNDS still
        asking for tools (or errored mid-loop) without ever producing a tool-free
        answer. Unlike the retired two-pass validator, this is NOT a cold re-read
        of a JSON dump by a weaker model — it runs GEMINI_MODEL over the exact
        same grounded conversation the loop built (every function_response part
        included), just with tools disabled so it is forced to answer in words
        instead of requesting yet another tool. Same voice, same grounding.
        """
        response = await resilient_vertex_call(
            self.client.aio.models.generate_content,
            model=settings.GEMINI_MODEL,
            contents=conversation
            + [
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            text=(
                                "Stop calling tools now and give the investigator your final answer, "
                                "grounded strictly in the tool results already gathered above."
                            )
                        )
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0,
                # No tools bound: the model can no longer defer with another
                # function_call, so this always returns prose.
            ),
        )
        return response.text

    @staticmethod
    def _map_to_widget(tool_name: str, result: Any) -> Optional[Dict[str, Any]]:
        """Map a tool output to the appropriate widget type (§10.2). No widget
        for a None/empty result (e.g. detect_structuring found no match) — an
        empty widget frame with a literal "null" JSON dump inside isn't a
        visualization, the narration already says "no data found" in text."""
        if result is None or result == [] or result == {}:
            return None
        widget_map = {
            "search_persons": "person_search_results",
            "get_graph_subset": "force_directed_graph",
            "get_ego_network": "force_directed_graph",
            "detect_communities": "force_directed_graph",
            "get_predicted_links": "predicted_links",
            "compute_centrality": "centrality_scores",
            "get_multi_jurisdiction_offenders": "multi_jurisdiction_offenders",
            "forecast_hotspots": "hotspot_map",
            "compute_risk_score": "risk_profile_card",
            "detect_financial_structuring": "flow_diagram",
            "detect_funnel_account": "flow_diagram",
            "detect_financial_cycles": "flow_diagram",
            "detect_organized_clusters": "flow_diagram",
            "run_financial_scan": "flow_diagram",
            "get_socio_indicators": "socio_trend",
            "get_crime_stats": "crime_stats_trend",
            "get_gwr_coefficients": "gwr_coefficients",
            "get_gwr_map": "gwr_map",
            "get_case_workspace": "case_workspace",
            "extract_entities": "entities_list",
            "generate_case_brief": "case_timeline",
            "get_active_alerts": "alerts_list",
            "get_mo_linkage_clusters": "mo_linkage_clusters",
        }
        widget_type = widget_map.get(tool_name)
        if widget_type:
            return {"widget_type": widget_type, "data": result}
        return None

    @staticmethod
    def _build_tool_schemas() -> List[Dict]:
        """Minimal tool schemas for LLM function-calling (plain JSON-schema dicts —
        provider-agnostic; see _json_schema_to_gemini_schema for the Gemini binding)."""
        return [
            {
                "name": "search_persons",
                "description": "Search for persons by name (ILIKE partial match). Use this to resolve a name the investigator mentioned into a person_id before calling any tool that needs one — never guess a person_id.",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}}, "required": ["query"]},
            },
            {
                "name": "get_graph_subset",
                "description": (
                    "Query a filtered subgraph across the whole network — persons, incidents, financial accounts "
                    "and their relationships — not scoped to one person. Use this for questions about a category or "
                    "region rather than one specific person (e.g. 'show accused persons in district 3', 'show accounts "
                    "connected by transactions', 'show everyone linked to incidents matching THEFT'). Combine "
                    "center_person_id+depth to instead center the subgraph on one person you've already resolved."
                ),
                "parameters": {"type": "object", "properties": {
                    "node_labels": {"type": "array", "items": {"type": "string", "enum": ["Person", "Incident", "Account"]}},
                    "edge_types": {"type": "array", "items": {"type": "string", "enum": [
                        "ACCUSED_IN", "VICTIM_IN", "WITNESSED", "ASSOCIATED_WITH", "TRANSACTED_WITH", "PREDICTED_LINK",
                    ]}},
                    "district_id": {"type": "integer"},
                    "crime_no_contains": {"type": "string"},
                    "date_from": {"type": "string"},
                    "date_to": {"type": "string"},
                    "center_person_id": {"type": "string"},
                    "depth": {"type": "integer"},
                    "limit": {"type": "integer"},
                }},
            },
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
                "name": "get_predicted_links",
                "description": "Get plausible-but-unconfirmed network links (GCN link prediction) for a person — a lead, never rendered as a confirmed edge",
                "parameters": {"type": "object", "properties": {"person_id": {"type": "string"}, "top_k": {"type": "integer"}}, "required": ["person_id"]},
            },
            {
                "name": "compute_centrality",
                "description": "Compute PageRank (surfaces the likely operational leader) and betweenness (surfaces the broker bridging two groups) centrality over a given graph",
                "parameters": {"type": "object", "properties": {"graph_data": {"type": "object", "properties": {
                    "nodes": {"type": "array", "items": {"type": "object", "properties": {}}},
                    "edges": {"type": "array", "items": {"type": "object", "properties": {}}},
                }}}},
            },
            {
                "name": "get_multi_jurisdiction_offenders",
                "description": "List persons whose accused-in incidents span more than one police unit/jurisdiction — a signal of organized or mobile criminal activity",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "detect_funnel_account",
                "description": "Detect a funnel/mule account pattern (inflow burst, dormancy, then rapid outflow) for a given account",
                "parameters": {"type": "object", "properties": {"account": {"type": "string"}}, "required": ["account"]},
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
                "name": "detect_organized_clusters",
                "description": "Run community detection (Louvain) over already-flagged accounts to find organized clusters — the third financial-crime typology beyond structuring and funnel accounts",
                "parameters": {"type": "object", "properties": {"flagged_accounts": {"type": "array", "items": {"type": "string"}}}, "required": ["flagged_accounts"]},
            },
            {
                "name": "run_financial_scan",
                "description": "Run every financial-crime detector (structuring, funnel account, layering cycles, organized clusters) over a given account list in one pass",
                "parameters": {"type": "object", "properties": {"accounts": {"type": "array", "items": {"type": "string"}}}, "required": ["accounts"]},
            },
            {
                "name": "get_socio_indicators",
                "description": "Get district-year socio-economic indicators (literacy, unemployment, urbanization, sex ratio, composite stress index) — place-level only, never tied to individual persons",
                "parameters": {"type": "object", "properties": {
                    "district_id": {"type": "integer"}, "year_from": {"type": "integer"}, "year_to": {"type": "integer"},
                }, "required": ["district_id"]},
            },
            {
                "name": "get_crime_stats",
                "description": "Get aggregate district-year-crime_head counts (raw and CHI-weighted)",
                "parameters": {"type": "object", "properties": {
                    "district_id": {"type": "integer"}, "year": {"type": "integer"}, "crime_head_id": {"type": "integer"},
                }, "required": ["district_id"]},
            },
            {
                "name": "get_gwr_coefficients",
                "description": "Get the latest Geographically Weighted Regression runs for one district — locally-varying coefficients for how literacy/unemployment/urbanization predict CHI-weighted crime harm there",
                "parameters": {"type": "object", "properties": {"district_id": {"type": "integer"}}, "required": ["district_id"]},
            },
            {
                "name": "get_gwr_map",
                "description": "Get the latest GWR coefficients for every district at once, with centroid coordinates, for a statewide map view",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "extract_document_text",
                "description": "OCR/extract the text of an already-uploaded document by its document_id",
                "parameters": {"type": "object", "properties": {"document_id": {"type": "string"}}, "required": ["document_id"]},
            },
            {
                "name": "extract_entities",
                "description": "Extract named entities (persons, locations, organizations) from a block of text",
                "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            },
            {
                "name": "generate_case_brief",
                "description": "Generate a full one-click investigator case brief",
                "parameters": {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
            },
            {
                "name": "get_case_workspace",
                "description": "Get the full investigator workspace view for a case — core FIR fields, suspects/witnesses, evidence documents, and status timeline, masked per the requester's permissions",
                "parameters": {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
            },
            {
                "name": "get_active_alerts",
                "description": "List standing early-warning alerts — proactive signals for repeat offenders (multi-jurisdiction) and organized groups (dense co-offending communities). Use for questions like 'what should I be watching?', 'any active warnings?', or 'show gang-activity alerts'.",
                "parameters": {"type": "object", "properties": {
                    "alert_type": {"type": "string", "enum": ["repeat_offender", "organized_group", "emerging_hotspot", "financial"]},
                    "limit": {"type": "integer"},
                }},
            },
            {
                "name": "get_mo_linkage_clusters",
                "description": "Behavioral crime-series linkage for a crime head — candidate same-offender series grouped by modus operandi (trained MO-linkage model). Use for 'are these burglaries the same person?', 'find MO series for crime head 3', or linking a probable series before an arrest. Leads, not confirmed.",
                "parameters": {"type": "object", "properties": {
                    "crime_head_id": {"type": "integer"},
                    "min_similarity": {"type": "number"},
                }, "required": ["crime_head_id"]},
            },
        ]
