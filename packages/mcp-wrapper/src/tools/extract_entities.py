"""``extract_entities`` MCP tool — computational named entity recognition.

Performs regex and heuristic-based entity extraction from text.
Identifies: organizations, people, technologies, monetary amounts,
percentages, stock tickers, and dates.

No external API calls — pure local computation.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from src.middleware.cache import ResponseCache
from src.middleware.rate_limiter import RateLimiter
from src.serpapi.models import NormalizedArticle, NormalizedResponse

logger = logging.getLogger(__name__)

# --- Entity extraction patterns ---

_MONEY_RE = re.compile(
    r"\$\s?\d+(?:\.\d+)?\s*(?:billion|million|trillion|bn|mn|tn|B|M|T|k)?"
    r"|\d+(?:\.\d+)?\s*(?:billion|million|trillion)\s*(?:dollars|USD)?",
    re.IGNORECASE,
)

_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?(?:\s*%|\s+percent(?:age)?)", re.IGNORECASE)

_TICKER_RE = re.compile(
    r"\b([A-Z]{1,5})(?::(?:NASDAQ|NYSE|AMEX|LSE|TSE))\b"
    r"|\b(?:ticker|stock|shares?|NYSE|NASDAQ)[\s:]+([A-Z]{1,5})\b"
)

_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{4}\b"
    r"|\bQ[1-4]\s+\d{4}\b"
    r"|\b(?:FY|CY)\s?\d{4}\b",
    re.IGNORECASE,
)

_KNOWN_ORGS = {
    "OpenAI", "Anthropic", "Google", "Microsoft", "Meta", "Apple", "Amazon",
    "NVIDIA", "Tesla", "Netflix", "Salesforce", "Adobe", "IBM", "Intel",
    "AMD", "Qualcomm", "Samsung", "Huawei", "ByteDance", "TikTok",
    "DeepMind", "Cohere", "Mistral", "Stability AI", "Midjourney",
    "Perplexity", "Databricks", "Snowflake", "Palantir", "Stripe",
    "SpaceX", "Uber", "Airbnb", "Coinbase", "Robinhood",
    "Goldman Sachs", "JPMorgan", "Morgan Stanley", "BlackRock",
    "Sequoia", "Andreessen Horowitz", "a16z", "Y Combinator",
    "AWS", "Azure", "GCP", "GitHub", "GitLab", "Docker",
    "SEC", "FTC", "FDA", "DOJ", "Pentagon", "NATO", "EU",
    "United Nations", "World Bank", "IMF", "WHO", "IEEE",
    "Gartner", "McKinsey", "Deloitte", "Accenture", "PwC",
}

_KNOWN_TECH = {
    "GPT-4", "GPT-5", "GPT-4o", "Claude", "Gemini", "Llama", "Mistral",
    "DALL-E", "Sora", "Copilot", "ChatGPT", "Bard",
    "LangChain", "LangGraph", "AutoGPT", "CrewAI", "Dify",
    "PyTorch", "TensorFlow", "JAX", "Hugging Face", "ONNX",
    "Kubernetes", "Docker", "Terraform", "React", "Next.js",
    "transformer", "diffusion", "RAG", "RLHF", "fine-tuning",
    "LLM", "LLMs", "SLM", "AGI", "ASI", "NLP", "NER",
    "reinforcement learning", "neural network", "deep learning",
    "machine learning", "computer vision", "generative AI",
    "agentic AI", "multimodal", "embedding", "vector database",
    "MCP", "tool use", "function calling",
    "blockchain", "Web3", "cryptocurrency", "DeFi", "NFT",
    "quantum computing", "edge computing", "5G", "IoT",
}

_CAPITALIZED_PHRASE_RE = re.compile(
    r"\b(?:[A-Z][a-z]+(?:\s+(?:of|the|and|for|in|on|at|by|to)\s+)?){2,4}(?:[A-Z][a-z]+)\b"
)

_PERSON_TITLE_RE = re.compile(
    r"(?:CEO|CTO|COO|CFO|CMO|President|Chairman|Director|VP|Professor|Dr\.|Mr\.|Ms\.)"
    r"\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})"
)


def _extract(text: str) -> dict[str, Any]:
    """Extract named entities from text."""
    entities: dict[str, list[str]] = {
        "organizations": [],
        "people": [],
        "technologies": [],
        "monetary_amounts": [],
        "percentages": [],
        "tickers": [],
        "dates": [],
    }

    for org in _KNOWN_ORGS:
        if org.lower() in text.lower():
            entities["organizations"].append(org)

    for tech in _KNOWN_TECH:
        pattern = re.compile(re.escape(tech), re.IGNORECASE)
        if pattern.search(text):
            entities["technologies"].append(tech)

    for m in _MONEY_RE.finditer(text):
        val = m.group().strip()
        if val not in entities["monetary_amounts"]:
            entities["monetary_amounts"].append(val)

    for m in _PERCENT_RE.finditer(text):
        val = m.group().strip()
        if val not in entities["percentages"]:
            entities["percentages"].append(val)

    for m in _TICKER_RE.finditer(text):
        ticker = m.group(1) or m.group(2)
        if ticker and ticker not in entities["tickers"] and len(ticker) >= 2:
            entities["tickers"].append(ticker)

    for m in _DATE_RE.finditer(text):
        val = m.group().strip()
        if val not in entities["dates"]:
            entities["dates"].append(val)

    for m in _PERSON_TITLE_RE.finditer(text):
        name = m.group(1).strip()
        if name not in entities["people"] and len(name.split()) >= 2:
            entities["people"].append(name)

    for key in entities:
        entities[key] = entities[key][:15]

    total = sum(len(v) for v in entities.values())
    return {"entities": entities, "total_entities": total}


async def execute_extract_entities(
    text: str,
    *,
    cache: ResponseCache,
    rate_limiter: RateLimiter,
) -> dict[str, Any]:
    """Extract named entities from text.

    Parameters
    ----------
    text:
        The text to analyze for entity extraction.
    """
    request_id = str(uuid.uuid4())

    if not text or not text.strip():
        from src.middleware.error_handler import validation_error_response
        return validation_error_response([("text", "Text is required")])

    result = _extract(text)
    ents = result["entities"]

    snippet_parts = [f"Total entities found: {result['total_entities']}"]
    for category, items in ents.items():
        if items:
            label = category.replace("_", " ").title()
            snippet_parts.append(f"{label}: {', '.join(items)}")

    snippet = "\n".join(snippet_parts)
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    response = NormalizedResponse(
        articles=[
            NormalizedArticle(
                title=f"Entity Extraction — {result['total_entities']} entities found",
                url=f"analysis://entities/{request_id}",
                source="SignalOps NER Engine",
                published_date=now,
                snippet=snippet,
            )
        ],
        query=text[:100],
        total_results=1,
        cached=False,
        request_id=request_id,
    )
    return response.model_dump()
