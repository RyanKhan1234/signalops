"""In-memory TTL cache for SerpApi responses.

Uses ``cachetools.TTLCache`` as the backing store.  Cache keys are stable
SHA-256 hashes of the tool name and sorted input parameters so that
semantically identical calls hit the same cache entry regardless of argument
ordering.

Redis upgrade path
------------------
To upgrade to Redis, swap out the ``TTLCache`` implementation in
``ResponseCache`` for a Redis client (e.g. ``redis.asyncio``).  The public
interface — ``get``, ``set``, ``make_key`` — is designed to remain unchanged.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Default maximum number of entries to keep in the in-memory cache.
_DEFAULT_MAX_SIZE: int = 512


class ResponseCache:
    """TTL-based in-memory cache for normalised SerpApi responses.

    Parameters
    ----------
    ttl_seconds:
        Number of seconds after which a cache entry expires.
    max_size:
        Maximum number of entries to hold in memory before evicting oldest.
    """

    def __init__(
        self,
        ttl_seconds: int = 900,
        max_size: int = _DEFAULT_MAX_SIZE,
    ) -> None:
        self._ttl = ttl_seconds
        self._cache: TTLCache = TTLCache(maxsize=max_size, ttl=ttl_seconds)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @staticmethod
    def make_key(tool_name: str, params: dict[str, Any]) -> str:
        """Generate a stable cache key from the tool name and input parameters.

        The key is a lowercase hex SHA-256 digest of the canonical JSON
        representation of ``{tool_name, **sorted_params}``.

        Parameters
        ----------
        tool_name:
            The MCP tool name (e.g. ``"search_news"``).
        params:
            The tool input parameters (order-independent).

        Returns
        -------
        str
            A 64-character hex string suitable for use as a cache key.
        """
        payload = {"_tool": tool_name, **dict(sorted(params.items()))}
        serialised = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialised.encode()).hexdigest()

    def get(self, key: str) -> Any | None:
        """Retrieve a cached value by key.

        Parameters
        ----------
        key:
            Cache key produced by :meth:`make_key`.

        Returns
        -------
        Any | None
            The cached value, or ``None`` if absent or expired.
        """
        value = self._cache.get(key)
        if value is not None:
            logger.debug("Cache HIT for key %s…", key[:16])
        else:
            logger.debug("Cache MISS for key %s…", key[:16])
        return value

    def set(self, key: str, value: Any) -> None:
        """Store a value in the cache.

        Parameters
        ----------
        key:
            Cache key produced by :meth:`make_key`.
        value:
            The value to cache (must be serialisable, though the in-memory
            cache stores Python objects directly).
        """
        self._cache[key] = value
        logger.debug(
            "Cache SET key %s… (TTL=%ds, size=%d/%d)",
            key[:16],
            self._ttl,
            len(self._cache),
            self._cache.maxsize,
        )

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from the cache.

        Returns
        -------
        bool
            ``True`` if the key existed and was removed, ``False`` otherwise.
        """
        existed = key in self._cache
        if existed:
            del self._cache[key]
            logger.debug("Cache INVALIDATED key %s…", key[:16])
        return existed

    def clear(self) -> None:
        """Remove all entries from the cache."""
        self._cache.clear()
        logger.debug("Cache CLEARED")

    @property
    def size(self) -> int:
        """Number of live entries currently in the cache."""
        return len(self._cache)

    @property
    def ttl(self) -> int:
        """Configured TTL in seconds."""
        return self._ttl
