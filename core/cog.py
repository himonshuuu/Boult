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
import typing
from datetime import datetime

import discord
from discord.ext.commands import Cog

from .bot import Boult

logger = logging.getLogger(__name__)

class Cog(Cog):
    """
    Enhanced subclass of discord.ext.commands.Cog with additional functionality
    for better cog management and debugging capabilities.
    """

    def __init__(self, bot: "Boult"):
        """
        Initialize the cog with extended features.
        
        Args:
            bot: The main bot instance this cog is attached to
        """
        self.bot = bot
        self._start_time = datetime.now()
        self._last_error: typing.Optional[Exception] = None
        self._is_ready = asyncio.Event()
    

    def __repr__(self) -> str:
        """
        Enhanced string representation of the cog instance.
        
        Returns:
            str: Detailed string representation including cog status
        """
        status = "ready" if self._is_ready.is_set() else "not ready"
        uptime = datetime.now() - self._start_time
        return f"<{self.__class__.__name__} name={self.__class__.__name__} status={status} uptime={uptime}>"

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        """
        Returns the display emoji for this cog.
        Can be overridden by subclasses to provide custom emojis.
        
        Returns:
            discord.PartialEmoji: The emoji to display for this cog
        """
        return discord.PartialEmoji(name="question_mark", id=1310234747137691749)

    @property
    def uptime(self) -> float:
        """
        Calculate the uptime of this cog in seconds.
        
        Returns:
            float: The number of seconds this cog has been running
        """
        return (datetime.now() - self._start_time).total_seconds()

    async def cog_load(self) -> None:
        """
        Called when the cog is loaded.
        Sets up any necessary initialization.
        """
        self.bot.logger.debug(f"Loading cog {self.__class__.__name__}")
        self._is_ready.set()

    async def cog_unload(self) -> None:
        """
        Called when the cog is unloaded.
        Handles cleanup tasks.
        """
        self.bot.logger.debug(f"Unloading {self.__class__.__name__}")
        self._is_ready.clear()

    def log_error(self, error: Exception) -> None:
        """
        Log an error that occurred in this cog.
        
        Args:
            error: The exception that occurred
        """
        self._last_error = error
        self.bot.logger.error(f"Error in {self.__class__.__name__}: {error}", exc_info=error)
