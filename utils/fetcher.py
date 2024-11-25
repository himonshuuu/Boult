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



from typing import Optional, Union, TYPE_CHECKING
import discord
from discord.ext import commands

if TYPE_CHECKING:
    from core import Boult  # Only imported during type checking

class EntityFetcher:
    """Utility class for fetching Discord entities with caching."""
    
    def __init__(self, bot: "Boult"):  # Use string literal type hint
        self.bot: "Boult" = bot

    async def get_or_fetch_guild(self, guild_id: int) -> Optional[discord.Guild]:
        """Looks up a guild in cache or fetches if not found.
        
        Parameters
        -----------
        guild_id: int
            The guild ID to search for.
            
        Returns
        ---------
        Optional[Guild]
            The guild or None if not found.
        """
        guild = self.bot.get_guild(guild_id)
        if guild is not None:
            return guild

        try:
            guild = await self.bot.fetch_guild(guild_id)
            return guild
        except discord.HTTPException:
            return None

    async def get_or_fetch_member(
        self, guild: discord.Guild, member_id: int
    ) -> Optional[discord.Member]:
        """Looks up a member in cache or fetches if not found.
        
        Parameters
        -----------
        guild: Guild
            The guild to look in.
        member_id: int
            The member ID to search for.
            
        Returns
        ---------
        Optional[Member]
            The member or None if not found.
        """
        member = guild.get_member(member_id)
        if member is not None:
            return member

        shard: discord.ShardInfo = self.bot.get_shard(guild.shard_id)  # type: ignore
        if shard.is_ws_ratelimited():
            try:
                member = await guild.fetch_member(member_id)
            except discord.HTTPException:
                return None
            else:
                return member

        members = await guild.query_members(limit=1, user_ids=[member_id], cache=True)
        if not members:
            return None
        return members[0]

    async def get_or_fetch_channel(
        self, 
        channel_id: int, 
        guild: Optional[discord.Guild] = None
    ) -> Optional[Union[discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel, discord.Thread]]:
        """Looks up a channel in cache or fetches if not found.
        
        Parameters
        -----------
        channel_id: int
            The channel ID to search for.
        guild: Optional[Guild]
            The guild to look in (optional, for optimization).
            
        Returns
        ---------
        Optional[Union[TextChannel, VoiceChannel, CategoryChannel, Thread]]
            The channel or None if not found.
        """
        # Check cache first
        channel = self.bot.get_channel(channel_id)
        if channel is not None:
            return channel

        # If guild is provided, check guild channels
        if guild is not None:
            channel = guild.get_channel(channel_id)
            if channel is not None:
                return channel

        # Fetch from API
        try:
            channel = await self.bot.fetch_channel(channel_id)
            return channel
        except discord.HTTPException:
            return None

    async def get_or_fetch_text_channel(
        self, channel_id: int, guild: Optional[discord.Guild] = None
    ) -> Optional[discord.TextChannel]:
        """Specifically fetch a text channel."""
        channel = await self.get_or_fetch_channel(channel_id, guild)
        return channel if isinstance(channel, discord.TextChannel) else None

    async def get_or_fetch_voice_channel(
        self, channel_id: int, guild: Optional[discord.Guild] = None
    ) -> Optional[discord.VoiceChannel]:
        """Specifically fetch a voice channel."""
        channel = await self.get_or_fetch_channel(channel_id, guild)
        return channel if isinstance(channel, discord.VoiceChannel) else None

    async def get_or_fetch_thread(
        self, thread_id: int, guild: Optional[discord.Guild] = None
    ) -> Optional[discord.Thread]:
        """Specifically fetch a thread."""
        channel = await self.get_or_fetch_channel(thread_id, guild)
        return channel if isinstance(channel, discord.Thread) else None

    async def get_or_fetch_message(
        self, 
        channel: Union[discord.TextChannel, discord.Thread, discord.DMChannel], 
        message_id: int
    ) -> Optional[discord.Message]:
        """Looks up a message in cache or fetches if not found.
        
        Parameters
        -----------
        channel: Union[TextChannel, Thread, DMChannel]
            The channel to look in.
        message_id: int
            The message ID to search for.
            
        Returns
        ---------
        Optional[Message]
            The message or None if not found.
        """
        try:
            # Try to get from cache first
            message = channel.get_partial_message(message_id)
            if message is not None:
                return message

            # Fetch if not in cache
            return await channel.fetch_message(message_id)
        except discord.HTTPException:
            return None

    async def get_or_fetch_user(self, user_id: int) -> Optional[discord.User]:
        """Looks up a user in cache or fetches if not found.
        
        Parameters
        -----------
        user_id: int
            The user ID to search for.
            
        Returns
        ---------
        Optional[User]
            The user or None if not found.
        """
        user = self.bot.get_user(user_id)
        if user is not None:
            return user

        try:
            user = await self.bot.fetch_user(user_id)
            return user
        except discord.HTTPException:
            return None
