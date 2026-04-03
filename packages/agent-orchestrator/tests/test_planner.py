"""Tests for the tool call planner."""

from __future__ import annotations

import pytest

from src.agent.planner import plan_tool_calls, _count_groups, _is_named_entity, _is_tech_topic, MAX_CALLS
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


class TestIsTechTopic:
    """Tests for the _is_tech_topic heuristic."""

    def test_ai_agents_is_tech(self) -> None:
        assert _is_tech_topic("AI agents") is True

    def test_llm_training_is_tech(self) -> None:
        assert _is_tech_topic("LLM training") is True

    def test_open_source_is_tech(self) -> None:
        assert _is_tech_topic("open source software") is True

    def test_sports_betting_is_not_tech(self) -> None:
        assert _is_tech_topic("sports betting") is False

    def test_company_name_is_not_tech(self) -> None:
        # Named entities like "OpenAI" are companies, not classified as tech topics
        assert _is_tech_topic("OpenAI") is False

    def test_crypto_is_tech(self) -> None:
        assert _is_tech_topic("crypto blockchain") is True


class TestPlanToolCalls:
    """Tests for plan_tool_calls function."""

    def test_latest_news_named_entity_uses_company_news(self) -> None:
        intent = make_intent(intent_type="latest_news", entities=["OpenAI"], time_range="1d")
        plan = plan_tool_calls(intent)
        assert any(c.tool_name == "search_company_news" for c in plan.calls)

    def test_latest_news_topic_phrase_uses_search_news(self) -> None:
        intent = make_intent(intent_type="latest_news", entities=["AI model releases"], time_range="1d")
        plan = plan_tool_calls(intent)
        assert any(c.tool_name == "search_news" for c in plan.calls)

    def test_latest_news_includes_reddit(self) -> None:
        intent = make_intent(intent_type="latest_news", entities=["OpenAI"], time_range="1d")
        plan = plan_tool_calls(intent)
        assert any(c.tool_name == "search_reddit" for c in plan.calls)

    def test_latest_news_two_calls_per_entity(self) -> None:
        """Each entity produces a primary call + reddit call."""
        intent = make_intent(
            intent_type="latest_news",
            entities=["AI model releases", "LLM trends"],
            time_range="1d",
        )
        plan = plan_tool_calls(intent)
        assert len(plan.calls) == 4  # 2 entities × 2 calls each

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
        assert "search_web" in tool_names
        assert "search_reddit" in tool_names

    def test_deep_dive_topic_uses_search_news(self) -> None:
        intent = make_intent(intent_type="deep_dive", entities=["AI model releases"], time_range="7d")
        plan = plan_tool_calls(intent)
        assert any(c.tool_name == "search_news" for c in plan.calls)

    def test_deep_dive_topic_uses_multiple_tools(self) -> None:
        intent = make_intent(intent_type="deep_dive", entities=["AI model releases"], time_range="7d")
        plan = plan_tool_calls(intent)
        assert len(plan.calls) >= 3

    def test_deep_dive_broader_search_uses_time_range(self) -> None:
        """Calls that accept time_range should propagate it."""
        intent = make_intent(intent_type="deep_dive", time_range="7d")
        plan = plan_tool_calls(intent)
        time_range_calls = [c for c in plan.calls if "time_range" in c.arguments]
        assert all(c.arguments["time_range"] == "7d" for c in time_range_calls)

    def test_deep_dive_tech_topic_includes_scholar_and_github(self) -> None:
        intent = make_intent(intent_type="deep_dive", entities=["AI agents"], time_range="7d")
        plan = plan_tool_calls(intent)
        tool_names = {c.tool_name for c in plan.calls}
        assert "search_scholar" in tool_names
        assert "search_github" in tool_names

    def test_deep_dive_non_tech_topic_includes_quora(self) -> None:
        intent = make_intent(intent_type="deep_dive", entities=["sports betting regulation"], time_range="7d")
        plan = plan_tool_calls(intent)
        tool_names = {c.tool_name for c in plan.calls}
        assert "search_quora" in tool_names

    def test_deep_dive_call_count_does_not_exceed_max(self) -> None:
        intent = make_intent(
            intent_type="deep_dive",
            entities=["A", "B", "C", "D", "E"],
            time_range="7d",
        )
        plan = plan_tool_calls(intent)
        assert len(plan.calls) <= MAX_CALLS

    def test_risk_scan_includes_news_call(self) -> None:
        intent = make_intent(intent_type="risk_scan", time_range="7d")
        plan = plan_tool_calls(intent)
        assert any(c.tool_name in ("search_news", "search_company_news") for c in plan.calls)

    def test_risk_scan_includes_web(self) -> None:
        intent = make_intent(intent_type="risk_scan", time_range="7d")
        plan = plan_tool_calls(intent)
        assert any(c.tool_name == "search_web" for c in plan.calls)

    def test_risk_scan_includes_reddit(self) -> None:
        intent = make_intent(intent_type="risk_scan", time_range="7d")
        plan = plan_tool_calls(intent)
        assert any(c.tool_name == "search_reddit" for c in plan.calls)

    def test_risk_scan_query_includes_risk_framing(self) -> None:
        intent = make_intent(intent_type="risk_scan", time_range="7d")
        plan = plan_tool_calls(intent)
        risk_calls = [c for c in plan.calls if "risk" in str(c.arguments.get("query", "")).lower()
                      or "controversy" in str(c.arguments.get("query", "")).lower()
                      or "topics" in c.arguments]
        assert len(risk_calls) >= 1

    def test_trend_watch_uses_search_news(self) -> None:
        intent = make_intent(intent_type="trend_watch", time_range="30d")
        plan = plan_tool_calls(intent)
        assert any(c.tool_name == "search_news" for c in plan.calls)

    def test_trend_watch_includes_videos(self) -> None:
        intent = make_intent(intent_type="trend_watch", time_range="30d")
        plan = plan_tool_calls(intent)
        assert any(c.tool_name == "find_videos" for c in plan.calls)

    def test_trend_watch_includes_reddit(self) -> None:
        intent = make_intent(intent_type="trend_watch", time_range="30d")
        plan = plan_tool_calls(intent)
        assert any(c.tool_name == "search_reddit" for c in plan.calls)

    def test_trend_watch_tech_topic_includes_github(self) -> None:
        intent = make_intent(intent_type="trend_watch", entities=["AI agents"], time_range="30d")
        plan = plan_tool_calls(intent)
        assert any(c.tool_name == "search_github" for c in plan.calls)

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
        # 5 entities × 2 calls each (primary + reddit) = 10 max
        assert len(plan.calls) <= 10

    def test_plan_preserves_intent(self) -> None:
        intent = make_intent()
        plan = plan_tool_calls(intent)
        assert plan.intent == intent

    def test_time_range_propagated_to_news_calls(self) -> None:
        """time_range should be on all calls that accept it (news/company_news)."""
        intent = make_intent(time_range="7d")
        plan = plan_tool_calls(intent)
        time_range_calls = [c for c in plan.calls if "time_range" in c.arguments]
        assert len(time_range_calls) >= 1
        for call in time_range_calls:
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
