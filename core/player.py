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
from datetime import datetime, timedelta
from typing import Dict, List, Set, Union

import discord
import wavelink
from discord.ext import tasks

from extensions.context.context import BoultContext
from utils.cache import CacheManager

logger = logging.getLogger(__name__)

class PlayerState:
    """Encapsulates player state data"""
    def __init__(self):
        self.skip_votes: Dict[int, Set[int]] = {}
        self.previous_votes: Dict[int, Set[int]] = {}
        self.vote_expiry: Dict[str, datetime] = {}
        self.vote_locks: Dict[str, asyncio.Lock] = {}
        self._cache = CacheManager(max_size=100, ttl=3600)

class Player(wavelink.Player):
    """
    Enhanced wavelink.Player with advanced functionality for music playback control.
    Implements complex voting systems, caching, and state management.
    """

    ctx: BoultContext
    home: Union[discord.TextChannel, discord.VoiceChannel, discord.Thread]
    message: discord.Message
    start_time: datetime
    last_update: datetime

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._state = PlayerState()
        self._vote_cleanup.start()
        self._track_history: List[wavelink.Playable] = []
        self._max_history = 50
        logger.info(f"Initialized player for guild {self.channel.guild.id}")

    @tasks.loop(minutes=5.0)
    async def _vote_cleanup(self):
        """Cleanup expired votes periodically"""
        now = datetime.now()
        for vote_type, expiry in self._state.vote_expiry.copy().items():
            if now > expiry:
                guild_id = int(vote_type.split('_')[1])
                if 'skip' in vote_type:
                    self._state.skip_votes.pop(guild_id, None)
                else:
                    self._state.previous_votes.pop(guild_id, None)
                self._state.vote_expiry.pop(vote_type)

    async def is_privileged(self, user: Union[discord.Member, discord.User]) -> bool:
        """Check if user has privileged access"""
        if not isinstance(user, discord.Member):
            return False
            
        return any([
            user.guild_permissions.administrator,
            user.guild_permissions.ban_members,
            user.guild_permissions.manage_messages,
            user.guild_permissions.manage_channels,
            user.id == self.current.extras.requester,
            await self.is_dj()
        ])

    async def is_dj(self) -> bool:
        """Verify DJ role status through context"""
        return await self.ctx.is_dj()

    async def destroy(self) -> None:
        """Cleanup player resources and state"""
        try:
            self._vote_cleanup.cancel()
            self.queue.clear()
            await self.stop()
            self._state = PlayerState()
            self._track_history.clear()
            self.start_time = None

            embed = discord.Embed(
                color=self.ctx.bot.config.color.color,
                description="Player resources cleaned up and destroyed"
            ).set_author(name="Player Stopped", icon_url=self.ctx.bot.user.display_avatar.url)
            
            await self.home.send(embed=embed, delete_after=15)
            logger.info(f"Player destroyed for guild {self.guild.id}")
            
        except Exception as e:
            logger.error(f"Error destroying player: {e}")
            raise

    async def handle_vote(
        self,
        ctx: Union[BoultContext, discord.Interaction],
        vote_type: str,
        action: str,
        required_votes: int
    ) -> bool:
        """
        Generic vote handler with rate limiting and synchronization
        
        Args:
            ctx: Command context or interaction
            vote_type: Type of vote (skip/previous)
            action: Description of vote action
            required_votes: Number of votes needed
            
        Returns:
            bool: Whether vote threshold was met
        """
        guild_id = ctx.guild.id
        user_id = ctx.user.id if isinstance(ctx, discord.Interaction) else ctx.author.id
        vote_key = f"{vote_type}_{guild_id}"

        async with self._state.vote_locks.setdefault(vote_key, asyncio.Lock()):
            votes = getattr(self._state, f"{vote_type}_votes")
            if guild_id not in votes:
                votes[guild_id] = set()

            if user_id in votes[guild_id]:
                embed = discord.Embed().set_author(
                    name=f"Already voted to {action}",
                    icon_url=self.ctx.bot.user.display_avatar.url
                )
                await self._send_response(ctx, embed)
                return False

            votes[guild_id].add(user_id)
            self._state.vote_expiry[vote_key] = datetime.now() + timedelta(minutes=5)

            total_votes = len(votes[guild_id])
            
            embed = discord.Embed().set_author(
                name=f"Vote to {action}: {total_votes}/{required_votes} required",
                icon_url=self.ctx.bot.user.display_avatar.url
            )
            await self._send_response(ctx, embed)

            return total_votes >= required_votes

    async def next(self, ctx: Union[BoultContext, discord.Interaction]) -> None:
        """Handle skip requests with voting"""
        if self.queue.is_empty:
            embed = discord.Embed().set_author(
                name="Queue empty",
                icon_url=self.ctx.bot.user.display_avatar.url
            )
            content = "-# </play:1310295137586384989> to add more songs"
            await self._send_response(ctx, embed, content=content, ephemeral=True)
            return

        if await self.is_privileged(ctx.user if isinstance(ctx, discord.Interaction) else ctx.author):
            await self._execute_skip()
            return

        required_votes = len([m for m in self.channel.members if not m.bot])
        if await self.handle_vote(ctx, "skip", "skip", required_votes):
            await self._execute_skip()
            self._state.skip_votes.pop(ctx.guild.id, None)

    async def previous(self, ctx: Union[BoultContext, discord.Interaction]) -> None:
        """Handle previous track requests with voting"""
        if not self.current or self.queue.history.is_empty:
            status = "No track is playing" if not self.current else "No previous tracks"
            embed = discord.Embed().set_author(
                name=status,
                icon_url=self.ctx.bot.user.display_avatar.url
            )
            await self._send_response(ctx, embed)
            return

        if await self.is_privileged(ctx.user if isinstance(ctx, discord.Interaction) else ctx.author):
            await self._execute_previous()
            return

        required_votes = len([m for m in self.channel.members if not m.bot])
        if await self.handle_vote(ctx, "previous", "play previous", required_votes):
            await self._execute_previous()
            self._state.previous_votes.pop(ctx.guild.id, None)

    async def _execute_skip(self) -> None:
        """Execute skip operation and send notification"""
        track_info = f"> [{self.current.title}]({self.current.uri}) - {self.current.author}"
        embed = discord.Embed(
            color=self.ctx.bot.config.color.color,
            description=track_info
        ).set_footer(
            text=f"{len(self.queue._items) - 1} tracks in queue"
        ).set_author(
            name="Skipped track",
            icon_url=self.ctx.bot.user.display_avatar.url
        )
        await self.home.send(embed=embed, delete_after=15)
        await self.stop()

    async def _execute_previous(self) -> None:
        """Execute previous track operation and send notification"""
        track = self.queue.history.get()
        await self.play(track)
        
        track_info = f"> [{self.current.title}]({self.current.uri}) - {self.current.author}"
        embed = discord.Embed(
            color=self.ctx.bot.config.color.color,
            description=track_info
        ).set_footer(
            text=f"{len(self.queue._items)} tracks in queue"
        ).set_author(
            name="Playing previous track",
            icon_url=self.ctx.bot.user.display_avatar.url
        )
        await self.home.send(embed=embed, delete_after=15)

    async def _send_response(
        self,
        ctx: Union[BoultContext, discord.Interaction],
        embed: discord.Embed,
        **kwargs
    ) -> None:
        """Unified response handler for both interactions and commands"""
        if isinstance(ctx, discord.Interaction):
            await ctx.response.send_message(embed=embed, **kwargs)
        else:
            await ctx.send(embed=embed, delete_after=30, **kwargs)
