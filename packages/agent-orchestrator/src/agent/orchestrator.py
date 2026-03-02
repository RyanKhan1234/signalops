"""LangGraph agent graph for the SignalOps Agent Orchestrator.

Graph topology:
  [START]
    → detect_intent
    → plan_tools
    → execute_tools
    → process_articles
    → compose_digest
    → validate_guardrails  (loops back to compose_digest on failure, max 2 retries)
    → log_trace
  [END]

State is a typed dict that flows through every node.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agent.composer import compose_digest
from src.agent.guardrails import collect_known_urls, validate_and_sanitize
from src.agent.intent import detect_intent
from src.agent.planner import plan_tool_calls
from src.agent.processor import (
    cluster_articles,
    deduplicate_articles,
    extract_signals,
    generate_action_items,
    identify_risks_and_opportunities,
)
from src.models.digest import (
    ActionItem,
    Article,
    DetectedIntent,
    DigestResponse,
    KeySignal,
    MCPToolResult,
    Opportunity,
    Risk,
    ToolPlan,
)
from src.models.trace import ToolTraceEntry
from src.services.traceability import TraceabilityClient
from src.tools.mcp_client import MCPClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------


class OrchestratorState(TypedDict):
    """Typed state dict that flows through the LangGraph nodes."""

    # Input
    prompt: str
    correlation_id: str

    # Intent detection output
    intent: DetectedIntent | None

    # Planner output
    tool_plan: ToolPlan | None

    # Tool execution outputs
    tool_results: list[MCPToolResult]
    tool_traces: list[ToolTraceEntry]

    # Article processing outputs
    all_articles: list[Article]

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

    # Error state
    error: str | None


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------


async def node_detect_intent(state: OrchestratorState) -> dict[str, Any]:
    """Node 1: Detect intent and extract entities from the user prompt."""
    logger.info("[node_detect_intent] prompt=%s", state["prompt"][:80])
    try:
        intent = await detect_intent(state["prompt"])
        logger.info("[node_detect_intent] intent_type=%s entities=%s", intent.intent_type, intent.entities)
        return {"intent": intent}
    except Exception as exc:
        logger.error("[node_detect_intent] failed: %s", exc)
        return {"error": f"Intent detection failed: {exc}"}


async def node_plan_tools(state: OrchestratorState) -> dict[str, Any]:
    """Node 2: Plan which MCP tool calls to make based on intent."""
    if state.get("error") or state.get("intent") is None:
        return {}
    intent: DetectedIntent = state["intent"]
    try:
        tool_plan = plan_tool_calls(intent)
        logger.info("[node_plan_tools] planned %d calls", len(tool_plan.calls))
        return {"tool_plan": tool_plan}
    except Exception as exc:
        logger.error("[node_plan_tools] failed: %s", exc)
        return {"error": f"Tool planning failed: {exc}"}


async def node_execute_tools(state: OrchestratorState) -> dict[str, Any]:
    """Node 3: Execute all planned tool calls against the MCP Wrapper."""
    if state.get("error") or state.get("tool_plan") is None:
        return {}
    tool_plan: ToolPlan = state["tool_plan"]
    correlation_id: str = state.get("correlation_id", "")

    try:
        async with MCPClient(correlation_id=correlation_id) as mcp:
            results_and_traces = await mcp.call_tools_parallel(tool_plan.calls)

        tool_results = [r for r, _ in results_and_traces]
        tool_traces = [t for _, t in results_and_traces]
        all_articles = deduplicate_articles(
            [article for result in tool_results for article in result.articles]
        )

        logger.info(
            "[node_execute_tools] %d calls → %d total articles (after dedup)",
            len(tool_results),
            len(all_articles),
        )
        return {
            "tool_results": tool_results,
            "tool_traces": tool_traces,
            "all_articles": all_articles,
        }
    except Exception as exc:
        logger.error("[node_execute_tools] failed: %s", exc)
        return {"error": f"Tool execution failed: {exc}"}


async def node_process_articles(state: OrchestratorState) -> dict[str, Any]:
    """Node 4: Run the full article processing pipeline.

    This is a single combined node that covers:
    - Clustering
    - Signal extraction
    - Risk / opportunity identification
    - Action item generation
    """
    if state.get("error"):
        return {}
    all_articles: list[Article] = state.get("all_articles", [])
    logger.info("[node_process_articles] processing %d articles", len(all_articles))

    # If no articles at all, short-circuit — guardrails will handle the empty case
    if not all_articles:
        logger.info("[node_process_articles] no articles — skipping processing")
        return {}

    try:
        clusters = await cluster_articles(all_articles)
        signals = await extract_signals(clusters)
        risks, opportunities = await identify_risks_and_opportunities(signals, all_articles)
        action_items = await generate_action_items(risks, opportunities)

        # Store processed outputs in state via a transient key
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
    """Node 5: Compose the structured digest from processed pipeline outputs."""
    if state.get("error") or state.get("intent") is None:
        return {}

    intent: DetectedIntent = state["intent"]
    all_articles: list[Article] = state.get("all_articles", [])
    signals = state.get("_signals", [])
    risks = state.get("_risks", [])
    opportunities = state.get("_opportunities", [])
    action_items = state.get("_action_items", [])
    tool_traces: list[ToolTraceEntry] = state.get("tool_traces", [])

    try:
        draft = await compose_digest(
            intent=intent,
            all_articles=all_articles,
            signals=signals,
            risks=risks,
            opportunities=opportunities,
            action_items=action_items,
            tool_traces=tool_traces,
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

    tool_results: list[MCPToolResult] = state.get("tool_results", [])
    known_urls = collect_known_urls(tool_results)
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

    # Add all nodes
    graph.add_node("detect_intent", node_detect_intent)
    graph.add_node("plan_tools", node_plan_tools)
    graph.add_node("execute_tools", node_execute_tools)
    graph.add_node("process_articles", node_process_articles)
    graph.add_node("compose_digest", node_compose_digest)
    graph.add_node("validate_guardrails", node_validate_guardrails)
    graph.add_node("log_trace", node_log_trace)

    # Add edges (sequential pipeline)
    graph.add_edge(START, "detect_intent")
    graph.add_edge("detect_intent", "plan_tools")
    graph.add_edge("plan_tools", "execute_tools")
    graph.add_edge("execute_tools", "process_articles")
    graph.add_edge("process_articles", "compose_digest")
    graph.add_edge("compose_digest", "validate_guardrails")

    # Conditional edge: guardrails can loop back to compose_digest or proceed to log_trace
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


async def run_pipeline(prompt: str, correlation_id: str = "") -> DigestResponse:
    """Execute the full orchestrator pipeline for a given prompt.

    Args:
        prompt: The user's natural language query.
        correlation_id: Optional request correlation ID for distributed tracing.

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
        "intent": None,
        "tool_plan": None,
        "tool_results": [],
        "tool_traces": [],
        "all_articles": [],
        "draft_digest": None,
        "final_digest": None,
        "guardrails_retries": 0,
        "error": None,
        "_signals": [],
        "_risks": [],
        "_opportunities": [],
        "_action_items": [],
    }

    logger.info("Starting pipeline for correlation_id=%s prompt='%s'", correlation_id, prompt[:80])
    final_state = await compiled_graph.ainvoke(initial_state)

    if final_state.get("error"):
        error_msg = final_state["error"]
        logger.error("Pipeline failed: %s", error_msg)
        raise RuntimeError(f"Orchestrator pipeline failed: {error_msg}")

    final_digest = final_state.get("final_digest")
    if final_digest is None:
        raise RuntimeError("Pipeline completed but produced no digest")

    return final_digest
