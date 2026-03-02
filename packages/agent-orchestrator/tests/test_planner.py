"""Tests for the tool call planner."""

from __future__ import annotations

import pytest

from src.agent.planner import plan_tool_calls, _count_groups
from src.models.digest import DetectedIntent, PlannedToolCall


def make_intent(
    intent_type: str = "weekly_report",
    entities: list[str] | None = None,
    time_range: str = "7d",
) -> DetectedIntent:
    """Helper to create test DetectedIntent objects."""
    return DetectedIntent(
        intent_type=intent_type,  # type: ignore[arg-type]
        entities=entities or ["Walmart Connect"],
        time_range=time_range,
        original_query="test query",
    )


class TestPlanToolCalls:
    """Tests for plan_tool_calls function."""

    def test_daily_digest_produces_company_news_calls(self) -> None:
        intent = make_intent(intent_type="daily_digest", time_range="1d")
        plan = plan_tool_calls(intent)
        assert all(c.tool_name == "search_company_news" for c in plan.calls)

    def test_daily_digest_one_call_per_entity(self) -> None:
        intent = make_intent(
            intent_type="daily_digest",
            entities=["Walmart Connect", "Amazon DSP"],
            time_range="1d",
        )
        plan = plan_tool_calls(intent)
        assert len(plan.calls) == 2

    def test_weekly_report_includes_both_call_types(self) -> None:
        intent = make_intent(intent_type="weekly_report", time_range="7d")
        plan = plan_tool_calls(intent)
        tool_names = {c.tool_name for c in plan.calls}
        assert "search_company_news" in tool_names
        assert "search_news" in tool_names

    def test_weekly_report_broader_search_uses_7d_range(self) -> None:
        intent = make_intent(intent_type="weekly_report", time_range="7d")
        plan = plan_tool_calls(intent)
        search_news_calls = [c for c in plan.calls if c.tool_name == "search_news"]
        assert all(c.arguments["time_range"] == "7d" for c in search_news_calls)

    def test_risk_alert_includes_risk_topics(self) -> None:
        intent = make_intent(intent_type="risk_alert", time_range="1d")
        plan = plan_tool_calls(intent)
        company_calls = [c for c in plan.calls if c.tool_name == "search_company_news"]
        assert len(company_calls) >= 1
        # Should include topics parameter with risk-related terms
        assert "topics" in company_calls[0].arguments

    def test_risk_alert_includes_risk_oriented_search_news(self) -> None:
        intent = make_intent(intent_type="risk_alert", time_range="1d")
        plan = plan_tool_calls(intent)
        search_news_calls = [c for c in plan.calls if c.tool_name == "search_news"]
        assert len(search_news_calls) >= 1

    def test_competitor_monitor_uses_search_news(self) -> None:
        intent = make_intent(intent_type="competitor_monitor", time_range="30d")
        plan = plan_tool_calls(intent)
        assert all(c.tool_name == "search_news" for c in plan.calls)

    def test_competitor_monitor_wider_result_set(self) -> None:
        intent = make_intent(intent_type="competitor_monitor", time_range="30d")
        plan = plan_tool_calls(intent)
        # At least one call should request more results than default
        assert any(c.arguments.get("num_results", 0) > 10 for c in plan.calls)

    def test_all_calls_in_same_parallel_group_for_daily(self) -> None:
        """Daily digest calls should all be in group 0 (fully parallel)."""
        intent = make_intent(
            intent_type="daily_digest",
            entities=["A", "B", "C"],
            time_range="1d",
        )
        plan = plan_tool_calls(intent)
        assert all(c.parallel_group == 0 for c in plan.calls)

    def test_entity_cap_at_max_five(self) -> None:
        """Planner should cap at 5 entities even if intent has more."""
        intent = make_intent(
            intent_type="daily_digest",
            entities=["A", "B", "C", "D", "E", "F", "G"],
        )
        plan = plan_tool_calls(intent)
        # For daily_digest, one call per entity, capped at 5
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

    def test_empty_entities_produces_no_company_calls(self) -> None:
        intent = DetectedIntent(
            intent_type="competitor_monitor",
            entities=[],
            time_range="30d",
            original_query="who is emerging in retail media",
        )
        plan = plan_tool_calls(intent)
        company_calls = [c for c in plan.calls if c.tool_name == "search_company_news"]
        assert len(company_calls) == 0


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
