""" 
MIT License

Copyright (c) 2024 Himangshu Saikia

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import asyncio
import time
import logging
from typing import Any, Callable, Dict, TypeVar, Optional

from lru import LRU

T = TypeVar('T')
logger = logging.getLogger(__name__)

class CacheManager:
    """A cache manager that provides TTL and size-based caching with async support."""
    
    def __init__(self, max_size: int = 1000, ttl: float = 3600):
        """
        Initialize the cache manager.
        
        Args:
            max_size: Maximum number of items to store in cache
            ttl: Time to live in seconds for cache entries
        """
        self._cache: Dict[str, tuple[Any, float]] = LRU(max_size)
        self._ttl = ttl
        self._hits = 0
        self._misses = 0
        self._lock = asyncio.Lock()

    async def get(self, key: str, fetcher: Optional[Callable[[], T]] = None) -> Optional[T]:
        """
        Get a value from cache, fetching and caching if not present and fetcher provided.
        
        Args:
            key: Cache key
            fetcher: Optional callable that returns/awaits the value if not in cache
            
        Returns:
            The cached value, fetched value if fetcher provided, or None if not found
        """
        async with self._lock:
            # Check if key exists and is not expired
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.monotonic() - timestamp <= self._ttl:
                    self._hits += 1
                    return value
                else:
                    # Remove expired entry
                    del self._cache[key]

            self._misses += 1
            
            if fetcher is None:
                return None
                
            try:
                # Fetch new value
                value = fetcher()
                if asyncio.iscoroutine(value):
                    value = await value
                    
                # Cache the new value
                self._cache[key] = (value, time.monotonic())
                return value
                
            except Exception as e:
                logger.error(f"Error fetching value for key {key}: {str(e)}")
                raise

    async def set(self, key: str, value: Any, expire: float = None) -> None:
        """Set a value in cache with optional expiration."""
        expire = expire or self._ttl
        self._cache[key] = (value, time.monotonic() + expire)
        logger.debug(f"Set cache key {key} with value {value} and expiration {expire}")

    def invalidate(self, key: str) -> None:
        """Remove a specific key from cache."""
        self._cache.pop(key, None)
        
    def invalidate_pattern(self, pattern: str) -> None:
        """Remove all keys containing the pattern."""
        keys_to_remove = [k for k in self._cache.keys() if pattern in k]
        for key in keys_to_remove:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all entries from cache."""
        self._cache.clear()

    def get_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return {
            'size': len(self._cache),
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0
        }
    
    def cleanup_expired(self) -> None:
        """Cleanup expired entries from cache."""
        now = time.monotonic()
        expired_keys = [k for k, (_, expiry) in self._cache.items() if now > expiry]
        for key in expired_keys:
            self._cache.pop(key, None)

    def cleanup_old(self) -> None:
        """Cleanup old entries from cache."""
        now = time.monotonic()
        expired_keys = [k for k, (_, expiry) in self._cache.items() if now > expiry]
        for key in expired_keys:
            self._cache.pop(key, None)
