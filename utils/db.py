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



import asyncpg
from typing import Optional, Dict, Any, List, Union, TypeVar
from contextlib import asynccontextmanager
import logging
from functools import wraps
import time

T = TypeVar('T')

class Row:
    """Represents a single row from a database query."""
    __slots__ = ('__dict__',)  # Memory optimization

    def __init__(self, data: Dict[str, Any]):
        self.__dict__.update(data)

    def __repr__(self) -> str:
        return f"<Row {self.__dict__}>"
    
    def get(self, key: str, default: T = None) -> Union[Any, T]:
        """Safely get a value from the row."""
        return self.__dict__.get(key, default)

class DatabaseManager:
    def __init__(self, pool_size: int = 20, timeout: float = 30.0):
        self.pool: Optional[asyncpg.pool.Pool] = None
        self._pool_size = pool_size
        self._timeout = timeout
        self.logger = logging.getLogger('database')
        self._query_count = 0
        self._last_queries: Dict[str, float] = {}  # Query cache timing

    async def initialize(self, dsn: str) -> None:
        """Initialize the database pool."""
        try:
            self.pool = await asyncpg.create_pool(
                dsn,
                min_size=2,
                max_size=self._pool_size,
                command_timeout=self._timeout,
                statement_cache_size=200
            )
            self.logger.info("Database pool initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize database pool: {e}")
            raise

    async def close(self) -> None:
        """Close the database pool."""
        if self.pool:
            await self.pool.close()
            self.logger.info("Database pool closed")

    def log_query(func):
        """Decorator to log query execution time."""
        @wraps(func)
        async def wrapper(self, query: str, *args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(self, query, *args, **kwargs)
                execution_time = time.perf_counter() - start
                self._last_queries[query] = execution_time
                self._query_count += 1
                
                if execution_time > 1.0:  # Log slow queries
                    self.logger.warning(f"Slow query ({execution_time:.2f}s): {query}")
                return result
            except Exception as e:
                self.logger.error(f"Query failed: {query}, Error: {e}")
                raise
        return wrapper

    @asynccontextmanager
    async def acquire(self) -> asyncpg.Connection:
        """Get a connection from the pool using async context manager."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as connection:
            try:
                yield connection
            except Exception as e:
                self.logger.error(f"Database connection error: {e}")
                raise

    @log_query
    async def fetch_one(self, query: str, *args: Any) -> Optional[Row]:
        """Fetch a single row from the database."""
        async with self.acquire() as connection:
            result = await connection.fetchrow(query, *args)
            return Row(dict(result)) if result else None

    @log_query
    async def fetch_all(self, query: str, *args: Any) -> List[Row]:
        """Fetch multiple rows from the database."""
        async with self.acquire() as connection:
            results = await connection.fetch(query, *args)
            return [Row(dict(row)) for row in results]

    @log_query
    async def execute(self, query: str, *args: Any) -> str:
        """Execute a non-query operation."""
        async with self.acquire() as connection:
            return await connection.execute(query, *args)

    async def execute_many(self, query: str, args: List[tuple]) -> None:
        """Execute the same operation with different sets of arguments."""
        async with self.acquire() as connection:
            await connection.executemany(query, args)

    async def get_query_stats(self) -> Dict[str, Any]:
        """Get statistics about query execution."""
        return {
            'total_queries': self._query_count,
            'slow_queries': len([t for t in self._last_queries.values() if t > 1.0]),
            'average_time': sum(self._last_queries.values()) / len(self._last_queries) if self._last_queries else 0
        }

    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions."""
        async with self.acquire() as connection:
            async with connection.transaction():
                yield connection

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = $1
            );
        """
        return await self.fetch_one(query, table_name) is not None
