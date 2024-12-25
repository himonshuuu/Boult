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
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, Protocol, TypeVar, cast

import discord
from discord.ext import commands

from core import Boult, Cog
from core.player import Player
from extensions.context import BoultContext
from utils.checks import in_voice_channel

T = TypeVar("T")
BotT = TypeVar("BotT", bound="Boult")
CogT = TypeVar("CogT", bound="Utility")

logger = logging.getLogger(__name__)

class VoiceStateManager(Protocol):
    async def connect(self, *, timeout: float, reconnect: bool) -> None: ...
    async def disconnect(self, *, force: bool = False) -> None: ...

class UtilityConfiguration:
    def __init__(self, **kwargs: Any) -> None:
        self.search_engines: Dict[str, str] = {
            "youtube-music": "ytmsearch",
            "soundcloud": "scsearch", 
            "youtube": "ytsearch",
            "spotify": "spsearch",
            "jiosaavn": "jssearch"
        }
        self.default_search_engine: Optional[str] = kwargs.get("default_search_engine")
        self.voice_timeout: float = kwargs.get("voice_timeout", 300.0)
        self.voice_reconnect: bool = kwargs.get("voice_reconnect", True)

class Utility(Cog):
    """Advanced utility functionality for bot configuration and voice management."""

    def __init__(self, bot: Boult) -> None:
        super().__init__(bot)
        self.config = UtilityConfiguration()
        self._voice_states: Dict[int, VoiceStateManager] = {}
        self._voice_locks: Dict[int, asyncio.Lock] = {}
        self._last_member: Optional[discord.Member] = None
        self._init_time = datetime.now(timezone.utc)

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(id=1257989664418168932, name="utility")

    @property
    def uptime(self) -> float:
        return (datetime.now(timezone.utc) - self._init_time).total_seconds()

    async def _get_voice_state(self, guild_id: int) -> Optional[VoiceStateManager]:
        return self._voice_states.get(guild_id)

    async def _acquire_voice_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._voice_locks:
            self._voice_locks[guild_id] = asyncio.Lock()
        return self._voice_locks[guild_id]

    @commands.hybrid_command(name="join", aliases=["connect"], with_app_command=True)
    @in_voice_channel(user=True)
    async def join(self, ctx: BoultContext, channel: Optional[discord.VoiceChannel] = None) -> None:
        """
        Join a voice channel with advanced connection handling.

        Parameters
        -----------
        channel: Optional[discord.VoiceChannel]
            The voice channel to join. If not specified, joins the author's channel.

        Raises
        -------
        commands.VoiceError
            If voice connection fails or times out
        """
        if ctx.interaction:
            await ctx.defer()

        async with await self._acquire_voice_lock(ctx.guild.id):
            target_channel = channel or getattr(ctx.author.voice, "channel", None)
            
            if not target_channel:
                raise commands.VoiceError("No valid voice channel found to join")

            try:
                voice_client = await target_channel.connect(
                    timeout=self.config.voice_timeout,
                    reconnect=self.config.voice_reconnect,
                    cls=Player,
                    self_deaf=True
                )
                self._voice_states[ctx.guild.id] = cast(VoiceStateManager, voice_client)
                
                embed = discord.Embed(
                    color=self.bot.config.color.color,
                    timestamp=datetime.now(timezone.utc)
                ).set_author(
                    name=f"Connected to {target_channel.name}",
                    icon_url=self.bot.user.display_avatar.url
                )
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Failed to connect to voice channel: {e}")
                raise commands.CommandError(f"Failed to connect: {str(e)}")

    @commands.hybrid_command(name="leave", aliases=["disconnect"], with_app_command=True)
    async def leave(self, ctx: BoultContext) -> None:
        """Disconnect from the current voice channel with proper cleanup."""
        if ctx.interaction:
            await ctx.defer()

        async with await self._acquire_voice_lock(ctx.guild.id):
            voice_state = await self._get_voice_state(ctx.guild.id)
            
            if not voice_state:
                embed = discord.Embed(
                    color=self.bot.config.color.color,
                    timestamp=datetime.now(timezone.utc)
                ).set_author(
                    name="Not connected to any voice channel",
                    icon_url=self.bot.user.display_avatar.url
                )
                return await ctx.send(embed=embed)

            try:
                await voice_state.disconnect(force=True)
                self._voice_states.pop(ctx.guild.id, None)
                
                embed = discord.Embed(
                    color=self.bot.config.color.color,
                    timestamp=datetime.now(timezone.utc)
                ).set_author(
                    name="Successfully disconnected",
                    icon_url=self.bot.user.display_avatar.url
                )
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Failed to disconnect from voice channel: {e}")
                raise commands.VoiceError(f"Failed to disconnect: {str(e)}")

    @commands.hybrid_group(name="config", with_app_command=True)
    async def _config(self, ctx: BoultContext) -> None:
        """Advanced configuration management interface."""
        if ctx.interaction:
            await ctx.defer()

        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @_config.command(name="prefix", with_app_command=True)
    @commands.has_permissions(administrator=True)
    async def prefix(self, ctx: BoultContext, prefix: Optional[str] = None) -> None:
        """
        Configure the bot's command prefix for this guild.
        
        Parameters
        -----------
        prefix: Optional[str]
            The new prefix to set. If None, displays current prefix.
        """
        if ctx.interaction:
            await ctx.defer()

        if prefix is None:
            embed = discord.Embed(
                description=f"Current prefix: `{self.bot.config.bot.default_prefix}`",
                color=self.bot.config.color.color,
                timestamp=datetime.now(timezone.utc)
            )
            return await ctx.send(embed=embed)

        try:
            await self.bot.db.execute(
                "UPDATE guild_config SET prefix = $1 WHERE guild_id = $2",
                prefix,
                ctx.guild.id
            )
            embed = discord.Embed(
                description=f"Successfully updated prefix to `{prefix}`",
                color=self.bot.config.color.color,
                timestamp=datetime.now(timezone.utc)
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to update prefix: {e}")
            raise commands.CommandError(f"Failed to update prefix: {str(e)}")

    @_config.group(name="247", with_app_command=True, invoke_without_command=True)
    async def _247(self, ctx: BoultContext) -> None:
        """24/7 voice presence configuration interface."""
        embed = discord.Embed(
            description="Please use `/247 enable` or `/247 disable` to manage 24/7 mode.",
            color=self.bot.config.color.color,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)

    @_247.command(name="enable")
    async def _enable(self, ctx: BoultContext) -> None:
        """Enable 24/7 voice presence mode."""
        if ctx.interaction:
            await ctx.defer()

        async with await self._acquire_voice_lock(ctx.guild.id):
            try:
                data = await self.bot.db.fetch_one(
                    "SELECT vc_channel FROM guild_config WHERE guild_id = $1",
                    ctx.guild.id
                )

                if data is None:
                    await self.bot.db.execute(
                        "INSERT INTO guild_config (guild_id, prefix, vc_channel) VALUES ($1, $2, $3)",
                        ctx.guild.id,
                        self.bot.config.bot.default_prefix,
                        0
                    )

                voice_state = await self._get_voice_state(ctx.guild.id)
                if not voice_state:
                    embed = discord.Embed(
                        color=self.bot.config.color.color
                    ).set_author(
                        name="Not connected to any voice channel",
                        icon_url=self.bot.user.display_avatar.url
                    )
                    return await ctx.send(embed=embed)

                channel_id = ctx.voice_client.channel.id
                await self.bot.db.execute(
                    "UPDATE guild_config SET vc_channel = $1 WHERE guild_id = $2",
                    channel_id,
                    ctx.guild.id
                )

                embed = discord.Embed(
                    description=f"24/7 mode enabled in <#{channel_id}>",
                    color=self.bot.config.color.color,
                    timestamp=datetime.now(timezone.utc)
                )
                await ctx.send(embed=embed)

            except Exception as e:
                logger.error(f"Failed to enable 24/7 mode: {e}")
                raise commands.CommandError(f"Failed to enable 24/7 mode: {str(e)}")

    @_247.command(name="disable")
    async def _disable(self, ctx: BoultContext) -> None:
        """Disable 24/7 voice presence mode."""
        if ctx.interaction:
            await ctx.defer()

        try:
            data = await self.bot.db.fetch_one(
                "SELECT vc_channel FROM guild_config WHERE guild_id = $1",
                ctx.guild.id
            )

            if data is None or data.vc_channel == 0:
                embed = discord.Embed(
                    color=self.bot.config.color.color
                ).set_author(
                    name="24/7 mode is not currently enabled",
                    icon_url=self.bot.user.display_avatar.url
                )
                return await ctx.send(embed=embed)

            await self.bot.db.execute(
                "UPDATE guild_config SET vc_channel = $1 WHERE guild_id = $2",
                0,
                ctx.guild.id
            )

            embed = discord.Embed(
                description="24/7 mode has been disabled",
                color=self.bot.config.color.color,
                timestamp=datetime.now(timezone.utc)
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Failed to disable 24/7 mode: {e}")
            raise commands.CommandError(f"Failed to disable 24/7 mode: {str(e)}")

    @_config.command(name="search", with_app_command=True)
    async def _search(
        self,
        ctx: BoultContext,
        search_engine: Literal[
            "spotify", "youtube", "soundcloud", "youtube-music", "jiosaavn", "none"
        ]
    ) -> None:
        """
        Configure preferred music search engine.
        
        Parameters
        -----------
        search_engine: str
            The search engine to use for music queries
        """
        if ctx.interaction:
            await ctx.defer()

        try:
            user_config = await self.bot.db.fetch_one(
                "SELECT * FROM user_config WHERE user_id=$1",
                ctx.author.id
            )

            search_value = None if search_engine == "none" else self.config.search_engines.get(search_engine)

            if search_engine == "none":
                if user_config:
                    await self.bot.db.execute(
                        "UPDATE user_config SET search_engine = $1 WHERE user_id = $2",
                        None,
                        ctx.author.id
                    )
                embed = discord.Embed(
                    description="Search engine preference cleared. You will be prompted to choose each time.",
                    color=self.bot.config.color.color,
                    timestamp=datetime.now(timezone.utc)
                )
                return await ctx.send(embed=embed)

            if user_config is None:
                await self.bot.db.execute(
                    "INSERT INTO user_config (user_id, search_engine) VALUES ($1, $2)",
                    ctx.author.id,
                    search_value
                )
            else:
                await self.bot.db.execute(
                    "UPDATE user_config SET search_engine = $1 WHERE user_id = $2",
                    search_value,
                    ctx.author.id
                )

            embed = discord.Embed(
                color=self.bot.config.color.color,
                timestamp=datetime.now(timezone.utc)
            ).set_author(
                name=f"Search engine preference set to {search_engine}",
                icon_url=self.bot.user.display_avatar.url
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Failed to update search engine preference: {e}")
            raise commands.CommandError(f"Failed to update search engine: {str(e)}")

    @_config.group(name="noprefix", aliases=["np"], hidden=True)
    @commands.is_owner()
    async def _noprefix(self, ctx: BoultContext) -> None:
        """Administrative interface for managing no-prefix users."""
        pass

    @_noprefix.command(name="add", aliases=["a"], hidden=True)
    @commands.is_owner()
    async def _add(self, ctx: BoultContext, user: discord.User) -> None:
        """
        Grant no-prefix privileges to a user.
        
        Parameters
        -----------
        user: discord.User
            The user to grant no-prefix privileges to
        """
        try:
            user_config = await self.bot.db.fetch_one(
                "SELECT no_prefix FROM user_config WHERE user_id=$1",
                user.id
            )

            if user_config is None:
                await self.bot.db.execute(
                    "INSERT INTO user_config (user_id, no_prefix) VALUES ($1, $2)",
                    user.id,
                    True
                )
            else:
                await self.bot.db.execute(
                    "UPDATE user_config SET no_prefix = $1 WHERE user_id = $2",
                    True,
                    user.id
                )

            embed = discord.Embed(
                color=self.bot.config.color.color,
                timestamp=datetime.now(timezone.utc)
            ).set_author(
                name=f"Granted no-prefix privileges to {user}",
                icon_url=self.bot.user.display_avatar.url
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Failed to add no-prefix user: {e}")
            raise commands.CommandError(f"Failed to update privileges: {str(e)}")

    @_noprefix.command(name="remove", aliases=["r"], hidden=True)
    @commands.is_owner()
    async def _remove(self, ctx: BoultContext, user: discord.User) -> None:
        """
        Revoke no-prefix privileges from a user.
        
        Parameters
        -----------
        user: discord.User
            The user to revoke no-prefix privileges from
        """
        try:
            user_config = await self.bot.db.fetch_one(
                "SELECT no_prefix FROM user_config WHERE user_id=$1",
                user.id
            )

            if user_config is None:
                await self.bot.db.execute(
                    "INSERT INTO user_config (user_id, no_prefix) VALUES ($1, $2)",
                    user.id,
                    False
                )
            else:
                await self.bot.db.execute(
                    "UPDATE user_config SET no_prefix = $1 WHERE user_id = $2",
                    False,
                    user.id
                )

            embed = discord.Embed(
                color=self.bot.config.color.color,
                timestamp=datetime.now(timezone.utc)
            ).set_author(
                name=f"Revoked no-prefix privileges from {user}",
                icon_url=self.bot.user.display_avatar.url
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Failed to remove no-prefix user: {e}")
            raise commands.CommandError(f"Failed to update privileges: {str(e)}")
