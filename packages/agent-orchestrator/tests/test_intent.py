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

    def test_weekly_report_detection(self) -> None:
        prompt = "Anything important about Walmart Connect this week?"
        intent = detect_intent_heuristic(prompt)
        assert intent.intent_type == "weekly_report"
        assert intent.time_range == "7d"
        assert intent.original_query == prompt

    def test_daily_digest_detection_today(self) -> None:
        intent = detect_intent_heuristic("What happened today with Amazon advertising?")
        assert intent.intent_type == "daily_digest"
        assert intent.time_range == "1d"

    def test_daily_digest_detection_overnight(self) -> None:
        intent = detect_intent_heuristic("Any overnight news about Target retail media?")
        assert intent.intent_type == "daily_digest"
        assert intent.time_range == "1d"

    def test_daily_digest_detection_this_morning(self) -> None:
        intent = detect_intent_heuristic("this morning's updates on Google ads")
        assert intent.intent_type == "daily_digest"

    def test_risk_alert_detection(self) -> None:
        intent = detect_intent_heuristic(
            "Are there any risks from Walmart Connect expanding self-serve?"
        )
        assert intent.intent_type == "risk_alert"
        assert intent.time_range == "1d"

    def test_risk_alert_threat_keyword(self) -> None:
        intent = detect_intent_heuristic("threat from new Amazon DSP launch")
        assert intent.intent_type == "risk_alert"

    def test_risk_alert_concern_keyword(self) -> None:
        intent = detect_intent_heuristic("concern about competitor pricing changes")
        assert intent.intent_type == "risk_alert"

    def test_competitor_monitor_detection(self) -> None:
        intent = detect_intent_heuristic(
            "Who else is emerging in the retail media landscape?"
        )
        assert intent.intent_type == "competitor_monitor"
        assert intent.time_range == "30d"

    def test_default_fallback_to_weekly_report(self) -> None:
        intent = detect_intent_heuristic("competitive intelligence")
        assert intent.intent_type == "weekly_report"
        assert intent.time_range == "7d"

    def test_entity_extraction_multi_word_company(self) -> None:
        intent = detect_intent_heuristic("Walmart Connect news this week")
        assert "Walmart Connect" in intent.entities

    def test_entity_extraction_single_entity(self) -> None:
        intent = detect_intent_heuristic("Amazon weekly news")
        assert len(intent.entities) >= 1

    def test_empty_entities_gets_default(self) -> None:
        intent = detect_intent_heuristic("anything happening this week?")
        assert len(intent.entities) >= 1
        assert intent.entities[0] == "general competitive intelligence"

    def test_entities_are_unique(self) -> None:
        intent = detect_intent_heuristic("Walmart Connect Walmart Connect this week")
        # Should not have duplicate entities
        assert len(intent.entities) == len(set(intent.entities))

    def test_risk_takes_priority_over_weekly(self) -> None:
        # "this week" + "risk" — risk should take precedence
        intent = detect_intent_heuristic("risk this week from Walmart Connect")
        assert intent.intent_type == "risk_alert"

    def test_weekly_with_7_days(self) -> None:
        intent = detect_intent_heuristic("past 7 days news on Amazon DSP")
        assert intent.intent_type == "weekly_report"
        assert intent.time_range == "7d"


class TestFallbackIntent:
    """Tests for the fallback intent constructor."""

    def test_fallback_returns_weekly_report(self) -> None:
        intent = _fallback_intent("some garbled prompt")
        assert intent.intent_type == "weekly_report"
        assert intent.time_range == "7d"
        assert "general competitive intelligence" in intent.entities

    def test_fallback_preserves_original_query(self) -> None:
        prompt = "some garbled prompt that failed to parse"
        intent = _fallback_intent(prompt)
        assert intent.original_query == prompt


class TestDetectedIntentModel:
    """Tests for the DetectedIntent Pydantic model."""

    def test_valid_daily_digest(self) -> None:
        intent = DetectedIntent(
            intent_type="daily_digest",
            entities=["Walmart Connect"],
            time_range="1d",
            original_query="What's new today?",
        )
        assert intent.intent_type == "daily_digest"

    def test_valid_weekly_report(self) -> None:
        intent = DetectedIntent(
            intent_type="weekly_report",
            entities=["Amazon", "Google"],
            time_range="7d",
            original_query="Weekly report",
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
        for intent_type in ["daily_digest", "weekly_report", "risk_alert", "competitor_monitor"]:
            intent = DetectedIntent(
                intent_type=intent_type,  # type: ignore[arg-type]
                entities=["Test"],
                time_range="1d",
                original_query="test",
            )
            assert intent.intent_type == intent_type
