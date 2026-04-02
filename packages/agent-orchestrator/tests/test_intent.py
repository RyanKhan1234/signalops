"""Tests for intent detection (heuristic and LLM-based paths)."""

from __future__ import annotations

import pytest

from src.agent.intent import detect_intent_heuristic, _fallback_intent
from src.models.digest import DetectedIntent


# ---------------------------------------------------------------------------
# Heuristic intent detection tests (no LLM required)
# ---------------------------------------------------------------------------


class TestHeuristicIntentDetection:
    """Tests for the heuristic-based intent detector."""

    def test_deep_dive_detection_this_week(self) -> None:
        prompt = "What's been happening with AI model releases this week?"
        intent = detect_intent_heuristic(prompt)
        assert intent.intent_type == "deep_dive"
        assert intent.time_range == "7d"
        assert intent.original_query == prompt

    def test_latest_news_detection_today(self) -> None:
        intent = detect_intent_heuristic("What's new today in AI?")
        assert intent.intent_type == "latest_news"
        assert intent.time_range == "1d"

    def test_latest_news_detection_just_dropped(self) -> None:
        intent = detect_intent_heuristic("Any models just dropped from Anthropic?")
        assert intent.intent_type == "latest_news"
        assert intent.time_range == "1d"

    def test_latest_news_detection_this_morning(self) -> None:
        intent = detect_intent_heuristic("this morning's updates on LLMs")
        assert intent.intent_type == "latest_news"

    def test_risk_scan_detection(self) -> None:
        intent = detect_intent_heuristic(
            "Are there any risks with AI regulation right now?"
        )
        assert intent.intent_type == "risk_scan"
        assert intent.time_range == "7d"

    def test_risk_scan_controversy_keyword(self) -> None:
        intent = detect_intent_heuristic("controversy around OpenAI's latest move")
        assert intent.intent_type == "risk_scan"

    def test_risk_scan_concern_keyword(self) -> None:
        intent = detect_intent_heuristic("concerns about sports betting addiction")
        assert intent.intent_type == "risk_scan"

    def test_trend_watch_detection(self) -> None:
        intent = detect_intent_heuristic(
            "What's emerging in the AI agent landscape?"
        )
        assert intent.intent_type == "trend_watch"
        assert intent.time_range == "30d"

    def test_default_fallback_to_deep_dive(self) -> None:
        intent = detect_intent_heuristic("tell me about AI")
        assert intent.intent_type == "deep_dive"
        assert intent.time_range == "7d"

    def test_entity_extraction_multi_word(self) -> None:
        intent = detect_intent_heuristic("Large Language Models news this week")
        assert "Large Language Models" in intent.entities

    def test_entity_extraction_single_entity(self) -> None:
        intent = detect_intent_heuristic("OpenAI weekly news")
        assert len(intent.entities) >= 1

    def test_empty_entities_gets_default(self) -> None:
        intent = detect_intent_heuristic("anything happening this week?")
        assert len(intent.entities) >= 1
        assert intent.entities[0] == "general research"

    def test_entities_are_unique(self) -> None:
        intent = detect_intent_heuristic("Large Language Models Large Language Models this week")
        assert len(intent.entities) == len(set(intent.entities))

    def test_risk_takes_priority_over_deep_dive(self) -> None:
        # "this week" + "risk" — risk_scan should take precedence
        intent = detect_intent_heuristic("risk this week from AI regulation")
        assert intent.intent_type == "risk_scan"

    def test_deep_dive_with_7_days(self) -> None:
        intent = detect_intent_heuristic("past 7 days news on sports betting")
        assert intent.intent_type == "deep_dive"
        assert intent.time_range == "7d"


class TestFallbackIntent:
    """Tests for the fallback intent constructor."""

    def test_fallback_returns_deep_dive(self) -> None:
        intent = _fallback_intent("some garbled prompt")
        assert intent.intent_type == "deep_dive"
        assert intent.time_range == "7d"
        assert "general research" in intent.entities

    def test_fallback_preserves_original_query(self) -> None:
        prompt = "some garbled prompt that failed to parse"
        intent = _fallback_intent(prompt)
        assert intent.original_query == prompt


class TestDetectedIntentModel:
    """Tests for the DetectedIntent Pydantic model."""

    def test_valid_latest_news(self) -> None:
        intent = DetectedIntent(
            intent_type="latest_news",
            entities=["AI models"],
            time_range="1d",
            original_query="What's new today?",
        )
        assert intent.intent_type == "latest_news"

    def test_valid_deep_dive(self) -> None:
        intent = DetectedIntent(
            intent_type="deep_dive",
            entities=["sports betting", "regulation"],
            time_range="7d",
            original_query="Deep dive on sports betting regulation",
        )
        assert len(intent.entities) == 2

    def test_invalid_intent_type_raises(self) -> None:
        with pytest.raises(Exception):
            DetectedIntent(
                intent_type="invalid_type",  # type: ignore[arg-type]
                entities=["Test"],
                time_range="1d",
                original_query="test",
            )

    def test_all_four_intent_types_valid(self) -> None:
        for intent_type in ["latest_news", "deep_dive", "risk_scan", "trend_watch"]:
            intent = DetectedIntent(
                intent_type=intent_type,  # type: ignore[arg-type]
                entities=["Test"],
                time_range="1d",
                original_query="test",
            )
            assert intent.intent_type == intent_type
