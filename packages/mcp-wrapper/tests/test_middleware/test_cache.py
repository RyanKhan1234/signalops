"""Tests for src/middleware/cache.py."""

from __future__ import annotations

import time

import pytest

from src.middleware.cache import ResponseCache


class TestCacheKeyGeneration:
    """Test cache key generation."""

    def test_same_params_same_key(self) -> None:
        k1 = ResponseCache.make_key("search_news", {"query": "test", "time_range": "7d"})
        k2 = ResponseCache.make_key("search_news", {"query": "test", "time_range": "7d"})
        assert k1 == k2

    def test_different_params_different_key(self) -> None:
        k1 = ResponseCache.make_key("search_news", {"query": "test1"})
        k2 = ResponseCache.make_key("search_news", {"query": "test2"})
        assert k1 != k2

    def test_different_tool_name_different_key(self) -> None:
        k1 = ResponseCache.make_key("search_news", {"query": "test"})
        k2 = ResponseCache.make_key("search_company_news", {"query": "test"})
        assert k1 != k2

    def test_param_order_independent(self) -> None:
        """Cache key should be the same regardless of dict insertion order."""
        k1 = ResponseCache.make_key(
            "search_news",
            {"query": "test", "time_range": "7d", "num_results": 10},
        )
        k2 = ResponseCache.make_key(
            "search_news",
            {"num_results": 10, "time_range": "7d", "query": "test"},
        )
        assert k1 == k2

    def test_key_is_hex_string(self) -> None:
        key = ResponseCache.make_key("search_news", {"query": "test"})
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


class TestCacheGetSet:
    """Test get/set operations."""

    def test_get_returns_none_for_missing_key(self, news_cache: ResponseCache) -> None:
        assert news_cache.get("nonexistent-key") is None

    def test_set_and_get_returns_value(self, news_cache: ResponseCache) -> None:
        news_cache.set("test-key", {"articles": []})
        result = news_cache.get("test-key")
        assert result == {"articles": []}

    def test_set_overwrites_existing(self, news_cache: ResponseCache) -> None:
        news_cache.set("key", {"version": 1})
        news_cache.set("key", {"version": 2})
        assert news_cache.get("key") == {"version": 2}

    def test_size_increases_after_set(self, news_cache: ResponseCache) -> None:
        assert news_cache.size == 0
        news_cache.set("key1", "value1")
        assert news_cache.size == 1
        news_cache.set("key2", "value2")
        assert news_cache.size == 2

    def test_duplicate_key_does_not_increase_size(
        self, news_cache: ResponseCache
    ) -> None:
        news_cache.set("key", "v1")
        news_cache.set("key", "v2")
        assert news_cache.size == 1


class TestCacheTTL:
    """Test TTL expiry behaviour."""

    def test_expired_entry_returns_none(self) -> None:
        """Entries should expire after TTL seconds."""
        cache = ResponseCache(ttl_seconds=1)
        cache.set("key", "value")
        assert cache.get("key") == "value"
        time.sleep(1.1)
        assert cache.get("key") is None

    def test_unexpired_entry_returns_value(self, news_cache: ResponseCache) -> None:
        news_cache.set("key", "value")
        # 900-second TTL — should still be valid after a few ms
        assert news_cache.get("key") == "value"

    def test_ttl_property(self) -> None:
        cache = ResponseCache(ttl_seconds=300)
        assert cache.ttl == 300


class TestCacheInvalidate:
    """Test cache invalidation."""

    def test_invalidate_existing_key(self, news_cache: ResponseCache) -> None:
        news_cache.set("key", "value")
        removed = news_cache.invalidate("key")
        assert removed is True
        assert news_cache.get("key") is None

    def test_invalidate_nonexistent_key(self, news_cache: ResponseCache) -> None:
        removed = news_cache.invalidate("ghost-key")
        assert removed is False

    def test_clear_empties_cache(self, news_cache: ResponseCache) -> None:
        news_cache.set("k1", "v1")
        news_cache.set("k2", "v2")
        news_cache.clear()
        assert news_cache.size == 0
        assert news_cache.get("k1") is None
