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
# Maximum total tool calls per plan (prevents runaway API usage on wide queries)
MAX_CALLS = 15

# Words that indicate an entity is a topic/phrase rather than a named entity.
# Entities containing these words get search_news; others get search_company_news.
_TOPIC_WORDS = frozenset({
    "regulation", "release", "releases", "market", "trend", "trends",
    "technology", "news", "latest", "update", "updates", "industry",
    "development", "developments", "policy", "law", "betting", "crypto",
    "research", "science", "health", "climate", "election", "elections",
    "model", "models", "agent", "agents", "system", "systems",
})

# Words that indicate an entity is a tech/AI/software topic.
_TECH_WORDS = frozenset({
    "ai", "ml", "llm", "llms", "gpt", "neural", "crypto", "blockchain",
    "software", "algorithm", "code", "coding", "programming",
    "python", "javascript", "typescript", "github", "open", "source",
    "api", "library", "framework", "dataset", "training", "inference",
    "gpu", "quantum", "computing", "saas", "cloud",
})


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

    if intent.intent_type == "latest_news":
        calls = _plan_latest_news(entities, intent.time_range)

    elif intent.intent_type == "deep_dive":
        calls = _plan_deep_dive(entities, intent.time_range)

    elif intent.intent_type == "risk_scan":
        calls = _plan_risk_scan(entities, intent.time_range)

    elif intent.intent_type == "trend_watch":
        calls = _plan_trend_watch(entities, intent.time_range)

    else:
        logger.warning("Unknown intent_type '%s' — falling back to latest_news plan", intent.intent_type)
        calls = _plan_latest_news(entities, intent.time_range)

    logger.info("Planned %d tool calls across %d parallel groups", len(calls), _count_groups(calls))
    return ToolPlan(intent=intent, calls=calls)


# ---------------------------------------------------------------------------
# Named entity detection
# ---------------------------------------------------------------------------


def _is_named_entity(entity: str) -> bool:
    """Return True if the entity looks like a named entity (company, org, person).

    Heuristic: short (≤ 3 words) and contains no common topic/subject words.
    Named entities get search_company_news; topic phrases get search_news.

    Examples:
      "OpenAI"           → True  (named entity)
      "Anthropic"        → True
      "sports betting regulation" → False (topic phrase)
      "AI model releases"        → False
    """
    words = entity.lower().split()
    if len(words) > 3:
        return False
    return not any(w in _TOPIC_WORDS for w in words)


def _is_tech_topic(entity: str) -> bool:
    """Return True if the entity sounds like a tech/AI/software topic.

    Examples:
      "AI agents"  → True
      "LLM training" → True
      "sports betting" → False
    """
    words = entity.lower().split()
    return any(w in _TECH_WORDS for w in words)


# ---------------------------------------------------------------------------
# Intent-specific planners
# ---------------------------------------------------------------------------


