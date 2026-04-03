"""LangGraph agent graph for the SignalOps Agent Orchestrator.

Graph topology:
  [START]
    → fetch_user_context
    → detect_intent
    → agentic_research   (OpenAI tool_use loop via LangChain — decides tools, inspects results, iterates)
    → process_articles
    → compose_digest
    → validate_guardrails  (loops back to compose_digest on failure, max 2 retries)
    → log_trace
  [END]

State is a typed dict that flows through every node.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from src.agent.composer import compose_digest
from src.agent.guardrails import validate_and_sanitize
from src.agent.intent import detect_intent
from src.agent.processor import (
    cluster_articles,
    deduplicate_articles,
    extract_signals,
    generate_action_items,
    identify_risks_and_opportunities,
)
from src.agent.researcher import StreamCallback, run_research_loop
from src.config import settings
from src.models.digest import (
    ActionItem,
    Article,
    DetectedIntent,
    DigestResponse,
    KeySignal,
    MCPToolResult,
    Opportunity,
    Risk,
)
from src.models.trace import ToolTraceEntry
from src.services.traceability import TraceabilityClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------


class OrchestratorState(TypedDict):
    """Typed state dict that flows through the LangGraph nodes."""

    # Input
    prompt: str
    correlation_id: str
    user_id: str

    # User context (fetched from traceability store)
    user_context: str

    # Intent detection output
    intent: DetectedIntent | None

    # Agentic research outputs
    tool_results: list[MCPToolResult]
    tool_traces: list[ToolTraceEntry]
    all_articles: list[Article]
    research_summary: str
    reasoning_steps: list[str]

    # Processing pipeline outputs (set by node_process_articles, read by node_compose_digest)
    _signals: list[KeySignal]
    _risks: list[Risk]
    _opportunities: list[Opportunity]
    _action_items: list[ActionItem]

    # Composed digest (pre-guardrails)
    draft_digest: DigestResponse | None

    # Validated digest (post-guardrails)
    final_digest: DigestResponse | None

    # Guardrails retry counter
    guardrails_retries: int

    # Streaming callback (not serialized — set at pipeline entry)
    _stream_callback: StreamCallback

    # Error state
    error: str | None


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------


def _safe_emit(callback: StreamCallback, event: str, data: dict[str, Any]) -> None:
    """Emit a streaming event, swallowing errors."""
    if callback is None:
        return
    try:
        callback(event, data)
    except Exception as exc:
        logger.warning("Stream callback error: %s", exc)


async def node_fetch_user_context(state: OrchestratorState) -> dict[str, Any]:
    """Node 0: Fetch user context from the Traceability Store.

    Best-effort — if the store is unreachable or the profile doesn't exist,
    the pipeline continues with an empty context string.
    """
    user_id = state.get("user_id", "default")
    base_url = settings.traceability_store_url.rstrip("/")
    url = f"{base_url}/api/profiles/{user_id}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
        if resp.status_code == 200:
            context = resp.json().get("context", "")
            if context:
                logger.info("[node_fetch_user_context] loaded %d-char context for user=%s", len(context), user_id)
            return {"user_context": context}
    except Exception as exc:
        logger.warning("[node_fetch_user_context] could not fetch profile for %s: %s", user_id, exc)

    return {"user_context": ""}


async def node_detect_intent(state: OrchestratorState) -> dict[str, Any]:
    """Node 1: Detect intent and extract entities from the user prompt."""
    logger.info("[node_detect_intent] prompt=%s", state["prompt"][:80])
    on_event: StreamCallback = state.get("_stream_callback")

    try:
        intent = await detect_intent(state["prompt"])
        logger.info("[node_detect_intent] intent_type=%s entities=%s", intent.intent_type, intent.entities)

        if on_event:
            _safe_emit(on_event, "intent", {
                "intent_type": intent.intent_type,
                "entities": intent.entities,
                "time_range": intent.time_range,
            })

        return {"intent": intent}
    except Exception as exc:
        logger.error("[node_detect_intent] failed: %s", exc)
        return {"error": f"Intent detection failed: {exc}"}


async def node_agentic_research(state: OrchestratorState) -> dict[str, Any]:
    """Node 2: Agentic research loop — Claude decides which tools to call."""
    if state.get("error") or state.get("intent") is None:
        return {}

    intent: DetectedIntent = state["intent"]
    correlation_id: str = state.get("correlation_id", "")
    on_event: StreamCallback = state.get("_stream_callback")

    user_context: str = state.get("user_context", "")

    try:
        result = await run_research_loop(
            intent=intent,
            correlation_id=correlation_id,
            on_event=on_event,
            user_context=user_context,
        )

        all_articles = deduplicate_articles(result.articles)

        logger.info(
            "[node_agentic_research] %d tool calls → %d articles (after dedup), summary=%d chars",
            len(result.tool_traces),
            len(all_articles),
            len(result.research_summary),
        )
        return {
            "tool_traces": result.tool_traces,
            "all_articles": all_articles,
            "research_summary": result.research_summary,
            "reasoning_steps": result.reasoning_steps,
        }
    except Exception as exc:
        logger.error("[node_agentic_research] failed: %s", exc)
        return {"error": f"Agentic research failed: {exc}"}


async def node_process_articles(state: OrchestratorState) -> dict[str, Any]:
    """Node 3: Run the full article processing pipeline.

    This is a single combined node that covers:
    - Clustering
    - Signal extraction
    - Risk / opportunity identification
    - Action item generation
    """
    if state.get("error"):
        return {}
    all_articles: list[Article] = state.get("all_articles", [])
    on_event: StreamCallback = state.get("_stream_callback")
    logger.info("[node_process_articles] processing %d articles", len(all_articles))

    user_context: str = state.get("user_context", "")

    if not all_articles:
        logger.info("[node_process_articles] no articles — skipping processing")
        return {}

    try:
        if on_event:
            _safe_emit(on_event, "processing", {"stage": "clustering"})
        clusters = await cluster_articles(all_articles)

        if on_event:
            _safe_emit(on_event, "processing", {"stage": "extracting_signals"})
        signals = await extract_signals(clusters)

        if on_event:
            _safe_emit(on_event, "processing", {"stage": "identifying_risks"})
        risks, opportunities = await identify_risks_and_opportunities(signals, all_articles, user_context=user_context)

        if on_event:
            _safe_emit(on_event, "processing", {"stage": "generating_actions"})
        action_items = await generate_action_items(risks, opportunities, user_context=user_context)

        return {
            "_signals": signals,
            "_risks": risks,
            "_opportunities": opportunities,
            "_action_items": action_items,
        }
    except Exception as exc:
        logger.error("[node_process_articles] failed: %s", exc)
        return {"error": f"Article processing failed: {exc}"}


async def node_compose_digest(state: OrchestratorState) -> dict[str, Any]:
    """Node 4: Compose the structured digest from processed pipeline outputs."""
    if state.get("error") or state.get("intent") is None:
        return {}

    intent: DetectedIntent = state["intent"]
    all_articles: list[Article] = state.get("all_articles", [])
    signals = state.get("_signals", [])
    risks = state.get("_risks", [])
    opportunities = state.get("_opportunities", [])
    action_items = state.get("_action_items", [])
    tool_traces: list[ToolTraceEntry] = state.get("tool_traces", [])
    research_summary: str = state.get("research_summary", "")
    reasoning_steps: list[str] = state.get("reasoning_steps", [])
    on_event: StreamCallback = state.get("_stream_callback")

    if on_event:
        _safe_emit(on_event, "composing", {"stage": "executive_summary"})

    user_context: str = state.get("user_context", "")

    try:
        draft = await compose_digest(
            intent=intent,
            all_articles=all_articles,
            signals=signals,
            risks=risks,
            opportunities=opportunities,
            action_items=action_items,
            tool_traces=tool_traces,
            research_summary=research_summary,
            reasoning_steps=reasoning_steps,
            user_context=user_context,
        )
        logger.info("[node_compose_digest] draft digest report_id=%s", draft.report_id)
        return {"draft_digest": draft}
    except Exception as exc:
        logger.error("[node_compose_digest] failed: %s", exc)
        return {"error": f"Digest composition failed: {exc}"}


async def node_validate_guardrails(state: OrchestratorState) -> dict[str, Any]:
    """Node 6: Validate and sanitize the draft digest using guardrails.

    If validation drops all content and retries remain, loops back to compose_digest.
    After max retries, returns the empty-result digest.
    """
    if state.get("error"):
        return {}
    draft: DigestResponse | None = state.get("draft_digest")
    if draft is None:
        logger.warning("[node_validate_guardrails] no draft digest — returning empty result")
        return {"final_digest": None}

    all_articles: list[Article] = state.get("all_articles", [])
    known_urls = {a.url for a in all_articles if a.url}
    retries: int = state.get("guardrails_retries", 0)

    try:
        validated = validate_and_sanitize(draft, known_urls)
        # Check if result is empty (no signals, no risks, no opps)
        is_empty = not validated.key_signals and not validated.risks and not validated.opportunities

        if is_empty and retries < 2 and state.get("all_articles"):
            # Retry: loop back to compose_digest
            logger.info(
                "[node_validate_guardrails] empty result after guardrails (retry %d/2) — recomposing",
                retries + 1,
            )
            return {
                "guardrails_retries": retries + 1,
                "draft_digest": None,  # Clear draft so compose re-runs
            }

        logger.info(
            "[node_validate_guardrails] digest validated — signals=%d risks=%d opps=%d",
            len(validated.key_signals),
            len(validated.risks),
            len(validated.opportunities),
        )
        return {"final_digest": validated}
    except Exception as exc:
        logger.error("[node_validate_guardrails] validation error: %s", exc)
        return {"error": f"Guardrails validation failed: {exc}"}


async def node_log_trace(state: OrchestratorState) -> dict[str, Any]:
    """Node 7: Log the completed digest and tool trace to the Traceability Store."""
    final: DigestResponse | None = state.get("final_digest")
    if final is None:
        logger.warning("[node_log_trace] no final digest to log")
        return {}

    try:
        client = TraceabilityClient()
        await client.log_report(final)
        logger.info("[node_log_trace] logged report %s to traceability store", final.report_id)
    except Exception as exc:
        # Non-fatal: log the error but don't fail the pipeline
        logger.error("[node_log_trace] failed to log trace: %s — continuing", exc)

    return {}


# ---------------------------------------------------------------------------
# Graph routing
# ---------------------------------------------------------------------------


def should_recompose(state: OrchestratorState) -> str:
    """Routing function: after guardrails, decide whether to recompose or finish."""
    if state.get("error"):
        return "log_trace"
    # If draft was cleared and retries remain, go back to compose
    if state.get("draft_digest") is None and state.get("guardrails_retries", 0) > 0:
        final = state.get("final_digest")
        if final is None:
            return "compose_digest"
    return "log_trace"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    """Construct and compile the LangGraph state graph.

    Returns:
        A compiled StateGraph ready to invoke.
    """
    graph = StateGraph(OrchestratorState)

    graph.add_node("fetch_user_context", node_fetch_user_context)
    graph.add_node("detect_intent", node_detect_intent)
    graph.add_node("agentic_research", node_agentic_research)
    graph.add_node("process_articles", node_process_articles)
    graph.add_node("compose_digest", node_compose_digest)
    graph.add_node("validate_guardrails", node_validate_guardrails)
    graph.add_node("log_trace", node_log_trace)

    graph.add_edge(START, "fetch_user_context")
    graph.add_edge("fetch_user_context", "detect_intent")
    graph.add_edge("detect_intent", "agentic_research")
    graph.add_edge("agentic_research", "process_articles")
    graph.add_edge("process_articles", "compose_digest")
    graph.add_edge("compose_digest", "validate_guardrails")

    graph.add_conditional_edges(
        "validate_guardrails",
        should_recompose,
        {
            "compose_digest": "compose_digest",
            "log_trace": "log_trace",
        },
    )
    graph.add_edge("log_trace", END)

    return graph


# Build the compiled graph (module-level singleton)
_graph = build_graph()
compiled_graph = _graph.compile()


async def run_pipeline(
    prompt: str,
    correlation_id: str = "",
    on_event: StreamCallback = None,
    user_id: str = "default",
) -> DigestResponse:
    """Execute the full orchestrator pipeline for a given prompt.

    Args:
        prompt: The user's natural language query.
        correlation_id: Optional request correlation ID for distributed tracing.
        on_event: Optional callback for streaming progress events.
        user_id: User identifier for loading personalized context.

    Returns:
        The final validated DigestResponse.

    Raises:
        RuntimeError: If the pipeline encounters a fatal error.
    """
    import uuid

    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    initial_state: OrchestratorState = {
        "prompt": prompt,
        "correlation_id": correlation_id,
        "user_id": user_id,
        "user_context": "",
        "intent": None,
        "tool_results": [],
        "tool_traces": [],
        "all_articles": [],
        "research_summary": "",
        "reasoning_steps": [],
        "draft_digest": None,
        "final_digest": None,
        "guardrails_retries": 0,
        "_stream_callback": on_event,
        "error": None,
        "_signals": [],
        "_risks": [],
        "_opportunities": [],
        "_action_items": [],
    }

    logger.info("Starting pipeline for correlation_id=%s prompt='%s'", correlation_id, prompt[:80])
    try:
        final_state = await asyncio.wait_for(
            compiled_graph.ainvoke(initial_state),
            timeout=180.0,
        )
    except asyncio.TimeoutError:
        raise RuntimeError("Orchestrator pipeline timed out after 180 seconds")

    if final_state.get("error"):
        error_msg = final_state["error"]
        logger.error("Pipeline failed: %s", error_msg)
        raise RuntimeError(f"Orchestrator pipeline failed: {error_msg}")

    final_digest = final_state.get("final_digest")
    if final_digest is None:
        raise RuntimeError("Pipeline completed but produced no digest")

    return final_digest
