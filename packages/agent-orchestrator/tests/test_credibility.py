"""Tests for source credibility scoring on Risk objects."""

from __future__ import annotations

from src.agent.composer import _score_source_credibility
from src.models.digest import Article


def make_article(url: str, source: str) -> Article:
    return Article(
        title="Test",
        url=url,
        source=source,
        published_date="2026-03-01",
        snippet="Test snippet.",
    )


def url_map(*articles: Article) -> dict[str, Article]:
    return {a.url: a for a in articles}


class TestScoreSourceCredibility:

    def test_recognized_outlet_scores_high(self) -> None:
        article = make_article("https://reuters.com/article-1", "Reuters")
        score = _score_source_credibility(["https://reuters.com/article-1"], url_map(article))
        assert score == "high"

    def test_bloomberg_scores_high(self) -> None:
        article = make_article("https://bloomberg.com/article-1", "Bloomberg")
        score = _score_source_credibility(["https://bloomberg.com/article-1"], url_map(article))
        assert score == "high"

    def test_techcrunch_scores_high(self) -> None:
        article = make_article("https://techcrunch.com/article-1", "TechCrunch")
        score = _score_source_credibility(["https://techcrunch.com/article-1"], url_map(article))
        assert score == "high"

    def test_three_distinct_unknown_outlets_scores_high(self) -> None:
        a1 = make_article("https://blog1.com/a", "Random Blog One")
        a2 = make_article("https://blog2.com/a", "Random Blog Two")
        a3 = make_article("https://blog3.com/a", "Random Blog Three")
        score = _score_source_credibility(
            ["https://blog1.com/a", "https://blog2.com/a", "https://blog3.com/a"],
            url_map(a1, a2, a3),
        )
        assert score == "high"

    def test_two_distinct_unknown_outlets_scores_medium(self) -> None:
        a1 = make_article("https://blog1.com/a", "Random Blog One")
        a2 = make_article("https://blog2.com/a", "Random Blog Two")
        score = _score_source_credibility(
            ["https://blog1.com/a", "https://blog2.com/a"],
            url_map(a1, a2),
        )
        assert score == "medium"

    def test_single_unknown_outlet_scores_low(self) -> None:
        article = make_article("https://randomnews.io/article-1", "RandomNews")
        score = _score_source_credibility(["https://randomnews.io/article-1"], url_map(article))
        assert score == "low"

    def test_empty_source_urls_scores_low(self) -> None:
        score = _score_source_credibility([], {})
        assert score == "low"

    def test_url_not_in_article_map_scores_low(self) -> None:
        # URL present in risk but article not fetched
        score = _score_source_credibility(["https://missing.com/article"], {})
        assert score == "low"

    def test_case_insensitive_outlet_matching(self) -> None:
        # Source stored with mixed case
        article = make_article("https://reuters.com/article-1", "REUTERS")
        score = _score_source_credibility(["https://reuters.com/article-1"], url_map(article))
        assert score == "high"

    def test_one_recognized_outlet_among_unknowns_still_scores_high(self) -> None:
        a1 = make_article("https://reuters.com/a", "Reuters")
        a2 = make_article("https://randomblog.io/a", "RandomBlog")
        score = _score_source_credibility(
            ["https://reuters.com/a", "https://randomblog.io/a"],
            url_map(a1, a2),
        )
        assert score == "high"

    def test_duplicate_outlet_does_not_inflate_count(self) -> None:
        # Two URLs from the same unknown outlet — still just 1 distinct outlet → low
        a1 = make_article("https://blog.io/article-1", "Unknown Blog")
        a2 = make_article("https://blog.io/article-2", "Unknown Blog")
        score = _score_source_credibility(
            ["https://blog.io/article-1", "https://blog.io/article-2"],
            url_map(a1, a2),
        )
        assert score == "low"
