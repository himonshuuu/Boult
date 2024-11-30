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



import discord
from typing import Optional
import asyncio
import wavelink
import datetime
from core import Boult, Cog, Player
from wavelink import Playable

from utils.format import format_duration
from utils.friendlytime import format_relative
from .view import MusicView
from utils import TimedTask


class MusicEvents(Cog):
    def __init__(self, bot: Boult):
        self.bot = bot
        self.tasks = {}
        self.updated_tracks = {}

    async def delete_message(self, message: Optional[discord.Message], delay: int = 0):
        """Deletes a message with an optional delay."""
        if message:
            try:
                await asyncio.sleep(delay)
                await message.delete()
            except discord.HTTPException:
                pass

    @Cog.listener("on_wavelink_track_exception")
    async def on_track_exception(self, payload: wavelink.TrackExceptionEventPayload):
        player: Player = payload.player
        await self.handle_error_message(
            player, "An error occurred while playing the track. Please try another song."
        )
        await self.delete_message(player.message)

    @Cog.listener("on_wavelink_track_start")
    async def on_track_start(self, payload: wavelink.TrackStartEventPayload):
        player: Player = payload.player
        channel: discord.TextChannel = player.home
        track: Playable = payload.track
        if player.autoplay == wavelink.AutoPlayMode.enabled:
            requester = self.bot.user
            requester_name = requester.name if requester else "@Unknown"
        else:
            requester = await self.bot.fetch_user(track.extras.requester)
            requester_name = requester.name if requester else "@Unknown"

        spotify_track = (
            await self.bot.spotify.get_track(track.identifier)
            if track.source == "spotify"
            else None
        )
        artists = (
            [f"[{a.entity.name}]({a.entity.url})" for a in spotify_track.artists]
            if spotify_track
            else [f"[{track.author}]"]
        )

        embed = discord.Embed(
            color=self.bot.color,
            description=f"> [{track.title}]({track.uri})\n> -# {', '.join(artists)}",
        )
        embed.set_author(name="Now playing", icon_url=self.bot.user.display_avatar.url)
        embed.set_thumbnail(url=track.artwork)
        embed.set_footer(text=f"Added by {requester_name} | {format_duration(track.length)}", icon_url=requester.display_avatar.url)


        view = MusicView(self.bot, player)

        content = None
        if player.autoplay == wavelink.AutoPlayMode.enabled:
            view.remove_item(view.next)
            content = "-# </autoplay:1310295138052079645> to disable"

        player.message = await channel.send(embed=embed, view=view, content=content if content else None, delete_after=(player.current.length / 1000) + 5)
        player.start_time = datetime.datetime.now()

        await self.update_channel_status(player, f"{track.title} - {track.author}")

        # Update play data in the database
        await self.bot.db.execute(
            """
            INSERT INTO user_play_data (user_id, track_id, plays, duration) 
            VALUES ($1, $2, 1, 0) 
            ON CONFLICT (user_id, track_id) DO UPDATE 
            SET plays = user_play_data.plays + 1
            """,
            requester.id if requester else 0,
            track.identifier,
        )
        player.current_track_info = {"user_id": requester.id if requester else 0, "track_id": track.identifier}

    @Cog.listener("on_wavelink_player_update")
    async def on_player_update(self, payload: wavelink.PlayerUpdateEventPayload):
        player: Player = payload.player
        if not player or not player.connected or not player.current:
            return

        track = player.current
        if self.updated_tracks.get(player.guild.id) == track.identifier:
            return

        self.updated_tracks[player.guild.id] = track.identifier
        if player.paused:
            await self.update_channel_status(player, f"▶️ {track.title} - {track.author}")
        else:
            await self.update_channel_status(player, f"{track.title} - {track.author}")

    @Cog.listener("on_wavelink_track_end")
    async def on_track_end(self, payload: wavelink.TrackEndEventPayload):
        player: Player = payload.player

        if player.autoplay == wavelink.AutoPlayMode.enabled:
            if not player.queue.is_empty:
                await player.play(player.queue.get())
                return
            return

        await self.cleanup_player(player)

        if player.queue.is_empty:
            await self.handle_queue_end(player)

    async def handle_queue_end(self, player: Player):
        """Handle the end of the queue."""
        if player.queue.is_empty:
            vc_channel = await self.bot.db.fetch_one(
                """
                SELECT vc_channel FROM guild_config WHERE guild_id = $1
                """,
                player.guild.id,
            )
            if not vc_channel or vc_channel.vc_channel == 0:
                if not player.playing:
                    task = TimedTask(wait=30)
                    self.tasks[player.guild.id] = task
                    task.start_task(self.safe_disconnect, player=player)

                    thirty_second = datetime.timedelta(seconds=30)
                    now = datetime.datetime.now() 
                    timestamp = now + thirty_second
                    await player.home.send(
                        content="-# run </config 247 enable:1309110309025484822> to prevent this",
                        embed=discord.Embed(
                            color=self.bot.color,
                            description=f"Leaving the voice channel in {format_relative(timestamp)}.",
                        ).set_author(name="Queue is empty", icon_url=self.bot.user.display_avatar.url), delete_after=30
                    )

                    await self.update_channel_status(player, "Boult Music")

                    return
                
            if not player.playing:
                await player.home.send(
                    content="-# </play:1310295137586384989> to add more songs",
                    embed=discord.Embed(
                        color=self.bot.color
                    ).set_author(name="Queue is empty", icon_url=self.bot.user.display_avatar.url)
                )
                return await self.update_channel_status(player, "Boult Music")


    async def safe_disconnect(self, player: Player):
        """Safely disconnect the player."""
        if player and player.connected:
            await player.disconnect(force=True)

    async def update_channel_status(self, player: Player, status: str):
        """Update the status of the channel."""
        try:
            await player.channel.edit(status=status)
        except Exception:
            pass

    async def cleanup_player(self, player: Player):
        """Cleanup player data and messages."""
        played_duration = (datetime.datetime.now() - player.start_time).total_seconds()
        track_info = player.current_track_info or {}
        user_id = track_info.get("user_id", 0)
        track_id = track_info.get("track_id", "")

        try :
            if player.message:
                await self.delete_message(player.message)
        except Exception:
            pass


        await self.bot.db.execute(
            """
            UPDATE user_play_data
            SET duration = duration + $1
            WHERE user_id = $2 AND track_id = $3
            """,
            played_duration,
            user_id,
            track_id,
        )

        self.updated_tracks.pop(player.guild.id, None)

    async def handle_error_message(self, player: Player, message: str):
        """Send an error message to the player home channel."""
        await player.home.send(
            embed=discord.Embed(color=self.bot.color, description=message).set_author(
                name="Error",
                icon_url=self.bot.user.display_avatar.url,
            )
        )

