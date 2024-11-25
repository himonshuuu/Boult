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
from typing import Any, Callable, Coroutine


class TimedTask:
    def __init__(self, wait: int = 60):
        self.wait = wait
        self.task: asyncio.Task | None = None
        self.task_function: Callable[[], Coroutine[Any, Any, Any]] | None = None

    async def _run_task(self) -> None:
        await asyncio.sleep(self.wait)
        if self.task_function:
            await self.task_function()

    def start_task(self, task_function: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any) -> None:
        self.task_function = lambda: task_function(*args, **kwargs)
        self.task = asyncio.create_task(self._run_task())

    def cancel_task(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
