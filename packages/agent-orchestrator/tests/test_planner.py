"""Tests for the tool call planner."""

from __future__ import annotations

import pytest

from src.agent.planner import plan_tool_calls, _count_groups, _is_named_entity
from src.models.digest import DetectedIntent, PlannedToolCall


def make_intent(
    intent_type: str = "deep_dive",
    entities: list[str] | None = None,
    time_range: str = "7d",
) -> DetectedIntent:
    """Helper to create test DetectedIntent objects."""
    return DetectedIntent(
        intent_type=intent_type,  # type: ignore[arg-type]
        entities=entities or ["AI models"],
        time_range=time_range,
        original_query="test query",
    )


class TestIsNamedEntity:
    """Tests for the _is_named_entity heuristic."""

    def test_short_company_name_is_named_entity(self) -> None:
        assert _is_named_entity("OpenAI") is True

    def test_two_word_company_is_named_entity(self) -> None:
        assert _is_named_entity("Anthropic") is True

    def test_topic_phrase_is_not_named_entity(self) -> None:
        assert _is_named_entity("AI model releases") is False

    def test_topic_with_regulation_is_not_named_entity(self) -> None:
        assert _is_named_entity("sports betting regulation") is False

    def test_long_phrase_is_not_named_entity(self) -> None:
        assert _is_named_entity("large language model developments") is False

    def test_two_word_brand_is_named_entity(self) -> None:
        assert _is_named_entity("Google DeepMind") is True


class TestPlanToolCalls:
    """Tests for plan_tool_calls function."""

    def test_latest_news_named_entity_uses_company_news(self) -> None:
        intent = make_intent(intent_type="latest_news", entities=["OpenAI"], time_range="1d")
        plan = plan_tool_calls(intent)
        assert any(c.tool_name == "search_company_news" for c in plan.calls)

    def test_latest_news_topic_phrase_uses_search_news(self) -> None:
        intent = make_intent(intent_type="latest_news", entities=["AI model releases"], time_range="1d")
        plan = plan_tool_calls(intent)
        assert all(c.tool_name == "search_news" for c in plan.calls)

    def test_latest_news_one_call_per_entity(self) -> None:
        intent = make_intent(
            intent_type="latest_news",
            entities=["AI model releases", "LLM trends"],
            time_range="1d",
        )
        plan = plan_tool_calls(intent)
        assert len(plan.calls) == 2

    def test_latest_news_named_entity_uses_company_param(self) -> None:
        intent = make_intent(intent_type="latest_news", entities=["OpenAI"], time_range="1d")
        plan = plan_tool_calls(intent)
        company_calls = [c for c in plan.calls if c.tool_name == "search_company_news"]
        assert company_calls[0].arguments["company"] == "OpenAI"

    def test_deep_dive_named_entity_mixes_tool_types(self) -> None:
        intent = make_intent(intent_type="deep_dive", entities=["Anthropic"], time_range="7d")
        plan = plan_tool_calls(intent)
        tool_names = {c.tool_name for c in plan.calls}
        assert "search_company_news" in tool_names
        assert "search_news" in tool_names

    def test_deep_dive_topic_uses_only_search_news(self) -> None:
        intent = make_intent(intent_type="deep_dive", entities=["AI model releases"], time_range="7d")
        plan = plan_tool_calls(intent)
        assert all(c.tool_name == "search_news" for c in plan.calls)
        assert len(plan.calls) >= 2

    def test_deep_dive_broader_search_uses_7d_range(self) -> None:
        intent = make_intent(intent_type="deep_dive", time_range="7d")
        plan = plan_tool_calls(intent)
        assert all(c.arguments["time_range"] == "7d" for c in plan.calls)

    def test_risk_scan_query_includes_risk_framing(self) -> None:
        intent = make_intent(intent_type="risk_scan", time_range="7d")
        plan = plan_tool_calls(intent)
        risk_calls = [c for c in plan.calls if "risk" in str(c.arguments.get("query", "")).lower()
                      or "controversy" in str(c.arguments.get("query", "")).lower()]
        assert len(risk_calls) >= 1

    def test_risk_scan_all_search_news(self) -> None:
        intent = make_intent(intent_type="risk_scan", time_range="7d")
        plan = plan_tool_calls(intent)
        assert all(c.tool_name == "search_news" for c in plan.calls)

    def test_trend_watch_uses_search_news(self) -> None:
        intent = make_intent(intent_type="trend_watch", time_range="30d")
        plan = plan_tool_calls(intent)
        assert all(c.tool_name == "search_news" for c in plan.calls)

    def test_trend_watch_wider_result_set(self) -> None:
        intent = make_intent(intent_type="trend_watch", time_range="30d")
        plan = plan_tool_calls(intent)
        assert any(c.arguments.get("num_results", 0) > 10 for c in plan.calls)

    def test_all_calls_in_same_parallel_group_for_latest_news(self) -> None:
        """latest_news calls should all be in group 0 (fully parallel)."""
        intent = make_intent(
            intent_type="latest_news",
            entities=["AI", "LLMs", "OpenAI"],
            time_range="1d",
        )
        plan = plan_tool_calls(intent)
        assert all(c.parallel_group == 0 for c in plan.calls)

    def test_entity_cap_at_max_five(self) -> None:
        """Planner should cap at 5 entities even if intent has more."""
        intent = make_intent(
            intent_type="latest_news",
            entities=["A", "B", "C", "D", "E", "F", "G"],
        )
        plan = plan_tool_calls(intent)
        # For latest_news, one call per entity, capped at 5
        assert len(plan.calls) <= 5

    def test_plan_preserves_intent(self) -> None:
        intent = make_intent()
        plan = plan_tool_calls(intent)
        assert plan.intent == intent

    def test_time_range_propagated_to_calls(self) -> None:
        intent = make_intent(time_range="7d")
        plan = plan_tool_calls(intent)
        for call in plan.calls:
            assert call.arguments.get("time_range") == "7d"

    def test_empty_entities_produces_no_calls_for_trend_watch(self) -> None:
        intent = DetectedIntent(
            intent_type="trend_watch",
            entities=[],
            time_range="30d",
            original_query="what's trending in AI?",
        )
        plan = plan_tool_calls(intent)
        assert len(plan.calls) == 0


class TestCountGroups:
    """Tests for the _count_groups helper."""

    def test_all_same_group(self) -> None:
        calls = [
            PlannedToolCall(tool_name="search_news", arguments={"query": "a", "time_range": "1d"}, parallel_group=0),
            PlannedToolCall(tool_name="search_news", arguments={"query": "b", "time_range": "1d"}, parallel_group=0),
        ]
        assert _count_groups(calls) == 1

    def test_two_groups(self) -> None:
        calls = [
            PlannedToolCall(tool_name="search_news", arguments={"query": "a", "time_range": "1d"}, parallel_group=0),
            PlannedToolCall(tool_name="search_news", arguments={"query": "b", "time_range": "1d"}, parallel_group=1),
        ]
        assert _count_groups(calls) == 2

    def test_empty_list(self) -> None:
        assert _count_groups([]) == 0
