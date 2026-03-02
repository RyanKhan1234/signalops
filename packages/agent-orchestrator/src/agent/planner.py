"""Tool call planner for the Agent Orchestrator.

Maps a DetectedIntent to an ordered list of MCP tool calls.
Calls in the same parallel_group can be executed concurrently.
"""

from __future__ import annotations

import logging

from src.models.digest import DetectedIntent, PlannedToolCall, ToolPlan

logger = logging.getLogger(__name__)

# Maximum number of entities to fan out over per plan (prevents runaway API usage)
MAX_ENTITIES = 5
# Default number of results to request per tool call
DEFAULT_NUM_RESULTS = 10


def plan_tool_calls(intent: DetectedIntent) -> ToolPlan:
    """Derive an ordered, parallelizable list of MCP tool calls from an intent.

    Each PlannedToolCall has a parallel_group field. Calls with the same
    group number can be executed concurrently; groups are executed sequentially
    in ascending order.

    Args:
        intent: The detected intent with entities and time range.

    Returns:
        A ToolPlan containing the intent and ordered list of calls.
    """
    logger.info(
        "Planning tool calls for intent_type=%s entities=%s time_range=%s",
        intent.intent_type,
        intent.entities,
        intent.time_range,
    )

    entities = intent.entities[:MAX_ENTITIES]
    calls: list[PlannedToolCall] = []

    if intent.intent_type == "daily_digest":
        calls = _plan_daily_digest(entities, intent.time_range)

    elif intent.intent_type == "weekly_report":
        calls = _plan_weekly_report(entities, intent.time_range)

    elif intent.intent_type == "risk_alert":
        calls = _plan_risk_alert(entities, intent.time_range)

    elif intent.intent_type == "competitor_monitor":
        calls = _plan_competitor_monitor(entities, intent.time_range)

    else:
        logger.warning("Unknown intent_type '%s' — falling back to daily_digest plan", intent.intent_type)
        calls = _plan_daily_digest(entities, intent.time_range)

    logger.info("Planned %d tool calls across %d parallel groups", len(calls), _count_groups(calls))
    return ToolPlan(intent=intent, calls=calls)


# ---------------------------------------------------------------------------
# Intent-specific planners
# ---------------------------------------------------------------------------


def _plan_daily_digest(entities: list[str], time_range: str) -> list[PlannedToolCall]:
    """Plan: one search_company_news call per entity, all in parallel (group 0)."""
    calls: list[PlannedToolCall] = []
    for entity in entities:
        calls.append(
            PlannedToolCall(
                tool_name="search_company_news",
                arguments={
                    "company": entity,
                    "time_range": time_range,
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )
    return calls


def _plan_weekly_report(entities: list[str], time_range: str) -> list[PlannedToolCall]:
    """Plan: search_company_news per entity (group 0) + broader search_news (group 0).

    All calls are in group 0 because they are all independent.
    """
    calls: list[PlannedToolCall] = []
    # Per-entity company news searches — parallel group 0
    for entity in entities:
        calls.append(
            PlannedToolCall(
                tool_name="search_company_news",
                arguments={
                    "company": entity,
                    "time_range": time_range,
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )
    # Broader thematic search — also group 0 (independent)
    if entities:
        broader_query = _build_weekly_query(entities)
        calls.append(
            PlannedToolCall(
                tool_name="search_news",
                arguments={
                    "query": broader_query,
                    "time_range": time_range,
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )
    return calls


def _plan_risk_alert(entities: list[str], time_range: str) -> list[PlannedToolCall]:
    """Plan: search_company_news per entity (group 0) + risk-oriented search_news (group 0)."""
    calls: list[PlannedToolCall] = []
    # Per-entity company news — parallel group 0
    for entity in entities:
        calls.append(
            PlannedToolCall(
                tool_name="search_company_news",
                arguments={
                    "company": entity,
                    "time_range": time_range,
                    "topics": ["risk", "threat", "competitive", "pricing", "expansion"],
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )
    # Risk-oriented broader search — group 0
    if entities:
        risk_query = _build_risk_query(entities)
        calls.append(
            PlannedToolCall(
                tool_name="search_news",
                arguments={
                    "query": risk_query,
                    "time_range": time_range,
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )
    return calls


def _plan_competitor_monitor(entities: list[str], time_range: str) -> list[PlannedToolCall]:
    """Plan: broad search_news for industry/segment (group 0)."""
    calls: list[PlannedToolCall] = []
    if entities:
        industry_query = _build_competitor_query(entities)
        calls.append(
            PlannedToolCall(
                tool_name="search_news",
                arguments={
                    "query": industry_query,
                    "time_range": time_range,
                    "num_results": DEFAULT_NUM_RESULTS * 2,  # wider net for landscape scans
                },
                parallel_group=0,
            )
        )
        # Also search for "new entrant" / "emerging" framing
        emerging_query = f"emerging new entrant startup {' '.join(entities)}"
        calls.append(
            PlannedToolCall(
                tool_name="search_news",
                arguments={
                    "query": emerging_query,
                    "time_range": time_range,
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )
    return calls


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------


def _build_weekly_query(entities: list[str]) -> str:
    """Build a broad weekly-report search query from a list of entities."""
    entity_part = " OR ".join(f'"{e}"' for e in entities[:3])
    return f"({entity_part}) competitive intelligence strategy"


def _build_risk_query(entities: list[str]) -> str:
    """Build a risk-oriented search query."""
    entity_part = " OR ".join(f'"{e}"' for e in entities[:3])
    return f"({entity_part}) risk threat competitive pressure market share"


def _build_competitor_query(entities: list[str]) -> str:
    """Build an industry/segment landscape query."""
    return f"{' '.join(entities)} industry landscape market players competitor"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_groups(calls: list[PlannedToolCall]) -> int:
    """Return the number of unique parallel groups in a list of calls."""
    return len({c.parallel_group for c in calls})
