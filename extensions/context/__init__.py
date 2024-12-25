from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

from .context import *

if TYPE_CHECKING:
    from core import Boult

async def setup(bot: Boult) -> None:
    bot.context = BoultContext

async def teardown(bot: Boult) -> None:
    bot.context = commands.Context