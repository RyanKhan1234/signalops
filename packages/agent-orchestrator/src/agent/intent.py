"""Intent detection and entity extraction for the Agent Orchestrator.

Classifies incoming natural-language prompts into one of four research modes
and extracts structured entities (topics, technologies, companies, domains).
"""

from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings
from src.models.digest import DetectedIntent, DigestType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_json_from_text(text: str) -> str:
    """Strip markdown code fences from an LLM response to extract raw JSON.

    Claude sometimes wraps JSON in ```json...``` or ```...``` fences even when
    instructed not to. This strips those fences before attempting json.loads().
    """
    text = re.sub(r"```(?:json)?\s*\n?", "", text)
    text = text.replace("```", "")
    return text.strip()


# ---------------------------------------------------------------------------
# Prompt templates — kept in version-controlled code, not external storage
# ---------------------------------------------------------------------------

INTENT_SYSTEM_PROMPT = """You are an intent classifier for a personal news research tool.

Your job is to analyze a user's natural-language prompt and return a structured JSON object
describing the research intent and topics. You must output ONLY valid JSON — no preamble, no markdown.

The JSON must conform to this schema:
{
  "intent_type": "<latest_news|deep_dive|risk_scan|trend_watch>",
  "entities": ["<topic, technology, company, or domain>", ...],
  "time_range": "<1d|7d|30d>",
  "original_query": "<the original user prompt verbatim>"
}

Intent classification rules:
- latest_news: user wants recent headlines or quick updates — keywords like "today", "latest", "just dropped", "what's new", "this morning", "overnight", "any news"
- deep_dive: user wants thorough, multi-angle research — keywords like "tell me everything", "deep dive", "breakdown", "this week", "past 7 days", "weekly", "comprehensive"
- risk_scan: user wants to surface concerns, controversies, or downsides — keywords like "risk", "concern", "problem", "controversy", "backlash", "threat", "danger", "warn", "downside"
- trend_watch: user wants to understand what's emerging or where things are heading — keywords like "trend", "emerging", "what's coming", "future", "growing", "rising", "new players", "landscape"

Default time_range mapping:
- latest_news → "1d"
- deep_dive → "7d"
- risk_scan → "7d"
- trend_watch → "30d"

Entity extraction:
- Extract all topics, technologies, companies, products, industries, or domains mentioned
- If no entity is explicitly named, infer from context (e.g., "AI safety" or "sports betting" are valid entities)
- Always include at least one entity

Do not hallucinate. Output only what is present in the prompt."""


async def detect_intent(prompt: str) -> DetectedIntent:
    """Classify a user prompt into a structured DetectedIntent.

    Uses the Anthropic API with structured JSON output to reliably extract
    intent type, entities, and time range from natural language.

    Args:
        prompt: The raw user-submitted natural language prompt.

    Returns:
        A DetectedIntent instance with classified fields.

    Raises:
        ValueError: If the LLM returns malformed JSON or missing required fields.
    """
    logger.info("Detecting intent for prompt: %s", prompt[:100])

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
        max_tokens=512,
    )

    response = await llm.ainvoke([
        SystemMessage(content=INTENT_SYSTEM_PROMPT),
        HumanMessage(content=f"Classify this prompt:\n\n{prompt}"),
    ])

    raw_text = response.content.strip() if isinstance(response.content, str) else str(response.content)
    logger.debug("Raw intent response: %s", raw_text)

    try:
        parsed = json.loads(_extract_json_from_text(raw_text))
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse intent JSON: %s — raw: %s", exc, raw_text)
        # Graceful fallback: treat as deep_dive with generic entity
        return _fallback_intent(prompt)

    # Validate required fields are present
    required_fields = {"intent_type", "entities", "time_range", "original_query"}
    missing = required_fields - set(parsed.keys())
    if missing:
        logger.warning("Intent response missing fields %s — using fallback", missing)
        return _fallback_intent(prompt)

    # Ensure intent_type is valid
    valid_types: set[DigestType] = {
        "latest_news",
        "deep_dive",
        "risk_scan",
        "trend_watch",
    }
    if parsed["intent_type"] not in valid_types:
        logger.warning("Unknown intent_type '%s' — defaulting to deep_dive", parsed["intent_type"])
        parsed["intent_type"] = "deep_dive"

    # Ensure entities is a non-empty list
    if not parsed.get("entities"):
        parsed["entities"] = ["general research"]

    return DetectedIntent(
        intent_type=parsed["intent_type"],
        entities=parsed["entities"],
        time_range=parsed["time_range"],
        original_query=prompt,
    )


def _fallback_intent(prompt: str) -> DetectedIntent:
    """Return a safe fallback intent when LLM response cannot be parsed."""
    return DetectedIntent(
        intent_type="deep_dive",
        entities=["general research"],
        time_range="7d",
        original_query=prompt,
    )


def detect_intent_heuristic(prompt: str) -> DetectedIntent:
    """Heuristic-based intent detection (no LLM required).

    Used as a fast path or fallback when the LLM is unavailable.
    Less accurate than the LLM-based approach but always available.

    Args:
        prompt: The raw user-submitted natural language prompt.

    Returns:
        A DetectedIntent instance derived from keyword matching.
    """
    prompt_lower = prompt.lower()

    # Determine intent type — checked in priority order
    if any(kw in prompt_lower for kw in ["risk", "threat", "concern", "watch out", "danger", "warn", "controversy", "backlash", "downside"]):
        intent_type: DigestType = "risk_scan"
        time_range = "7d"
    elif any(kw in prompt_lower for kw in ["trend", "emerging", "who else", "landscape", "rising", "future", "what's coming", "new players"]):
        intent_type = "trend_watch"
        time_range = "30d"
    elif any(kw in prompt_lower for kw in ["tell me everything", "deep dive", "breakdown", "this week", "weekly", "past 7 days", "7 days", "comprehensive"]):
        intent_type = "deep_dive"
        time_range = "7d"
    elif any(kw in prompt_lower for kw in ["today", "this morning", "overnight", "latest", "just dropped", "any news", "what's new"]):
        intent_type = "latest_news"
        time_range = "1d"
    else:
        intent_type = "deep_dive"
        time_range = "7d"

    # Simple entity extraction: capitalized words and quoted strings
    entities: list[str] = []
    # Extract quoted phrases
    quoted = re.findall(r'"([^"]+)"', prompt)
    entities.extend(quoted)
    # Extract capitalized multi-word phrases (e.g., "Large Language Models")
    cap_phrases = re.findall(r"(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", prompt)
    entities.extend(cap_phrases)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_entities: list[str] = []
    for e in entities:
        if e not in seen:
            seen.add(e)
            unique_entities.append(e)

    if not unique_entities:
        unique_entities = ["general research"]

    return DetectedIntent(
        intent_type=intent_type,
        entities=unique_entities,
        time_range=time_range,
        original_query=prompt,
    )
