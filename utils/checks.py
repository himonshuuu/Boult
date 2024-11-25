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

from typing import TYPE_CHECKING, Type

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from discord.ext.commands._types import Check

    from core import Player
    from utils import BoultContext as Context


def in_voice_channel(
    *, bot: bool = False, user: bool = True, same: bool = True
) -> Check[Context]:
    async def predicate(ctx: Context) -> bool:
        assert isinstance(ctx.author, discord.Member)
        if user and ctx.author.voice is None:
            await ctx.send(embed=discord.Embed(color=0x2b2d31).set_author(name="You must be in a voice channel to use this command.", icon_url=ctx.author.display_avatar.url))
            return False
        if bot and ctx.guild.voice_client is None:
            await ctx.send(embed=discord.Embed(color=0x2b2d31).set_author(name="Bot is not in a voice channel.", icon_url=ctx.bot.user.display_avatar.url))
            return False

        if (
            bot
            and user
            and same
            and ctx.voice_client
            and ctx.author.voice
            and ctx.voice_client.channel != ctx.author.voice.channel
        ):
            await ctx.send(embed=discord.Embed(color=0x2b2d31).set_author(name="You must be in same voice channel of Bot's", icon_url=ctx.bot.user.display_avatar.url))
            return False

        return True

    return commands.check(predicate)

def check_home(*, cls: Type[Player]) -> Check[Context]:
    async def predicate(ctx: Context) -> bool:
        if not ctx.voice_client:
            return True
        if not hasattr(ctx.voice_client, "home"):
            return True
        if ctx.voice_client.home is None:
            return True
        if ctx.voice_client.home == ctx.channel:
            return True
        await ctx.send(embed=discord.Embed(color=0x2b2d31).set_author(name=f"You must be in {ctx.voice_client.home.mention} to use this command.", icon_url=ctx.author.display_avatar.url))
        return False

    return commands.check(predicate)

def try_connect(*, cls: Type[Player]) -> Check[Context]:
    async def predicate(ctx: Context) -> bool:
        if ctx.author.voice is None:
            await ctx.send(embed=discord.Embed(color=0x2b2d31).set_author(name="You must be in a voice channel to use this command.", icon_url=ctx.bot.user.display_avatar.url))
            return False

        if ctx.voice_client and ctx.voice_client.channel == ctx.author.voice.channel:
            return True

        if ctx.voice_client and ctx.voice_client.channel != ctx.author.voice.channel:
            await ctx.send(embed=discord.Embed(color=0x2b2d31).set_author(name=f"You must be in same voice channel to use this command.", icon_url=ctx.bot.user.display_avatar.url))
            return False

        if ctx.author.voice.channel:
            try:
                player = await ctx.author.voice.channel.connect(cls=cls, self_deaf=True)
                player.home = ctx.channel
                player.ctx = ctx
            except discord.ClientException as e:
                await ctx.send(embed=discord.Embed(color=0x2b2d31).set_author(name="Failed connecting to channel", icon_url=ctx.bot.user.display_avatar.url))
                return False
        return True

    return commands.check(predicate)
