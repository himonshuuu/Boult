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


import asyncio
import datetime
import logging
import traceback
from enum import Enum
from typing import Any, Callable, Coroutine, List, Optional, Set

logger = logging.getLogger(__name__)

class TaskState(Enum):
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskMetrics:
    def __init__(self):
        self.start_time: Optional[datetime.datetime] = None
        self.end_time: Optional[datetime.datetime] = None
        self.attempts: int = 0
        self.failures: int = 0
        self.last_error: Optional[Exception] = None

class TimedTask:
    def __init__(self, wait: int = 60, max_retries: int = 3, retry_delay: int = 5):
        self.wait = wait
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.task: Optional[asyncio.Task] = None
        self.task_function: Optional[Callable[[], Coroutine[Any, Any, Any]]] = None
        self.state: TaskState = TaskState.PENDING
        self.metrics: TaskMetrics = TaskMetrics()
        self._dependencies: Set[TimedTask] = set()
        self._dependents: Set[TimedTask] = set()
        self._cleanup_callbacks: List[Callable[[], Coroutine[Any, Any, Any]]] = []
        self._lock = asyncio.Lock()

    def add_dependency(self, task: 'TimedTask') -> None:
        self._dependencies.add(task)
        task._dependents.add(self)

    def add_cleanup_callback(self, callback: Callable[[], Coroutine[Any, Any, Any]]) -> None:
        self._cleanup_callbacks.append(callback)

    async def _execute_with_retries(self) -> None:
        for attempt in range(self.max_retries + 1):
            try:
                self.metrics.attempts += 1
                if self.task_function:
                    await self.task_function()
                return
            except Exception as e:
                self.metrics.failures += 1
                self.metrics.last_error = e
                logger.error(f"Task attempt {attempt + 1} failed: {str(e)}\n{traceback.format_exc()}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
                else:
                    self.state = TaskState.FAILED
                    raise

    async def _run_task(self) -> None:
        async with self._lock:
            # Wait for dependencies to complete
            for dep in self._dependencies:
                if dep.state not in (TaskState.COMPLETED, TaskState.CANCELLED):
                    await asyncio.sleep(0.1)

            self.state = TaskState.RUNNING
            self.metrics.start_time = datetime.datetime.now()

            try:
                await asyncio.sleep(self.wait)
                await self._execute_with_retries()
                self.state = TaskState.COMPLETED
            except asyncio.CancelledError:
                self.state = TaskState.CANCELLED
                raise
            except Exception as e:
                logger.error(f"Task failed after all retries: {str(e)}")
                raise
            finally:
                self.metrics.end_time = datetime.datetime.now()
                for callback in self._cleanup_callbacks:
                    try:
                        await callback()
                    except Exception as e:
                        logger.error(f"Cleanup callback failed: {str(e)}")

    def start_task(self, task_function: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any) -> None:
        self.task_function = lambda: task_function(*args, **kwargs)
        self.task = asyncio.create_task(self._run_task())
        self.task.add_done_callback(self._handle_task_completion)

    def _handle_task_completion(self, future: asyncio.Future) -> None:
        try:
            future.result()
        except Exception as e:
            logger.error(f"Task completed with error: {str(e)}")

    def cancel_task(self) -> None:
        if self.task and not self.task.done():
            # Cancel dependent tasks first
            for dependent in self._dependents:
                dependent.cancel_task()
            self.task.cancel()
            self.state = TaskState.CANCELLED