def _plan_latest_news(entities: list[str], time_range: str) -> list[PlannedToolCall]:
    """Plan: one primary call per entity plus one supplemental reddit call per entity.

    Named entities get search_company_news; topic phrases get search_news.
    All calls run in parallel (group 0).
    """
    calls: list[PlannedToolCall] = []
    for entity in entities:
        if _is_named_entity(entity):
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
        else:
            calls.append(
                PlannedToolCall(
                    tool_name="search_news",
                    arguments={
                        "query": f"{entity} latest news",
                        "time_range": time_range,
                        "num_results": DEFAULT_NUM_RESULTS,
                    },
                    parallel_group=0,
                )
            )
        # Supplemental community signal via Reddit
        calls.append(
            PlannedToolCall(
                tool_name="search_reddit",
                arguments={
                    "query": f"{entity} discussion",
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )
    return calls


def _plan_deep_dive(entities: list[str], time_range: str) -> list[PlannedToolCall]:
    """Plan: per-entity calls (search_company_news or search_news) + supplemental
    web/reddit/scholar/github/quora calls + broader context search.

    All calls run in parallel (group 0). Total capped at MAX_CALLS.
    """
    calls: list[PlannedToolCall] = []
    for entity in entities:
        # Primary source: company news or topic news
        if _is_named_entity(entity):
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
        else:
            calls.append(
                PlannedToolCall(
                    tool_name="search_news",
                    arguments={
                        "query": entity,
                        "time_range": time_range,
                        "num_results": DEFAULT_NUM_RESULTS,
                    },
                    parallel_group=0,
                )
            )

        # Web analysis for all entities
        calls.append(
            PlannedToolCall(
                tool_name="search_web",
                arguments={
                    "query": f"{entity} analysis",
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )

        # Reddit community signal for all entities
        calls.append(
            PlannedToolCall(
                tool_name="search_reddit",
                arguments={
                    "query": entity,
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )

        # Tech topics get academic/code perspective; non-tech get Q&A perspective
        if _is_tech_topic(entity):
            calls.append(
                PlannedToolCall(
                    tool_name="search_scholar",
                    arguments={
                        "query": entity,
                        "num_results": DEFAULT_NUM_RESULTS,
                    },
                    parallel_group=0,
                )
            )
            calls.append(
                PlannedToolCall(
                    tool_name="search_github",
                    arguments={
                        "query": entity,
                        "num_results": DEFAULT_NUM_RESULTS,
                    },
                    parallel_group=0,
                )
            )
        else:
            calls.append(
                PlannedToolCall(
                    tool_name="search_quora",
                    arguments={
                        "query": entity,
                        "num_results": DEFAULT_NUM_RESULTS,
                    },
                    parallel_group=0,
                )
            )

    # Broader context search across all entities combined
    if entities:
        calls.append(
            PlannedToolCall(
                tool_name="search_news",
                arguments={
                    "query": _build_deep_dive_query(entities),
                    "time_range": time_range,
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )

    # Cap total calls to avoid runaway API usage
    return calls[:MAX_CALLS]


def _plan_risk_scan(entities: list[str], time_range: str) -> list[PlannedToolCall]:
    """Plan: per-entity risk-framed calls + web/reddit risk calls + broader risk search.

    All calls run in parallel (group 0).
    """
    calls: list[PlannedToolCall] = []
    for entity in entities:
        if _is_named_entity(entity):
            calls.append(
                PlannedToolCall(
                    tool_name="search_company_news",
                    arguments={
                        "company": entity,
                        "time_range": time_range,
                        "topics": ["risk", "controversy", "problem", "concern", "backlash"],
                        "num_results": DEFAULT_NUM_RESULTS,
                    },
                    parallel_group=0,
                )
            )
        else:
            calls.append(
                PlannedToolCall(
                    tool_name="search_news",
                    arguments={
                        "query": f"{entity} risk concern problem controversy",
                        "time_range": time_range,
                        "num_results": DEFAULT_NUM_RESULTS,
                    },
                    parallel_group=0,
                )
            )

        # Web search for risk signals
        calls.append(
            PlannedToolCall(
                tool_name="search_web",
                arguments={
                    "query": f"{entity} risk warning controversy",
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )

        # Reddit community concerns
        calls.append(
            PlannedToolCall(
                tool_name="search_reddit",
                arguments={
                    "query": f"{entity} problems concerns",
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )

    # Broader risk-oriented search across all entities
    if entities:
        calls.append(
            PlannedToolCall(
                tool_name="search_news",
                arguments={
                    "query": _build_risk_query(entities),
                    "time_range": time_range,
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )
    return calls


def _plan_trend_watch(entities: list[str], time_range: str) -> list[PlannedToolCall]:
    """Plan: broad trend-oriented search_news calls plus video, reddit, and (for tech) github signals.

    All calls run in parallel (group 0).
    """
    calls: list[PlannedToolCall] = []
    if entities:
        # Trend landscape search
        calls.append(
            PlannedToolCall(
                tool_name="search_news",
                arguments={
                    "query": _build_trend_query(entities),
                    "time_range": time_range,
                    "num_results": DEFAULT_NUM_RESULTS * 2,  # wider net for trend scanning
                },
                parallel_group=0,
            )
        )
        # Emerging/new angle search
        calls.append(
            PlannedToolCall(
                tool_name="search_news",
                arguments={
                    "query": f"emerging new development {' '.join(entities)}",
                    "time_range": time_range,
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )

        # Video content for trend discovery
        calls.append(
            PlannedToolCall(
                tool_name="search_videos",
                arguments={
                    "query": f"{' '.join(entities)} latest developments 2025",
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )

        # Reddit community trend signal
        calls.append(
            PlannedToolCall(
                tool_name="search_reddit",
                arguments={
                    "query": _build_trend_query(entities),
                    "num_results": DEFAULT_NUM_RESULTS,
                },
                parallel_group=0,
            )
        )

        # GitHub activity for tech topics
        if any(_is_tech_topic(e) for e in entities):
            calls.append(
                PlannedToolCall(
                    tool_name="search_github",
                    arguments={
                        "query": " ".join(entities),
                        "num_results": DEFAULT_NUM_RESULTS,
                    },
                    parallel_group=0,
                )
            )

    return calls


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------


def _build_deep_dive_query(entities: list[str]) -> str:
    """Build a broad multi-angle query for a deep dive."""
    entity_part = " OR ".join(f'"{e}"' for e in entities[:3])
    return f"({entity_part}) analysis update development"


def _build_risk_query(entities: list[str]) -> str:
    """Build a risk/controversy-oriented search query."""
    entity_part = " OR ".join(f'"{e}"' for e in entities[:3])
    return f"({entity_part}) risk controversy problem backlash warning"


def _build_trend_query(entities: list[str]) -> str:
    """Build a trend landscape search query."""
    return f"{' '.join(entities)} trend emerging landscape 2025"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_groups(calls: list[PlannedToolCall]) -> int:
    """Return the number of unique parallel groups in a list of calls."""
    return len({c.parallel_group for c in calls})
