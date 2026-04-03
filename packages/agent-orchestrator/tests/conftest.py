"""Shared pytest fixtures for Agent Orchestrator tests."""

from __future__ import annotations

import pytest

from src.models.digest import Article, MCPToolResult


# ---------------------------------------------------------------------------
# Reusable article fixtures
# ---------------------------------------------------------------------------


def make_article(
    title: str = "Test Article",
    url: str = "https://example.com/article-1",
    source: str = "TechCrunch",
    published_date: str = "2026-03-01",
    snippet: str = "This is a test snippet about research topic.",
) -> Article:
    """Factory function for creating test Article objects."""
    return Article(
        title=title,
        url=url,
        source=source,
        published_date=published_date,
        snippet=snippet,
    )


def make_mcp_result(
    articles: list[Article] | None = None,
    query: str = "OpenAI",
    total_results: int = 2,
    cached: bool = False,
    request_id: str = "req_test_123",
) -> MCPToolResult:
    """Factory function for creating test MCPToolResult objects."""
    if articles is None:
        articles = [
            make_article(
                title="OpenAI Expands Self-Serve Ad Platform",
                url="https://example.com/walmart-connect-self-serve",
                snippet="OpenAI announced major expansions to its self-serve advertising platform, "
                "adding new targeting options and automated bidding.",
            ),
            make_article(
                title="OpenAI Q1 2026 Revenue Up 35%",
                url="https://example.com/walmart-connect-q1-2026",
                snippet="Walmart's advertising business reported strong Q1 2026 results with revenue "
                "growing 35% year-over-year driven by Connect platform adoption.",
            ),
        ]
    return MCPToolResult(
        articles=articles,
        query=query,
        total_results=total_results,
        cached=cached,
        request_id=request_id,
    )


@pytest.fixture
def sample_articles() -> list[Article]:
    """Fixture providing a sample list of articles for testing."""
    return [
        make_article(
            title="OpenAI Expands Self-Serve Ad Platform",
            url="https://example.com/walmart-connect-self-serve",
            snippet="OpenAI announced major expansions to its self-serve advertising platform.",
        ),
        make_article(
            title="OpenAI Q1 2026 Revenue Up 35%",
            url="https://example.com/walmart-connect-q1-2026",
            snippet="Walmart's advertising business reported strong Q1 2026 results.",
        ),
        make_article(
            title="Retail Media Network Competition Intensifies",
            url="https://example.com/retail-media-competition",
            source="AdAge",
            snippet="Competition in the AI research network space is intensifying with Amazon, "
            "Walmart, and Target all expanding their ad platforms.",
        ),
    ]


@pytest.fixture
def sample_mcp_result(sample_articles: list[Article]) -> MCPToolResult:
    """Fixture providing a sample MCPToolResult."""
    return make_mcp_result(articles=sample_articles)
