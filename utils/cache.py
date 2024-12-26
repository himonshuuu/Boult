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
import logging
import time
from collections import OrderedDict
from threading import Lock
from typing import Any, Callable, Dict, Generic, Optional, TypeVar, Union

from lru import LRU

K = TypeVar('K')
V = TypeVar('V')
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

class TTLCache(Generic[K, V]):
    """
    A thread-safe cache implementation with time-based expiration of entries.
    
    Features:
    - Generic type support for keys and values
    - Thread-safe operations
    - Automatic cleanup of expired entries
    - Optional maximum size limit
    - Least Recently Used (LRU) eviction when max size is reached
    - O(1) complexity for get/set operations
    
    Args:
        ttl (float): Time to live in seconds for cache entries
        max_size (Optional[int]): Maximum number of entries to store (None for unlimited)
        cleanup_interval (float): Time between cleanup operations in seconds
    """
    
    def __init__(
        self,
        ttl: float = 300,
        max_size: Optional[int] = None,
        cleanup_interval: float = 60.0
    ):
        self._cache: OrderedDict[K, V] = OrderedDict()
        self._expires: Dict[K, float] = {}
        self._ttl = ttl
        self._max_size = max_size
        self._cleanup_interval = cleanup_interval
        self._lock = Lock()
        self._last_cleanup = time.monotonic()
        
    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """
        Retrieve a value from the cache.
        
        Args:
            key: The key to look up
            default: Value to return if key is not found or expired
            
        Returns:
            The cached value if found and not expired, otherwise the default value
        """
        with self._lock:
            self._maybe_cleanup()
            
            if key not in self._cache:
                return default
                
            if self._is_expired(key):
                self._remove(key)
                return default
                
            # Move to end for LRU
            value = self._cache.pop(key)
            self._cache[key] = value
            return value
            
    def set(self, key: K, value: V, ttl: Optional[float] = None) -> None:
        """
        Add or update a cache entry.
        
        Args:
            key: Key for the entry
            value: Value to cache
            ttl: Optional custom TTL for this entry (overrides default)
        """
        with self._lock:
            self._maybe_cleanup()
            
            if self._max_size and len(self._cache) >= self._max_size:
                # Remove oldest entry if at max size
                self._cache.popitem(last=False)
                
            # Remove old entry if it exists
            if key in self._cache:
                del self._cache[key]
                
            self._cache[key] = value
            self._expires[key] = time.monotonic() + (ttl if ttl is not None else self._ttl)
            
    def delete(self, key: K) -> bool:
        """
        Remove an entry from the cache.
        
        Args:
            key: Key to remove
            
        Returns:
            True if key was found and removed, False otherwise
        """
        with self._lock:
            if key in self._cache:
                self._remove(key)
                return True
            return False
            
    def clear(self) -> None:
        """Remove all entries from the cache."""
        with self._lock:
            self._cache.clear()
            self._expires.clear()
            
    def size(self) -> int:
        """Return current number of entries in cache."""
        with self._lock:
            return len(self._cache)
            
    def cleanup(self) -> int:
        """
        Remove all expired entries.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            initial_size = len(self._cache)
            expired = [k for k in self._cache if self._is_expired(k)]
            for key in expired:
                self._remove(key)
            return initial_size - len(self._cache)
            
    def touch(self, key: K, ttl: Optional[float] = None) -> bool:
        """
        Update the expiration time for an entry.
        
        Args:
            key: Key to update
            ttl: Optional new TTL value
            
        Returns:
            True if key was found and updated, False otherwise
        """
        with self._lock:
            if key in self._cache:
                self._expires[key] = time.monotonic() + (ttl if ttl is not None else self._ttl)
                return True
            return False
            
    def get_ttl(self, key: K) -> Optional[float]:
        """
        Get remaining TTL for a cache entry.
        
        Args:
            key: Key to check
            
        Returns:
            Remaining TTL in seconds or None if key not found
        """
        with self._lock:
            if key in self._expires:
                remain = self._expires[key] - time.monotonic()
                return max(0.0, remain) if remain > 0 else None
            return None
            
    def _is_expired(self, key: K) -> bool:
        """Check if a cache entry has expired."""
        return time.monotonic() >= self._expires[key]
        
    def _remove(self, key: K) -> None:
        """Remove a cache entry and its expiration time."""
        del self._cache[key]
        del self._expires[key]
        
    def _maybe_cleanup(self) -> None:
        """Perform cleanup if cleanup_interval has elapsed."""
        now = time.monotonic()
        if now - self._last_cleanup >= self._cleanup_interval:
            self.cleanup()
            self._last_cleanup = now

    def __getitem__(self, key: K) -> V:
        """Dictionary-style access to cache entries."""
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value
        
    def __setitem__(self, key: K, value: V) -> None:
        """Dictionary-style setting of cache entries."""
        self.set(key, value)
        
    def __delitem__(self, key: K) -> None:
        """Dictionary-style deletion of cache entries."""
        if not self.delete(key):
            raise KeyError(key)
            
    def __len__(self) -> int:
        """Return current cache size."""
        return self.size()
        
    def __contains__(self, key: K) -> bool:
        """Check if key exists in cache and is not expired."""
        return self.get(key) is not None
        
    def __bool__(self) -> bool:
        """Return True if cache contains any non-expired entries."""
        return bool(len(self))