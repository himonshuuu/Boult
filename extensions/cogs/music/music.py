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
import re
from typing import List, Optional

import discord
import wavelink
from discord import app_commands
from discord.ext import commands

from core import Boult, Cog, Player
from utils import (SimplePages, check_home, format_duration,
                   in_voice_channel, truncate_string, try_connect)

from extensions.context import BoultContext

from .view import (AutoPlayView, FilterView, LoopView, MusicView, SearchEngine,
                   SearchTrackSelect, TrackRemoveView, VolumeView)


class Music(Cog):
    """
    Music commands to play music.
    """
    def __init__(self, bot: Boult):
        super().__init__(bot)
        self.cache_manager = bot.cache_manager

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(id=1229721986674983043, name="playlist_avon")

    async def search_wavelink_track(self, query: str):
        # Try to get from cache first
        cache_key = f"wavelink_search:{query}"
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            return cached_result

        # If not in cache, do the search
        result = await wavelink.Playable.search(query, source="spsearch")

        # Cache the result for 1 hour
        await self.cache_manager.set(cache_key, result, expire=3600)
        return result

    async def query_autocomplete(
        self, interaction: discord.Interaction, query: str
    ) -> List[app_commands.Choice[str]]:
        cache_key = f"query_autocomplete:{query}"
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            return cached_result

        try:
            tracks = await wavelink.Playable.search(query, source="spsearch")
        except:
            default_choice = [
                app_commands.Choice(
                    name=f"Search Something or use url or query", value=""
                )
            ]
            await self.cache_manager.set(cache_key, default_choice, expire=300)
            return default_choice

        songs = [
            app_commands.Choice(
                name=f"{truncate_string(
                    value=f'{track.title} - {track.author}', max_length=100, suffix='')}",
                value=track.uri,
            )
            for track in tracks
        ]

        await self.cache_manager.set(cache_key, songs, expire=300)
        return songs

    @commands.command(name="playany", aliases=["playfromany", "plany"], hidden=True)
    @check_home(cls=Player)
    @in_voice_channel(user=True)
    @try_connect(cls=Player)
    async def play_from_any_source(self, ctx: BoultContext, *, query: str):
        if ctx.voice_client.channel != ctx.author.voice.channel:
            raise commands.CommandError(
                f"Join {ctx.voice_client.channel.mention} and try again.")

        if not hasattr(ctx.voice_client, "home"):
            ctx.voice_client.home = ctx.channel

        ctx.voice_client.autoplay = wavelink.AutoPlayMode.partial

        ctx.voice_client.ctx = ctx

        cache_key = f"playany:{query}"
        tracks = await self.cache_manager.get(cache_key)
        if not tracks:
            tracks = await wavelink.Playable.search(query)
            await self.cache_manager.set(cache_key, tracks, expire=1800)

        track = tracks[0]

        track.extras = wavelink.ExtrasNamespace({"requester": ctx.author.id})

        await ctx.voice_client.queue.put_wait(track)

        view = TrackRemoveView(self.bot, ctx.voice_client, [track])
        view.message = await ctx.send(
            embed=discord.Embed(
                description=f"> [{track.title}]({track.uri}) by [{track.author}]({
                    track.artist.url})"
            )
            .set_author(
                name="Enqueued track", icon_url=self.bot.user.display_avatar.url
            ),
            view=view if ctx.voice_client.playing else None,
        )

        if not ctx.voice_client.playing:
            await view.message.delete(delay=5)
            track = await ctx.voice_client.queue.get_wait()
            await ctx.voice_client.play(track)

    @commands.hybrid_command(name="play", with_app_command=True, aliases=["p", "pl"])
    @app_commands.autocomplete(query=query_autocomplete)
    @app_commands.describe(query="The song or playlist to play.")
    @check_home(cls=Player)
    @in_voice_channel(user=True)
    @try_connect(cls=Player)
    async def play(self, ctx: BoultContext, *, query: str):
        """Play a song from URL or query."""
        if ctx.interaction:
            await ctx.defer()

        if ctx.voice_client.channel != ctx.author.voice.channel:
            raise commands.CommandError(
                f"Join {ctx.voice_client.channel.mention} and try again.")

        ctx.voice_client.home = getattr(ctx.voice_client, "home", ctx.channel)
        ctx.voice_client.autoplay = wavelink.AutoPlayMode.partial
        ctx.voice_client.ctx = ctx

        source_handlers = {
            r"open\.spotify\.com": self._handle_spotify,
            r"(?:youtube\.com|youtu\.be)": self._handle_youtube,
            r"soundcloud\.com": self._handle_soundcloud,
            r"jiosaavn\.com": self._handle_jiosaavn
        }

        if user_id := next(
                (
                    int(match.group(1)) if match else int(query)
                    for pattern, match in {
                        r"<@!?(\d+)>": re.match(r"<@!?(\d+)>", query),
                        r"^\d+$": re.match(r"^\d+$", query)
                    }.items()
                    if match
                ),
            None
        ):
            await self._handle_user_activity(ctx, user_id=user_id)
            return

        for pattern, handler in source_handlers.items():
            if re.search(pattern, query, re.IGNORECASE):
                await handler(ctx, query)
                return

        await (
            self._handle_generic_url(ctx, query)
            if query.startswith(("http://", "https://"))
            else self._handle_search_query(ctx, query)
        )

        # except Exception as e:
        #     if not ctx.interaction:
        #         await ctx.message.add_reaction(ctx.tick(opt=False))

        #     error_msg = (
        #         f"An error occurred while processing your request: {str(e)}\n"
        #         f"Error type: {type(e).__name__}"
        #     )
        #     raise commands.CommandError(error_msg)

        if not ctx.interaction:
            await ctx.message.add_reaction(ctx.tick(opt=True))

    async def _handle_spotify(self, ctx: BoultContext, query: str):
        """Handle Spotify URLs with complex error handling and retry logic"""
        cache_key = f"spotify:{query}"
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            if isinstance(cached_result, wavelink.Playable):
                await self._play_single_track(ctx, cached_result)
                return
            elif isinstance(cached_result, list):
                await self._play_playlist(ctx, cached_result[0], cached_result[1], cached_result[2], query)
                return

        try:
            if "/track/" in query:
                tracks = await wavelink.Playable.search(query)
                if not tracks:
                    raise commands.CommandError("No tracks found for Spotify track")
                await self.cache_manager.set(cache_key, tracks[0], expire=3600)
                await self._play_single_track(ctx, tracks[0])

            elif "/playlist/" in query:
                tracks = None
                playlist = None
                retry_count = 0
                max_retries = 3

                while retry_count < max_retries:
                    try:
                        tracks = await wavelink.Playable.search(query, source="spsearch")
                        playlist = await self.bot.spotify.get_playlist(query)
                        break
                    except Exception as e:
                        retry_count += 1
                        if retry_count == max_retries:
                            playlist = await self.bot.spotify.get_playlist(query)
                            tracks = []
                            for track in playlist.tracks:
                                try:
                                    track_result = await wavelink.Playable.search(track.entity.url)
                                    if track_result:
                                        tracks.append(track_result[0])
                                except Exception:
                                    continue
                            if not tracks:
                                raise commands.CommandError(
                                    "Failed to load any tracks from playlist")
                        await asyncio.sleep(1)

                await self.cache_manager.set(cache_key, [tracks, playlist.entity.name, playlist.artwork], expire=3600)
                await self._play_playlist(ctx, tracks, playlist.entity.name, playlist.artwork, query)

            elif "/album/" in query:
                tracks = await wavelink.Playable.search(query, source="spsearch")
                if not tracks or not tracks.tracks:
                    raise commands.CommandError("No tracks found for Spotify album")
                album = await self.bot.spotify.get_album(query)
                if len(tracks.tracks) != len(album.tracks):
                    loaded_tracks = []
                    for track in album.tracks:
                        try:
                            track_result = await wavelink.Playable.search(track.entity.url)
                            if track_result:
                                loaded_tracks.append(track_result[0])
                        except Exception:
                            continue
                    if loaded_tracks:
                        tracks.tracks = loaded_tracks
                    else:
                        raise commands.CommandError(
                            "Failed to load any tracks from album")
                await self.cache_manager.set(cache_key, [tracks.tracks, album.entity.name, album.artwork], expire=3600)
                await self._play_playlist(ctx, tracks.tracks, album.entity.name, album.artwork, query)

            elif "/artist/" in query:
                tracks = await wavelink.Playable.search(query, source="spsearch")
                if not tracks or not tracks.tracks:
                    raise commands.CommandError("No tracks found for Spotify artist")
                artist = await self.bot.spotify.get_artist(query)
                # Filter out any invalid tracks
                valid_tracks = [
                    t for t in tracks.tracks if hasattr(t, 'uri') and t.uri]
                if not valid_tracks:
                    raise commands.CommandError("No valid tracks found for artist")
                await self.cache_manager.set(cache_key, [valid_tracks, f"Top tracks by {artist.entity.name}", artist.artwork], expire=3600)
                await self._play_playlist(ctx, valid_tracks, f"Top tracks by {artist.entity.name}", artist.artwork, query)

        except Exception as e:
            error_msg = f"Failed to process Spotify URL: {str(e)}"
            if isinstance(e, wavelink.LavalinkLoadException):
                error_msg = "Failed to load track from Spotify - try again later"
            raise Exception(error_msg)

    async def _play_single_track(self, ctx: BoultContext, track: wavelink.Playable):
        """Play a single track with enhanced error handling"""
        if not track or not hasattr(track, 'uri'):
            raise commands.CommandError("Invalid track object")

        track.extras = wavelink.ExtrasNamespace({
            "requester": ctx.author.id,
            "timestamp": datetime.datetime.now().timestamp(),
            "source": track.source
        })

        try:
            await ctx.voice_client.queue.put_wait(track)

            embed = discord.Embed(
                description=f"> [{track.title}]({track.uri}) by {
                    track.author}",
                timestamp=datetime.datetime.now()
            ).set_author(
                name="Enqueued track",
                icon_url=self.bot.user.display_avatar.url
            )

            view = TrackRemoveView(self.bot, ctx.voice_client, [track])
            view.message = await ctx.send(
                embed=embed,
                view=view if ctx.voice_client.playing else None
            )

            if not ctx.voice_client.playing:
                next_track = await ctx.voice_client.queue.get_wait()
                await ctx.voice_client.play(next_track)
                if view.message:
                    await view.message.delete(delay=5)

        except Exception as e:
            await ctx.voice_client.queue.remove(track)
            raise Exception(f"Failed to play track: {str(e)}")

    async def _play_playlist(self, ctx: BoultContext, tracks, name, artwork, query):
        """Play a playlist with enhanced validation and error handling"""
        if not tracks:
            raise commands.CommandError("No tracks provided")

        valid_tracks = []
        for track in tracks:
            if not isinstance(track, wavelink.Playable):
                continue
            track.extras = wavelink.ExtrasNamespace({
                "requester": ctx.author.id,
                "playlist_name": name,
                "timestamp": datetime.datetime.now().timestamp()
            })
            valid_tracks.append(track)

        if not valid_tracks:
            raise commands.CommandError("No valid tracks found in playlist")

        try:
            await ctx.voice_client.queue.put_wait(valid_tracks)

            view = TrackRemoveView(self.bot, ctx.voice_client, valid_tracks)
            embed = discord.Embed(
                description=f"> {len(valid_tracks)} tracks from [{
                    name}]({query})",
                timestamp=datetime.datetime.now()
            ).set_author(
                name="Enqueued playlist",
                icon_url=self.bot.user.display_avatar.url
            )

            if artwork:
                embed.set_thumbnail(url=artwork)

            total_duration = sum(t.duration for t in valid_tracks)
            embed.add_field(
                name="Total Duration",
                value=format_duration(total_duration)
            )

            view.message = await ctx.send(embed=embed, view=view)

            if not ctx.voice_client.playing:
                track = await ctx.voice_client.queue.get_wait()
                await ctx.voice_client.play(track)

        except Exception as e:
            # Cleanup on error
            for track in valid_tracks:
                try:
                    await ctx.voice_client.queue.remove(track)
                except:
                    continue
            raise commands.CommandError(f"Failed to play playlist: {str(e)}")

    async def _handle_youtube(self, ctx: BoultContext, query: str):
        """Handle YouTube URLs with enhanced validation"""
        cache_key = f"youtube:{query}"
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            if isinstance(cached_result, wavelink.Playable):
                await self._play_single_track(ctx, cached_result)
                return
            elif isinstance(cached_result, list):
                await self._play_playlist(ctx, cached_result, "YouTube Playlist", None, query)
                return

        try:
            tracks = await wavelink.Playable.search(query, source="ytsearch")

            if not tracks:
                raise commands.CommandError("No tracks found")

            if isinstance(tracks, wavelink.Playlist):
                if not tracks.tracks:
                    raise commands.CommandError("Playlist is empty")

                valid_tracks = []
                for track in tracks.tracks:
                    if not hasattr(track, 'uri'):
                        continue
                    track.extras = wavelink.ExtrasNamespace({
                        "requester": ctx.author.id,
                        "source": "youtube",
                        "playlist": True
                    })
                    valid_tracks.append(track)

                if not valid_tracks:
                    raise commands.CommandError("No valid tracks in playlist")

                await self.cache_manager.set(cache_key, valid_tracks, expire=3600)
                await self._play_playlist(
                    ctx,
                    valid_tracks,
                    "YouTube Playlist",
                    None,
                    query
                )
            else:
                if not tracks[0] or not hasattr(tracks[0], 'uri'):
                    raise commands.CommandError("Invalid track object")
                await self.cache_manager.set(cache_key, tracks[0], expire=3600)
                await self._play_single_track(ctx, tracks[0])

        except wavelink.LavalinkLoadException as e:
            raise commands.CommandError(
                f"Failed to load from YouTube: {str(e)}")

    async def _handle_soundcloud(self, ctx: BoultContext, query: str):
        """Handle SoundCloud URLs with retry logic"""
        cache_key = f"soundcloud:{query}"
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            if isinstance(cached_result, wavelink.Playable):
                await self._play_single_track(ctx, cached_result)
                return
            elif isinstance(cached_result, list):
                await self._play_playlist(ctx, cached_result, "SoundCloud Playlist", None, query)
                return

        max_retries = 3
        retry_count = 0
        last_error = None

        while retry_count < max_retries:
            try:
                tracks = await wavelink.Playable.search(query, source="scsearch")

                if isinstance(tracks, wavelink.Playlist):
                    valid_tracks = []
                    for track in tracks.tracks:
                        if hasattr(track, 'uri'):
                            track.extras = wavelink.ExtrasNamespace({
                                "requester": ctx.author.id,
                                "source": "soundcloud",
                                "timestamp": datetime.datetime.now().timestamp()
                            })
                            valid_tracks.append(track)

                    if not valid_tracks:
                        raise commands.CommandError("No valid tracks in playlist")

                    await self.cache_manager.set(cache_key, valid_tracks, expire=3600)
                    await self._play_playlist(
                        ctx,
                        valid_tracks,
                        "SoundCloud Playlist",
                        None,
                        query
                    )
                else:
                    if not tracks or not tracks[0]:
                        raise commands.CommandError("No tracks found")
                    await self.cache_manager.set(cache_key, tracks[0], expire=3600)
                    await self._play_single_track(ctx, tracks[0])
                return

            except Exception as e:
                last_error = e
                retry_count += 1
                await asyncio.sleep(1)

        raise Exception(f"Failed to load from SoundCloud after {
                                     max_retries} attempts: {str(last_error)}")

    async def _handle_jiosaavn(self, ctx: BoultContext, query: str):
        """Handle JioSaavn URLs with enhanced error handling"""
        cache_key = f"jiosaavn:{query}"
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            if isinstance(cached_result, wavelink.Playable):
                await self._play_single_track(ctx, cached_result)
                return
            elif isinstance(cached_result, list):
                await self._play_playlist(ctx, cached_result, "JioSaavn Playlist", None, query)
                return

        try:
            tracks = await wavelink.Playable.search(query, source="jssearch")

            if isinstance(tracks, wavelink.Playlist):
                valid_tracks = []
                for track in tracks.tracks:
                    if not hasattr(track, 'uri'):
                        continue
                    track.extras = wavelink.ExtrasNamespace({
                        "requester": ctx.author.id,
                        "source": "jiosaavn",
                        "timestamp": datetime.datetime.now().timestamp()
                    })
                    valid_tracks.append(track)

                if not valid_tracks:
                    raise commands.CommandError("No valid tracks found in playlist")

                await self.cache_manager.set(cache_key, valid_tracks, expire=3600)
                await self._play_playlist(
                    ctx,
                    valid_tracks,
                    "JioSaavn Playlist",
                    None,
                    query
                )
            else:
                if not tracks or not tracks[0]:
                    raise commands.CommandError ("No tracks found")
                await self.cache_manager.set(cache_key, tracks[0], expire=3600)
                await self._play_single_track(ctx, tracks[0])

        except Exception as e:
            raise Exception(
                f"Failed to load from JioSaavn: {str(e)}")

    async def _handle_user_activity(self, ctx: BoultContext, user_id: int):
        """Handle user activity with enhanced validation and error handling"""
        cache_key = f"user_activity:{user_id}"
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            await self._play_single_track(ctx, cached_result)
            return

        user = ctx.guild.get_member(user_id)

        if not user:
            raise commands.CommandError("User not found in this server")

        if not user.activities:
            raise commands.CommandError("User is not listening to spotify")

        spotify_activity = None
        for activity in user.activities:
            if activity.type == discord.ActivityType.listening:
                spotify_activity = activity
                break

        if not spotify_activity:
            raise commands.CommandError("User is not listening to anything")

        if not hasattr(spotify_activity, 'track_url'):
            raise commands.CommandError("Cannot determine what user is listening to")

        try:
            tracks = await wavelink.Playable.search(spotify_activity.track_url)
            if not tracks:
                raise commands.CommandError(
                    "Could not find the track user is listening to")

            track = tracks[0]
            if not hasattr(track, 'uri'):
                raise commands.CommandError("Invalid track data")

            # Cache for 5 minutes
            await self.cache_manager.set(cache_key, track, expire=300)
            await self._play_single_track(ctx, track)

        except Exception as e:
            raise Exception(
                f"Failed to play user's current track: {str(e)}")

    async def _handle_generic_url(self, ctx: BoultContext, query: str):
        """Handle generic URLs with enhanced validation and source checking"""
        cache_key = f"generic_url:{query}"
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            if isinstance(cached_result, wavelink.Playable):
                await self._play_single_track(ctx, cached_result)
                return
            elif isinstance(cached_result, list):
                await self._play_playlist(ctx, cached_result, "Playlist", None, query)
                return

        known_sources = {
            "open.spotify.com": "Spotify",
            "jiosaavn.com": "JioSaavn",
            "youtube.com": "YouTube",
            "youtu.be": "YouTube",
            "soundcloud.com": "SoundCloud"
        }

        for source_url, source_name in known_sources.items():
            if source_url in query:
                return  # Skip known sources

        try:
            tracks = await wavelink.Playable.search(query)

            if not tracks:
                raise ValueError("No tracks found for the provided URL")

            if hasattr(tracks, 'type') and tracks.type in ["playlist", "album", "artist"]:
                valid_tracks = []
                for track in tracks.tracks:
                    if not hasattr(track, 'uri'):
                        continue
                    track.extras = wavelink.ExtrasNamespace({
                        "requester": ctx.author.id,
                        "source": "generic",
                        "timestamp": datetime.datetime.now().timestamp()
                    })
                    valid_tracks.append(track)

                if not valid_tracks:
                    raise commands.CommandError (
                        "No valid tracks found in playlist/album")

                await self.cache_manager.set(cache_key, valid_tracks, expire=3600)
                await self._play_playlist(
                    ctx,
                    valid_tracks,
                    "Playlist",
                    None,
                    query
                )
            else:
                if not tracks[0] or not hasattr(tracks[0], 'uri'):
                    raise commands.CommandError("Invalid track data")
                await self.cache_manager.set(cache_key, tracks[0], expire=3600)
                await self._play_single_track(ctx, tracks[0])

        except wavelink.LavalinkLoadException as e:
            raise Exception(f"Failed to load from URL: {str(e)}")
        except Exception as e:
            raise Exception(
                f"An error occurred while processing URL: {str(e)}")

    async def _handle_search_query(self, ctx: BoultContext, query: str):
        """Handle search queries with enhanced error handling and validation"""
        cache_key = f"search:{query}"
        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            await self._play_single_track(ctx, cached_result)
            return

        try:
            search_engine = await self._get_search_engine(ctx)

            tracks = await wavelink.Playable.search(query, source=search_engine)
            if not tracks:
                raise commands.CommandError(f"No tracks found using {search_engine}")

            if not tracks[0] or not hasattr(tracks[0], 'uri'):
                raise commands.CommandError("Invalid track data returned from search")

            # Cache for 30 minutes
            await self.cache_manager.set(cache_key, tracks[0], expire=1800)
            await self._play_single_track(ctx, tracks[0])

        except Exception as e:
            raise commands.CommandError(f"Search failed: {str(e)}")

    async def _get_search_engine(self, ctx: BoultContext) -> str:
        """Get user's preferred search engine with enhanced database interaction"""
        cache_key = f"search_engine:{ctx.author.id}"
        cached_engine = await self.cache_manager.get(cache_key)
        if cached_engine:
            return cached_engine

        try:
            result = await self.bot.db.fetch_one(
                "SELECT search_engine FROM user_config WHERE user_id=$1",
                ctx.author.id
            )

            if result and result.search_engine:
                if result.search_engine not in ['ytsearch', 'scsearch', 'spsearch']:
                    engine = 'spsearch'
                else:
                    engine = result.search_engine
                # Cache for 24 hours
                await self.cache_manager.set(cache_key, engine, expire=86400)
                return engine

            view = SearchEngine(ctx)
            view.message = await ctx.send(
                content="-# You can skip this by using </config search:1309100011728011377>",
                embed=discord.Embed(
                    color=self.bot.config.color.color,
                ).set_author(
                    name="Select a search engine",
                    icon_url="https://cdn.discordapp.com/emojis/1305502599977373717.webp?size=96&quality=lossless",
                ),
                view=view,
            )

            try:
                await view.wait()
                engine = view.value or "spsearch"
                await self.cache_manager.set(cache_key, engine, expire=86400)
                return engine
            except Exception:
                return "spsearch"

        except Exception as e:
            self.bot.logger.error(f"Error getting search engine: {str(e)}")
            return "spsearch"

    @commands.hybrid_command(name="shuffle", with_app_command=True, aliases=["shf"])
    @commands.check_any(commands.has_permissions(manage_channels=True))
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def shuffle(self, ctx: BoultContext):
        """Shuffles the queue with enhanced randomization and feedback"""
        player: wavelink.Player = ctx.voice_client

        if ctx.interaction:
            await ctx.defer()

        if not player.playing:
            raise commands.CommandError(
                "No track is currently playing in the queue.")

        queue = player.queue
        if not queue or queue.is_empty:
            raise commands.CommandError(
                "The queue is currently empty. Add some tracks first.")

        original_order = list(queue)
        queue_length = len(original_order)

        for _ in range(3):  #
            queue.shuffle()

        new_order = list(queue)
        consecutive_matches = sum(1 for i in range(
            queue_length) if i < queue_length-1 and original_order[i] == new_order[i])

        if consecutive_matches > queue_length // 3:
            queue.shuffle()

        embed = discord.Embed(
            color=self.bot.config.color.color,
            timestamp=datetime.datetime.now()
        )
        embed.set_author(
            name="Queue Shuffled Successfully",
            icon_url=self.bot.user.display_avatar.url
        )

        embed.add_field(
            name="Queue Stats",
            value=f"• Total Tracks: {queue_length}\n"
            f"• Current Track: {
                player.current.title if player.current else 'None'}\n"
            f"• Shuffle Quality: {
                100 - (consecutive_matches * 100 // queue_length)}%"
        )

        if queue_length > 0:
            preview = "\n".join(
                f"`{i+1}.` {track.title[:50]}..."
                for i, track in enumerate(list(queue)[:3])
            )
            if queue_length > 3:
                preview += f"\n... and {queue_length - 3} more tracks"
            embed.add_field(name="New Queue Preview",
                            value=preview, inline=False)

        view = MusicView(self.bot, player)
        view.remove_item(view.stop)

        await ctx.send(
            content=f"{ctx.author.mention} shuffled the queue",
            embed=embed,
            view=view
        )

    @commands.hybrid_command(name="pause", with_app_command=True)
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def pause(self, ctx: BoultContext):
        """Pauses playback with enhanced state management and feedback"""
        if ctx.interaction:
            await ctx.defer()

        player: wavelink.Player = ctx.voice_client

        if player.paused:
            raise commands.CommandError("The player is already in a paused state.")

        # Save current playback state
        current_position = player.position
        current_track = player.current

        # Perform pause operation
        await player.pause(True)

        # Create detailed embed
        embed = discord.Embed(
            color=self.bot.config.color.color,
            timestamp=datetime.datetime.now(),
            description=(f"• Position: {format_duration(current_position)}/{format_duration(current_track.length)}\n") if current_track else None
        )
        embed.set_author(
            name="Player Paused",
            icon_url=self.bot.user.display_avatar.url
        )

        view = MusicView(bot=self.bot, player=player)
        view.remove_item(view.next)
        view.remove_item(view.stop)

        try:
            await player.channel.edit(
                status=f"⏸️ {
                    current_track.title if current_track else 'No track playing'}"
            )
        except discord.Forbidden:
            pass

        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="resume", with_app_command=True, aliases=["unpause"])
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def resume(self, ctx: BoultContext):
        """Resumes playback with enhanced state management and feedback"""
        if ctx.interaction:
            await ctx.defer()

        player: wavelink.Player = ctx.voice_client

        if not player.paused:
            embed = discord.Embed(
                color=self.bot.config.color.color,
                description="The player is already playing."
            )
            embed.set_author(
                name="Resume Failed",
                icon_url=self.bot.user.display_avatar.url
            )

            view = MusicView(bot=self.bot, player=player)
            view.remove_item(view.next)
            view.remove_item(view.stop)

            return await ctx.send(embed=embed, view=view)

        current_track = player.current
        pause_duration = (datetime.datetime.now(
        ) - player.last_update).total_seconds() if hasattr(player, 'last_update') else 0

        await player.pause(False)
        player.last_update = datetime.datetime.now()

        embed = discord.Embed(
            color=self.bot.config.color.color,
            timestamp=datetime.datetime.now()
        )
        embed.set_author(
            name="Player Resumed",
            icon_url=self.bot.user.display_avatar.url
        )

        if current_track:
            embed.add_field(
                name="Track Info",
                value=f"• Now Playing: {current_track.title}\n"
                f"• Paused For: {format_duration(pause_duration)}\n"
                f"• Position: {format_duration(
                    player.position)}/{format_duration(current_track.length)}"
            )

            if player.queue and not player.queue.is_empty:
                next_track = player.queue[0]
                embed.add_field(
                    name="Up Next",
                    value=f"• {next_track.title}",
                    inline=False
                )

        view = MusicView(bot=self.bot, player=player)
        view.remove_item(view.next)
        view.remove_item(view.stop)

        try:
            await player.channel.edit(
                status=f"▶️ {
                    current_track.title if current_track else 'No track playing'}"
            )
        except discord.Forbidden:
            pass

        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="stop", with_app_command=True)
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def stop(self, ctx: BoultContext):
        """Stops playback """
        if ctx.interaction:
            await ctx.defer()

        player: wavelink.Player = ctx.voice_client

        confirm_embed = discord.Embed(
            color=self.bot.config.color.color,
            description=f"⚠️ This will stop playback and clear the queue"
        )
        confirm_embed.set_author(
            name="Confirm Stop", icon_url=self.bot.user.display_avatar.url)

        conf = await ctx.confirm(
            message="Are you sure you want to stop the player?",
            embed=confirm_embed
        )

        if conf:
            try:
                await player._destroy(with_invalidate=True)

                embed = discord.Embed(
                    color=self.bot.config.color.color,
                    description=f"Player stopped by {ctx.author.mention}"
                )
                embed.set_author(
                    name="Player Stopped",
                    icon_url=self.bot.user.display_avatar.url
                )

                await ctx.send(embed=embed)

                try:
                    await player.channel.edit(status="Boult Music")
                except discord.Forbidden:
                    pass

            except Exception as e:
                self.bot.logger.error(f"Error during player stop: {str(e)}")
                raise commands.CommandError(
                    "An error occurred while stopping the player.")

    @commands.hybrid_command(name="skip", with_app_command=True, aliases=["next"])
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def skip(self, ctx: BoultContext):
        """Skips the current track"""
        if ctx.interaction:
            await ctx.defer()

        player: wavelink.Player = ctx.voice_client

        if not player.current:
            raise commands.CommandError("No track is currently playing.")

        await player.next(ctx=ctx)

    @commands.hybrid_command(name="skipto", with_app_command=True)
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def skipto(self, ctx: BoultContext, index: int):
        """Skips to a specific track in the queue"""
        if ctx.interaction:
            await ctx.defer()

        player: wavelink.Player = ctx.voice_client

        try:
            is_dj = await ctx.is_dj()
            if not is_dj:
                raise commands.CommandError(
                    "You must have DJ permissions or be an Admin to use this command."
                )
        except Exception as e:
            self.bot.logger.error(f"DJ check failed: {str(e)}")
            raise commands.CommandError("Failed to verify DJ permissions.")

        if not player.queue or player.queue.is_empty:
            raise commands.CommandError("The queue is empty.")

        queue_length = len(player.queue)
        if not 1 <= index <= queue_length:
            raise commands.CommandError(
                f"Invalid index. Please provide a number between 1 and {queue_length}."
            )

        target_track = player.queue.get_at(index - 1)
        await player.play(track=target_track)

        embed = discord.Embed(
            color=self.bot.config.color.color,
            description=f"Skipped to **{target_track.title}**"
        )
        embed.set_author(
            name=f"Skipped to Track #{index}",
            icon_url=self.bot.user.display_avatar.url
        )

        view = MusicView(self.bot, player)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="loop", with_app_command=True, aliases=["l"])
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def loop(self, ctx: BoultContext):
        """Loop mode control"""
        if ctx.interaction:
            await ctx.defer()

        player: wavelink.Player = ctx.voice_client

        embed = discord.Embed(
            color=self.bot.config.color.color
        )
        embed.set_author(
            name="Loop Mode Settings",
            icon_url=self.bot.user.display_avatar.url
        )

        view = LoopView(self.bot, player)
        msg = await ctx.send(embed=embed, view=view)
        view.msg = msg

    @commands.hybrid_group(
        name="filter",
        with_app_command=True,
        invoke_without_subcommand=True
    )
    @check_home(cls=Player)
    async def _filter(self, ctx: BoultContext):
        """Enhanced filter management with detailed feedback and visualization"""
        if ctx.interaction:
            await ctx.defer()

        player: wavelink.Player = ctx.voice_client

        embed = discord.Embed(
            color=self.bot.config.color.color,
            title="Audio Filter Configuration",
            timestamp=datetime.datetime.now()
        )

        if hasattr(player, 'filters') and player.filters:
            active_filters = [
                f"• {filter_name}"
                for filter_name, is_active in player.filters.items()
                if is_active
            ]
            if active_filters:
                embed.add_field(
                    name="Active Filters",
                    value="\n".join(active_filters),
                    inline=False
                )

        if player.current:
            embed.add_field(
                name="Current Track",
                value=f"• {player.current.title}\n"
                f"• Duration: {format_duration(player.current.length)}",
                inline=False
            )

        view = FilterView(player=player)
        view.msg = await ctx.send(embed=embed, view=view)

    def get_volume_color(self, volume: int) -> discord.Color:
        """Enhanced volume color calculation with smoother transitions"""
        if volume <= 20:
            return discord.Color.green()
        elif volume <= 50:
            green = int(255 * (50 - volume) / 30)
            return discord.Color.from_rgb(255 - green, 255, 0)
        else:
            red = min(255, int(255 * (volume - 50) / 50) + 200)
            green = max(0, int(255 * (100 - volume) / 50))
            return discord.Color.from_rgb(red, green, 0)

    @commands.hybrid_command(name="volume", with_app_command=True, aliases=["vol"])
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def volume(self, ctx: BoultContext, volume: Optional[int] = None):
        """Enhanced volume control with visual feedback and state management"""
        if ctx.interaction:
            await ctx.defer()

        player: wavelink.Player = ctx.voice_client

        if not volume:
            embed = discord.Embed(
                color=self.get_volume_color(player.volume),
                timestamp=datetime.datetime.now()
            )
            embed.set_author(
                name="Volume Control",
                icon_url=self.bot.user.display_avatar.url
            )

            embed.add_field(
                name="Current Volume",
                value=f"🔊 {player.volume}%",
                inline=True
            )

            if player.current:
                embed.add_field(
                    name="Now Playing",
                    value=f"• {player.current.title}\n"
                    f"• Position: {format_duration(
                        player.position)}/{format_duration(player.current.length)}",
                    inline=False
                )

            view = VolumeView(self.bot, player)
            view.msg = await ctx.send(embed=embed, view=view)
            return

        if not 0 <= volume <= 100:
            raise commands.CommandError(
                "Volume must be between 0 and 100. Please provide a valid value."
            )

        previous_volume = player.volume

        await player.set_volume(volume)

        embed = discord.Embed(
            color=self.get_volume_color(volume),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(
            name="Volume Updated",
            icon_url=self.bot.user.display_avatar.url
        )

        # Add volume change details
        embed.add_field(
            name="Volume Change",
            value=f"Previous: {previous_volume}% → Current: {volume}%\n"
            f"{'🔊' * (volume // 10 + 1)}",
            inline=False
        )

        if volume > 100:
            embed.add_field(
                name="⚠️ Volume Warning",
                value="High volume levels may cause audio distortion.",
                inline=False
            )

        view = VolumeView(self.bot, player)
        view.msg = await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="search", with_app_command=True)
    @check_home(cls=Player)
    @in_voice_channel(user=True, bot=True)
    async def search(self, ctx: BoultContext, *, query: str):
        """
        Searches for a track.   
        """
        if ctx.interaction:
            await ctx.defer()

        search_engine = await self.bot.db.fetch_one(
            "SELECT search_engine FROM user_config WHERE user_id=$1", ctx.author.id
        )

        if search_engine is not None:
            source = getattr(search_engine, 'search_engine', None)
            if source is None:
                view = SearchEngine(ctx)
                view.message = await ctx.send(
                    content="-# You can skip this by using </config search:1309100011728011377>",
                    embed=discord.Embed(
                        color=self.bot.config.color.color,
                    ).set_author(
                        name="Select a search engine",
                        icon_url="https://cdn.discordapp.com/emojis/1305502599977373717.webp?size=96&quality=lossless",
                    ),
                    view=view,
                )
                await view.wait()
                source = view.value
                if not source:
                    source = "spsearch"
        else:
            view = SearchEngine(ctx)
            view.message = await ctx.send(
                content="-# You can skip this by using >config search <engine_name>",
                embed=discord.Embed(
                    color=self.bot.config.color.color,
                ).set_author(
                    name="Select a search engine",
                    icon_url="https://cdn.discordapp.com/emojis/1305502599977373717.webp?size=96&quality=lossless",
                ),
                view=view,
            )
            await view.wait()
            source = view.value
            if not source:
                source = "spsearch"

        tracks = await wavelink.Playable.search(query, source=source)

        tracks_ = [
            {"name": f"{track.title} - {track.author}", "value": track.uri, "hyperlink": f"[{track.title}]({track.uri}) - {track.author}"} for track in tracks
        ]

        page = SimplePages([track["hyperlink"]
                           for track in tracks_], ctx=ctx, per_page=5)
        select = SearchTrackSelect(
            items=tracks_,
        )
        select.player = ctx.voice_client if ctx.voice_client else None
        select.message = view.message
        select.source = view.value
        select.bot = self.bot
        page.add_item(
            select
        )
        for items in page.children:
            if isinstance(items, discord.ui.Button):
                if items.label == "Skip to page..." or items.label == "Quit":
                    page.remove_item(items)

        page.embed.color = self.bot.config.color.color
        await page.start()

    @commands.hybrid_command(name="autoplay", with_app_command=True, aliases=["ap"])
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def autoplay(self, ctx: BoultContext):
        """
        Enables or disables autoplay mode."""
        if ctx.interaction:
            await ctx.defer()

        view = AutoPlayView(ctx.voice_client)
        view.msg = await ctx.send(
            embed=discord.Embed(color=self.bot.config.color.color).set_author(
                name="Press buttons to enable", icon_url=self.bot.user.display_avatar.url
            ),
            view=view,
        )

    @commands.hybrid_command(name="seek")
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def seek(self, ctx: BoultContext, position: str) -> None:
        """Seek to a specific time in the current song (e.g., 1:30)."""
        if ctx.interaction:
            await ctx.defer()

        if not ctx.voice_client or not ctx.voice_client.playing:
            raise commands.CommandError("No song is currently playing.")

        try:
            minutes, seconds = map(int, position.split(":"))
            milliseconds = (minutes * 60 + seconds) * 1000
            await ctx.voice_client.seek(milliseconds)
            await ctx.send(f"Jumped to {position}.")
        except ValueError:
            raise commands.CommandError(
                "Please provide a valid time format (MM:SS).")

    @commands.hybrid_group(name="queue")
    async def queue(self, ctx: BoultContext):
        """ 
        Queue management commands.
        """
        await ctx.send_help(ctx.command)

    @queue.command(name="movetrack", with_app_command=True, aliases=["mt"])
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def movetrack(self, ctx: BoultContext, index: int, to: int):
        """
        Moves a track to a specific position in the queue.
        """
        if ctx.interaction:
            await ctx.defer()

        dj = await ctx.is_dj()

        if not dj:
            raise commands.CommandError(
                "You must be a DJ or Admin to use this command.")

        if index > len(ctx.voice_client.queue):
            return await ctx.send(
                embed=discord.Embed(color=self.bot.config.color.color).set_author(
                    name="Invalid index", icon_url=self.bot.user.display_avatar.url
                )
            )

        if to > len(ctx.voice_client.queue):
            raise commands.CommandError("Invalid index")

        track = ctx.voice_client.queue._items[index - 1]
        ctx.voice_client.queue._items.remove(track)
        ctx.voice_client.queue._items.insert(to - 1, track)
        await ctx.send(
            embed=discord.Embed(color=self.bot.config.color.color).set_author(
                name=f"Moved {track.title} to {to}",
                icon_url=self.bot.user.display_avatar.url,
            )
        )

    @queue.command(name="remove", with_app_command=True, aliases=["rm"])
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def remove(self, ctx: BoultContext, index: int):
        """Removes a track from the queue."""
        if ctx.interaction:
            await ctx.defer()

        dj = await ctx.is_dj()

        if not dj:
            raise commands.CommandError(
                "You must be a DJ or Admin to use this command.")

        if index > len(ctx.voice_client.queue):
            raise commands.CommandError("Invalid index to remove.")

        track = ctx.voice_client.queue._items[index - 1]
        ctx.voice_client.queue._items.remove(track)
        await ctx.send(
            embed=discord.Embed(color=self.bot.config.color.color).set_author(
                name=f"Removed {track.title}", icon_url=self.bot.user.display_avatar.url
            )
        )

    @queue.command(name="clear", with_app_command=True, aliases=["clr"])
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def clear(self, ctx: BoultContext):
        """Clears the queue."""
        if ctx.interaction:
            await ctx.defer()

        conf = await ctx.confirm(
            "Are you sure you want to clear the queue?",
            timeout=30,
        )

        if not conf:
            return await ctx.send(
                embed=discord.Embed(color=self.bot.config.color.color).set_author(
                    name="Cancelled", icon_url=self.bot.user.display_avatar.url)
            )

        ctx.voice_client.queue.clear()
        await ctx.send(embed=discord.Embed(color=self.bot.config.color.color).set_author(name="Cleared the queue", icon_url=self.bot.user.display_avatar.url))

    @queue.command(name="removetracks", with_app_command=True, aliases=["rt"])
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def removetrack(self, ctx: BoultContext, limit: int):
        """Removes a track from the queue."""
        if ctx.interaction:
            await ctx.defer()

        dj = await ctx.is_dj()

        if not dj:
            raise commands.CheckFailure(
                "You must be a DJ or Admin to use this command."
            )

        if limit > len(ctx.voice_client.queue):
            raise commands.CommandError("Invalid limit")

        queue = ctx.voice_client.queue._items[:limit]
        for track in queue:
            ctx.voice_client.queue._items.remove(track)

        await ctx.send(embed=discord.Embed(color=self.bot.config.color.color).set_author(name=f"Removed {limit} tracks from the queue", icon_url=self.bot.user.display_avatar.url))

    @queue.command(name="show", with_app_command=True, aliases=["sh", "s"])
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def show(self, ctx: BoultContext):
        """
        Shows the player queue.
        """
        if ctx.interaction:
            await ctx.defer()
        if ctx.voice_client.queue.is_empty:
            raise commands.CommandError("Queue is empty")

        tracks = []
        for track in ctx.voice_client.queue:
            tracks.append(
                f"[{track.title}]({track.uri}) - {f'<@{track.extras.requester}>' if hasattr(
                    track.extras, 'requester') else '@Unknown'}"
            )

        page = SimplePages(tracks, ctx=ctx, per_page=10)
        view2 = TrackRemoveView(
            self.bot, ctx.voice_client, ctx.voice_client.queue._items)
        for items in page.children:
            if isinstance(items, discord.ui.Button):
                if items.label == "Skip to page..." or items.label == "Quit":
                    page.remove_item(items)
        page.embed.color = self.bot.config.color.color
        await page.start()

        view2.message = await ctx.send(view=view2)
