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
import datetime
from typing import Dict, Optional, Set, Tuple
from collections import defaultdict

import discord
import wavelink
from wavelink import Playable

from core import Boult, Cog, Player
from utils.format import format_duration
from utils.friendlytime import format_relative
from .view import MusicView, ErrorView
from utils import TimedTask
from utils.cache import CacheManager

class PlayerState:
    def __init__(self):
        self.last_position: float = 0
        self.last_update: datetime.datetime = datetime.datetime.now()
        self.pause_duration: float = 0
        self.total_played: float = 0

class MusicEvents(Cog):
    def __init__(self, bot: Boult):
        super().__init__(bot)
        self._tasks: Dict[int, TimedTask] = {}
        self._track_states: Dict[int, Dict[str, PlayerState]] = defaultdict(dict)
        self._updated_tracks: Set[Tuple[int, str]] = set()
        self._cache = CacheManager(max_size=1000, ttl=3600)
        self._lock = asyncio.Lock()

    async def _safe_message_delete(self, message: Optional[discord.Message], delay: float = 0) -> None:
        """Enhanced message deletion with retry logic and error handling."""
        if not message:
            return

        async def delete_attempt():
            try:
                await asyncio.sleep(delay)
                await message.delete()
            except discord.NotFound:
                pass
            except discord.Forbidden:
                self.bot.logger.warning(f"Missing permissions to delete message in {message.channel.id}")
            except Exception as e:
                self.bot.logger.error(f"Failed to delete message: {str(e)}", exc_info=True)

        asyncio.create_task(delete_attempt())

    @Cog.listener("on_wavelink_track_exception") 
    async def on_track_exception(self, payload: wavelink.TrackExceptionEventPayload):
        player: Player = payload.player
        error_view = ErrorView(self.bot)
        await self.handle_error_message(
            player,
            "An error occurred while playing the track. Please try another song.",
            view=error_view
        )
        if hasattr(player, 'message'):
            await self._safe_message_delete(player.message)

    @Cog.listener("on_wavelink_track_start")
    async def on_track_start(self, payload: wavelink.TrackStartEventPayload):
        player: Player = payload.player
        channel: discord.TextChannel = player.home
        track: Playable = payload.track

        async with self._lock:
            # Initialize track state
            state = PlayerState()
            self._track_states[player.guild.id][track.identifier] = state

            # Handle requester logic with caching
            requester_key = f"requester_{track.extras.requester}"
            requester = await self._cache.get(
                requester_key,
                lambda: self.bot.fetch_user(track.extras.requester) if not player.autoplay == wavelink.AutoPlayMode.enabled else self.bot.user
            )
            requester_name = requester.name if requester else "@Unknown"

            try:
                spotify_track = None
                if track.source == "spotify":
                    spotify_track = await self._cache.get(
                        f"spotify_{track.identifier}",
                        lambda: self.bot.spotify.get_track(track.identifier)
                    )

                artists = []
                if spotify_track and spotify_track.artists:
                    artists = [f"[{a.entity.name}]({a.entity.url})" for a in spotify_track.artists]
                else:
                    artists = [f"[{track.author}]"]

                # Rich embed construction
                embed = discord.Embed(
                    color=self.bot.color,
                    description=f"> [{track.title}]({track.uri})\n> -# {', '.join(artists)}",
                    timestamp=datetime.datetime.now()
                )
                embed.set_author(name="Now playing", icon_url=self.bot.user.display_avatar.url)
                embed.set_thumbnail(url=track.artwork)
                embed.set_footer(
                    text=f"Added by {requester_name} | {format_duration(track.length)}", 
                    icon_url=requester.display_avatar.url
                )
                content = None
                if player.queue and not player.queue.is_empty:
                    next_track = player.queue[0]
                    content = f"-# Next: [{next_track.title}]({next_track.uri})"
                
                view = MusicView(self.bot, player)

                if player.autoplay == wavelink.AutoPlayMode.enabled:
                    view.remove_item(view.next)
                    content = "-# </autoplay:1310295138052079645> to disable"

                player.message = await channel.send(embed=embed, view=view, content=content)
                player.start_time = datetime.datetime.now()

                await self.update_channel_status(player, f"{track.title} - {track.author}")

                player.current_track_info = {
                    "user_id": requester.id if requester else 0,
                    "track_id": track.identifier,
                    "start_time": datetime.datetime.now().isoformat()
                }

            except Exception as e:
                self.bot.logger.error(f"Error in track_start: {str(e)}", exc_info=True)
                await self.handle_error_message(player, "An error occurred while starting the track.")

    @Cog.listener("on_wavelink_player_update")
    async def on_player_update(self, payload: wavelink.PlayerUpdateEventPayload):
        player: Player = payload.player
        if not player or not player.connected or not player.current:
            return

        track = player.current
        track_key = (player.guild.id, track.identifier)
        
        if track_key in self._updated_tracks:
            return

        self._updated_tracks.add(track_key)
        try:
            status = f"{'▶️' if player.paused else ''} {track.title} - {track.author}"
            await self.update_channel_status(player, status)
            
            # Update track state
            if track.identifier in self._track_states[player.guild.id]:
                state = self._track_states[player.guild.id][track.identifier]
                current_time = datetime.datetime.now()
                if player.paused:
                    state.pause_duration += (current_time - state.last_update).total_seconds()
                else:
                    state.total_played += (current_time - state.last_update).total_seconds()
                state.last_update = current_time
                state.last_position = payload.position

        except Exception as e:
            self.bot.logger.error(f"Error in player_update: {str(e)}", exc_info=True)

    @Cog.listener("on_wavelink_track_end")
    async def on_track_end(self, payload: wavelink.TrackEndEventPayload):
        player: Player = payload.player

        try:
            if player.autoplay == wavelink.AutoPlayMode.enabled:
                if not player.queue.is_empty:
                    next_track = player.queue.get()
                    await player.play(next_track)
                    return
                return

            await self.cleanup_player(player)

            if player.queue.is_empty:
                await self.handle_queue_end(player)

        except Exception as e:
            self.bot.logger.error(f"Error in track_end: {str(e)}", exc_info=True)
            await self.handle_error_message(player, "An error occurred while ending the track.")

    async def handle_queue_end(self, player: Player):
        """Enhanced queue end handling with configurable behavior."""
        if not player.queue.is_empty:
            return

        try:
            async with self.bot.db.acquire() as conn:
                vc_config = await conn.fetchrow(
                    """
                    SELECT vc_channel
                    FROM guild_config 
                    WHERE guild_id = $1
                    """,
                    player.guild.id
                )

            if not vc_config or vc_config.vc_channel == 0:
                if not player.playing:
                    disconnect_timeout =  30
                    
                    task = TimedTask(wait=disconnect_timeout)
                    self._tasks[player.guild.id] = task
                    task.start_task(self.safe_disconnect, player=player)

                    timeout_delta = datetime.timedelta(seconds=disconnect_timeout)
                    disconnect_time = datetime.datetime.now() + timeout_delta
                    
                    embed = discord.Embed(
                        color=self.bot.color,
                        description=f"Leaving the voice channel in {format_relative(disconnect_time)}."
                    )
                    embed.set_author(name="Queue is empty", icon_url=self.bot.user.display_avatar.url)
                    embed.add_field(
                        name="Stay Connected", 
                        value="Run </config 247 enable:1309110309025484822> to prevent automatic disconnection"
                    )
                    
                    await player.home.send(
                        content="-# Configure 24/7 mode to prevent disconnection",
                        embed=embed,
                        delete_after=disconnect_timeout
                    )

                    await self.update_channel_status(player, "Boult Music")
                    return

            if not player.playing:
                embed = discord.Embed(color=self.bot.color)
                embed.set_author(name="Queue is empty", icon_url=self.bot.user.display_avatar.url)
                embed.add_field(
                    name="Add Music", 
                    value="Use </play:1310295137586384989> to add more songs"
                )
                
                await player.home.send(
                    embed=embed
                )
                return await self.update_channel_status(player, "Boult Music")

        except Exception as e:
            self.bot.logger.error(f"Error in handle_queue_end: {str(e)}", exc_info=True)
            await self.handle_error_message(player, "An error occurred while handling queue end.")

    async def safe_disconnect(self, player: Player):
        """Enhanced safe disconnection with cleanup."""
        try:
            if player and player.connected:
                # Cleanup before disconnection
                self._track_states.pop(player.guild.id, None)
                self._tasks.pop(player.guild.id, None)
                self._updated_tracks = {k for k in self._updated_tracks if k[0] != player.guild.id}
                
                await player.disconnect(force=True)
                self.bot.logger.info(f"Successfully disconnected player in guild {player.guild.id}")
        except Exception as e:
            self.bot.logger.error(f"Error in safe_disconnect: {str(e)}", exc_info=True)

    async def update_channel_status(self, player: Player, status: str):
        """Update voice channel status with rate limiting and error handling."""
        try:
            await player.channel.edit(status=status)
        except discord.Forbidden:
            self.bot.logger.warning(f"Missing permissions to update channel status in {player.guild.id}")
        except discord.HTTPException as e:
            self.bot.logger.error(f"HTTP error updating channel status: {str(e)}")
        except Exception as e:
            self.bot.logger.error(f"Unexpected error updating channel status: {str(e)}", exc_info=True)

    async def cleanup_player(self, player: Player):
        """Enhanced player cleanup with comprehensive state management."""
        try:
            # Cleanup message
            if hasattr(player, 'message'):
                await self._safe_message_delete(player.message)

            if player.guild.id in self._track_states and player.current:
                state = self._track_states[player.guild.id].get(player.current.identifier)
                if state:
                    self._track_states[player.guild.id].pop(player.current.identifier, None)
                    self._updated_tracks = {k for k in self._updated_tracks if k != (player.guild.id, player.current.identifier)}

        except Exception as e:
            self.bot.logger.error(f"Error in cleanup_player: {str(e)}", exc_info=True)
            await self.handle_error_message(player, "An error occurred during player cleanup.", view=None)

    async def handle_error_message(self, player: Player, message: str, view: Optional[discord.ui.View] = None):
        """Enhanced error message handling with optional view and logging."""
        try:
            embed = discord.Embed(
                color=self.bot.color,
                description=message,
                timestamp=datetime.datetime.now()
            )
            embed.set_author(name="Error", icon_url=self.bot.user.display_avatar.url)
            
            await player.home.send(embed=embed, view=view)
            self.bot.logger.error(f"Music player error in guild {player.guild.id}: {message}")
        except Exception as e:
            self.bot.logger.error(f"Failed to send error message: {str(e)}", exc_info=True)
