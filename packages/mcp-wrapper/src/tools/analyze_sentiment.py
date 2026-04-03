"""``analyze_sentiment`` MCP tool — computational NLP sentiment analysis.

Unlike the search tools, this performs actual computation on text.
Uses a curated word-list approach (VADER-inspired) to score sentiment
without external API calls or heavy ML dependencies.

Returns a single "article" with structured sentiment data in the snippet.
"""

from __future__ import annotations

import logging
import math
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from src.middleware.cache import ResponseCache
from src.middleware.rate_limiter import RateLimiter
from src.serpapi.models import NormalizedArticle, NormalizedResponse

logger = logging.getLogger(__name__)

# --- Sentiment lexicons (VADER-inspired, trimmed for size) ---

_POSITIVE = {
    "good", "great", "excellent", "amazing", "wonderful", "fantastic",
    "outstanding", "brilliant", "impressive", "innovative", "breakthrough",
    "revolutionary", "promising", "optimistic", "successful", "growth",
    "opportunity", "advantage", "benefit", "improve", "improved", "gain",
    "gained", "surge", "surged", "soar", "soared", "bullish", "upgrade",
    "upgraded", "outperform", "beat", "exceeded", "record", "milestone",
    "momentum", "acceleration", "leading", "dominant", "strong", "robust",
    "thriving", "booming", "profitable", "winning", "triumph", "exciting",
    "remarkable", "exceptional", "superior", "celebrated", "praised",
    "endorsed", "backed", "supported", "launched", "expanded", "acquired",
    "partnership", "collaboration", "adoption", "transformative", "disruptive",
    "efficient", "progress", "advance", "advanced", "achievement", "achieve",
}

_NEGATIVE = {
    "bad", "terrible", "awful", "poor", "disappointing", "failed", "failure",
    "crisis", "crash", "crashed", "decline", "declined", "drop", "dropped",
    "plunge", "plunged", "bearish", "downgrade", "downgraded", "underperform",
    "missed", "miss", "loss", "losses", "deficit", "debt", "bankrupt",
    "bankruptcy", "layoff", "layoffs", "fired", "shutdown", "closed",
    "controversy", "controversial", "scandal", "lawsuit", "sued", "fine",
    "fined", "penalty", "violation", "breach", "hack", "hacked", "leak",
    "leaked", "exploit", "vulnerability", "risk", "risky", "threat",
    "warning", "danger", "dangerous", "concern", "worried", "fear",
    "anxiety", "uncertain", "uncertainty", "volatile", "volatility",
    "collapse", "collapsed", "recession", "downturn", "slump", "stagnant",
    "struggling", "troubled", "criticized", "backlash", "outrage", "angry",
    "frustrated", "problem", "problematic", "flawed", "broken", "bug",
    "error", "mistake", "catastrophic", "devastating", "alarming",
}

_INTENSIFIERS = {
    "very", "extremely", "incredibly", "highly", "exceptionally",
    "remarkably", "significantly", "substantially", "tremendously",
    "dramatically", "massively", "critically", "severely",
}

_NEGATORS = {
    "not", "no", "never", "neither", "nor", "hardly", "barely",
    "scarcely", "doesn't", "don't", "didn't", "won't", "wouldn't",
    "couldn't", "shouldn't", "isn't", "aren't", "wasn't", "weren't",
}

_WORD_RE = re.compile(r"\b[a-z']+\b")


def _analyze(text: str) -> dict[str, Any]:
    """Run sentiment analysis on text, returning structured scores."""
    words = _WORD_RE.findall(text.lower())
    if not words:
        return {"score": 0.0, "label": "neutral", "confidence": 0.0,
                "positive_phrases": [], "negative_phrases": [],
                "word_count": 0, "positive_count": 0, "negative_count": 0}

    pos_count = 0
    neg_count = 0
    pos_phrases: list[str] = []
    neg_phrases: list[str] = []

    window = 3
    for i, word in enumerate(words):
        lookback = words[max(0, i - window):i]
        has_negator = any(w in _NEGATORS for w in lookback)
        has_intensifier = any(w in _INTENSIFIERS for w in lookback)
        multiplier = 1.5 if has_intensifier else 1.0

        if word in _POSITIVE:
            if has_negator:
                neg_count += multiplier
                if len(neg_phrases) < 8:
                    ctx = " ".join(words[max(0, i - 2):i + 1])
                    neg_phrases.append(ctx)
            else:
                pos_count += multiplier
                if len(pos_phrases) < 8:
                    ctx = " ".join(words[max(0, i - 2):i + 1])
                    pos_phrases.append(ctx)
        elif word in _NEGATIVE:
            if has_negator:
                pos_count += multiplier * 0.5
                if len(pos_phrases) < 8:
                    ctx = " ".join(words[max(0, i - 2):i + 1])
                    pos_phrases.append(ctx)
            else:
                neg_count += multiplier
                if len(neg_phrases) < 8:
                    ctx = " ".join(words[max(0, i - 2):i + 1])
                    neg_phrases.append(ctx)

    total_sentiment = pos_count + neg_count
    if total_sentiment == 0:
        score = 0.0
        label = "neutral"
        confidence = 0.3
    else:
        raw = (pos_count - neg_count) / total_sentiment
        score = round(raw, 3)
        confidence = round(min(total_sentiment / len(words) * 10, 1.0), 3)
        if score > 0.15:
            label = "positive"
        elif score < -0.15:
            label = "negative"
        else:
            label = "mixed"

    return {
        "score": score,
        "label": label,
        "confidence": confidence,
        "positive_count": int(pos_count),
        "negative_count": int(neg_count),
        "word_count": len(words),
        "sentiment_density": round(total_sentiment / len(words), 4) if words else 0,
        "positive_phrases": pos_phrases[:5],
        "negative_phrases": neg_phrases[:5],
    }


async def execute_analyze_sentiment(
    text: str,
    *,
    cache: ResponseCache,
    rate_limiter: RateLimiter,
) -> dict[str, Any]:
    """Analyze sentiment of the given text.

    Parameters
    ----------
    text:
        The text to analyze (article body, search snippets, etc.).
    """
    request_id = str(uuid.uuid4())

    if not text or not text.strip():
        from src.middleware.error_handler import validation_error_response
        return validation_error_response([("text", "Text is required")])

    analysis = _analyze(text)

    snippet_lines = [
        f"Sentiment: {analysis['label'].upper()} (score: {analysis['score']}, confidence: {analysis['confidence']})",
        f"Word count: {analysis['word_count']} | Positive signals: {analysis['positive_count']} | Negative signals: {analysis['negative_count']}",
        f"Sentiment density: {analysis['sentiment_density']}",
    ]
    if analysis["positive_phrases"]:
        snippet_lines.append(f"Positive phrases: {', '.join(repr(p) for p in analysis['positive_phrases'])}")
    if analysis["negative_phrases"]:
        snippet_lines.append(f"Negative phrases: {', '.join(repr(p) for p in analysis['negative_phrases'])}")

    snippet = "\n".join(snippet_lines)
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    result = NormalizedResponse(
        articles=[
            NormalizedArticle(
                title=f"Sentiment Analysis — {analysis['label'].upper()}",
                url=f"analysis://sentiment/{request_id}",
                source="SignalOps NLP Engine",
                published_date=now,
                snippet=snippet,
            )
        ],
        query=text[:100],
        total_results=1,
        cached=False,
        request_id=request_id,
    )
    return result.model_dump()
