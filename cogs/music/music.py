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



import re
from typing import List, Optional

import discord
import wavelink
from discord import app_commands
from discord.ext import commands

from cogs.music.view.view import AutoPlayView
from core import Boult, Cog, Player
from utils import (BoultContext, SimplePages, check_home, in_voice_channel,
                   truncate_string, try_connect)
from utils.exceptions import (BoultCheckFailure, InvalidSearch, NoResultFound, NoTracksFound, BoultWavelinkException, IncorrectChannelError)

from .view import (FilterView, LoopView, MusicView, SearchEngine,
                   SearchTrackSelect, TrackRemoveView, VolumeView)


class Music(Cog):
    """
    Music commands to play music.
    """

    def __init__(self, bot: Boult):
        self.bot = bot

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(id=1229721986674983043, name="playlist_avon")
    


    async def search_wavelink_track(self, query: str):
        return await wavelink.Playable.search(query, source="spsearch")

    async def query_autocomplete(
        self, interaction: discord.Interaction, query: str
    ) -> List[app_commands.Choice[str]]:
        try:
            tracks = await wavelink.Playable.search(query, source="spsearch")
        except:
            return [
                app_commands.Choice(
                    name=f"Search Something or use url or query", value=""
                )
            ]
        songs = [
            app_commands.Choice(
                name=f"{truncate_string(value=f'{track.title} - {track.author}', max_length=100, suffix='')}",
                value=track.uri,
            )
            for track in tracks
        ]
        return songs
    
    @commands.command(name="playany", aliases=["playfromany", "plany"], hidden=True)
    @check_home(cls=Player)
    @in_voice_channel(user=True)
    @try_connect(cls=Player)
    async def play_from_any_source(self, ctx: BoultContext, *, query: str):
        if ctx.voice_client.channel != ctx.author.voice.channel:
            raise IncorrectChannelError(f"Join {ctx.voice_client.channel.mention} and try again.")

        if not hasattr(ctx.voice_client, "home"):
            ctx.voice_client.home = ctx.channel

        ctx.voice_client.autoplay = wavelink.AutoPlayMode.partial

        ctx.voice_client.ctx = ctx

        tracks = await wavelink.Playable.search(query)

        track = tracks[0]

        track.extras = wavelink.ExtrasNamespace({"requester": ctx.author.id})

        await ctx.voice_client.queue.put_wait(track)

        view = TrackRemoveView(self.bot, ctx.voice_client, [track])
        view.message=await ctx.send(
            embed=discord.Embed(
                description=f"> [{track.title}]({track.uri}) by [{track.author}]({track.artist.url})"
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

        # Validate voice channel
        if ctx.voice_client.channel != ctx.author.voice.channel:
            raise IncorrectChannelError(f"Join {ctx.voice_client.channel.mention} and try again.")

        # Initialize voice client properties
        if not hasattr(ctx.voice_client, "home"):
            ctx.voice_client.home = ctx.channel
        ctx.voice_client.autoplay = wavelink.AutoPlayMode.partial
        ctx.voice_client.ctx = ctx

        try:
            # Handle different source types
            if "open.spotify.com" in query:
                await self._handle_spotify(ctx, query)
                return
                
            if any(url in query for url in ["youtube.com", "youtu.be"]):
                await self._handle_youtube(ctx, query)
                return
                
            if "soundcloud.com" in query:
                await self._handle_soundcloud(ctx, query)
                return
                
            if "jiosaavn.com" in query:
                await self._handle_jiosaavn(ctx, query)
                return

            mention_match = re.match(r"<@!?(\d+)>", query)  # Match mention format
            user_id_match = re.match(r"^\d+$", query)       # Match numeric user ID

            if mention_match or user_id_match:
                user_id = int(mention_match.group(1) if mention_match else query)
                await self._handle_user_activity(ctx, user_id=user_id)
                return

            # Handle generic URLs
            if query.startswith("https://"):
                await self._handle_generic_url(ctx, query)
                return

            # Handle search query
            await self._handle_search_query(ctx, query)

        except Exception as e:
            if not ctx.interaction:
                await ctx.message.add_reaction(ctx.tick(opt=False))
            msg = f"An error occurred while processing your request: {e}"
            raise commands.CommandError(msg)
        else:
            if not ctx.interaction:
                await ctx.message.add_reaction(ctx.tick(opt=True))

    async def _handle_spotify(self, ctx: BoultContext, query: str):
        """Handle Spotify URLs"""
        if "/track/" in query:
            tracks = await wavelink.Playable.search(query)
            await self._play_single_track(ctx, tracks[0])
            
        elif "/playlist/" in query:
            try:
                tracks = await wavelink.Playable.search(query, source="spsearch")
                playlist = await self.bot.spotify.get_playlist(query)
            except:
                playlist = await self.bot.spotify.get_playlist(query)
                tracks = []
                for track in playlist.tracks:
                    track = await wavelink.Playable.search(track.entity.url)
                    tracks.append(track[0]) 

            await self._play_playlist(ctx, tracks, playlist.entity.name, playlist.artwork, query)
            
        elif "/album/" in query:
            tracks = await wavelink.Playable.search(query, source="spsearch")
            album = await self.bot.spotify.get_album(query)
            await self._play_playlist(ctx, tracks.tracks, album.entity.name, album.artwork, query)
            
        elif "/artist/" in query:
            tracks = await wavelink.Playable.search(query, source="spsearch")
            artist = await self.bot.spotify.get_artist(query)
            await self._play_playlist(ctx, tracks.tracks, f"Top tracks by {artist.entity.name}", artist.artwork, query)


    async def _play_single_track(self, ctx: BoultContext, track: wavelink.Playable):
        """Play a single track"""
        track.extras = wavelink.ExtrasNamespace({"requester": ctx.author.id})
        await ctx.voice_client.queue.put_wait(track)
        
        embed = discord.Embed(
            description=f"> [{track.title}]({track.uri}) by {track.author}"
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

    async def _play_playlist(self, ctx: BoultContext, tracks, name, artwork, query):
        """Play a playlist"""
        for track in tracks:
            track.extras = wavelink.ExtrasNamespace({"requester": ctx.author.id})
        
        await ctx.voice_client.queue.put_wait(tracks)
        
        view = TrackRemoveView(self.bot, ctx.voice_client, tracks)
        view.message = await ctx.send(
            embed=discord.Embed(
                description=f"> {len(tracks)} tracks from [{name}]({query})"
            ).set_author(
                name="Enqueued playlist",
                icon_url=self.bot.user.display_avatar.url
            ).set_thumbnail(url=artwork),
            view=view
        )

        if not ctx.voice_client.playing:
            track = await ctx.voice_client.queue.get_wait()
            await ctx.voice_client.play(track)

    async def _handle_youtube(self, ctx: BoultContext, query: str):
        """Handle YouTube URLs"""
        tracks = await wavelink.Playable.search(query, source="ytsearch")
        
        if isinstance(tracks, wavelink.Playlist):
            for track in tracks.tracks:
                track.extras = wavelink.ExtrasNamespace({"requester": ctx.author.id})
            
            await self._play_playlist(
                ctx, 
                tracks.tracks,
                "YouTube Playlist",
                None,
                query
            )
        else:
            await self._play_single_track(ctx, tracks[0])

    async def _handle_soundcloud(self, ctx: BoultContext, query: str):
        """Handle SoundCloud URLs"""
        tracks = await wavelink.Playable.search(query, source="scsearch")
        
        if isinstance(tracks, wavelink.Playlist):
            for track in tracks.tracks:
                track.extras = wavelink.ExtrasNamespace({"requester": ctx.author.id})
            
            await self._play_playlist(
                ctx,
                tracks.tracks,
                "SoundCloud Playlist",
                None,
                query
            )
        else:
            await self._play_single_track(ctx, tracks[0])

    async def _handle_jiosaavn(self, ctx: BoultContext, query: str):
        """Handle JioSaavn URLs"""
        tracks = await wavelink.Playable.search(query, source="jssearch")
        
        if isinstance(tracks, wavelink.Playlist):
            for track in tracks.tracks:
                track.extras = wavelink.ExtrasNamespace({"requester": ctx.author.id})
            
            await self._play_playlist(
                ctx,
                tracks.tracks,
                "JioSaavn Playlist",
                None,
                query
            )
        else:
            await self._play_single_track(ctx, tracks[0])

    async def _handle_user_activity(self, ctx: BoultContext, user_id: int):
        """Handle user activity/currently playing"""
        user = ctx.guild.get_member(user_id)
        
        if not user or not user.activities:
            raise ValueError("User not found or not listening to anything")
            
        for activity in user.activities:
            if activity.type == discord.ActivityType.listening:
                tracks = await wavelink.Playable.search(activity.track_url)
                if not tracks:
                    raise ValueError("Track not found")
                await self._play_single_track(ctx, tracks[0])
                return
                
        raise ValueError("User is not listening to anything")

    async def _handle_generic_url(self, ctx: BoultContext, query: str):
        """Handle generic URLs"""
        # Skip if URL is from known sources
        known_sources = [
            "open.spotify.com",
            "jiosaavn.com",
            "youtube.com",
            "youtu.be",
            "soundcloud.com"
        ]
        
        if any(source in query for source in known_sources):
            return
            
        try:
            tracks = await wavelink.Playable.search(query)
            
            if not tracks:
                raise ValueError("No tracks found")
                
            if hasattr(tracks, 'type') and tracks.type in ["playlist", "album", "artist"]:
                for track in tracks.tracks:
                    track.extras = wavelink.ExtrasNamespace({"requester": ctx.author.id})
                
                await self._play_playlist(
                    ctx,
                    tracks.tracks,
                    "Playlist",
                    None,
                    query
                )
            else:
                await self._play_single_track(ctx, tracks[0])
                
        except wavelink.LavalinkLoadException:
            raise BoultWavelinkException("Could not load track")

    async def _handle_search_query(self, ctx: BoultContext, query: str):
        """Handle regular search queries"""
        # Get user's preferred search engine
        search_engine = await self._get_search_engine(ctx)
        
        tracks = await wavelink.Playable.search(query, source=search_engine)
        if not tracks:
            raise ValueError("No tracks found")
            
        await self._play_single_track(ctx, tracks[0])

    async def _get_search_engine(self, ctx: BoultContext) -> str:
        """Get user's preferred search engine or prompt for selection"""
        search_engine = await self.bot.db.fetch_one(
            "SELECT search_engine FROM user_config WHERE user_id=$1",
            ctx.author.id
        )
        
        if search_engine and search_engine.search_engine:
            return search_engine.search_engine
            
        # Prompt user to select search engine
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
        return view.value or "spsearch"


    async def _play_playlist(self, ctx: BoultContext, tracks, name, artwork, query):
        """Play a playlist"""
        for track in tracks:
            track.extras = wavelink.ExtrasNamespace({"requester": ctx.author.id})
        
        await ctx.voice_client.queue.put_wait(tracks)
        
        embed = discord.Embed(
            description=f"> {len(tracks)} tracks from [{name}]({query})"
        ).set_author(
            name="Enqueued playlist",
            icon_url=self.bot.user.display_avatar.url
        )
        
        if artwork:
            embed.set_thumbnail(url=artwork)
        
        view = TrackRemoveView(self.bot, ctx.voice_client, tracks)
        view.message = await ctx.send(embed=embed, view=view)

        if not ctx.voice_client.playing:
            track = await ctx.voice_client.queue.get_wait()
            await ctx.voice_client.play(track)

    @commands.hybrid_command(name="shuffle", with_app_command=True, aliases=["shf"])
    @commands.check_any(commands.has_permissions(manage_channels=True))
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def shuffle(self, ctx: BoultContext):
        """Shuffles the queue"""

        vc: wavelink.Player = ctx.voice_client

        if ctx.interaction:
            await ctx.defer()

        if not vc.playing:
            raise BoultCheckFailure("No track is playing.")
        if queue := vc.queue:
            if queue.is_empty:
                raise BoultCheckFailure("Queue is empty.")

            queue.shuffle()

            await ctx.send(f"{ctx.author.mention} queue has been shuffled.")
            return

    @commands.hybrid_command(name="pause", with_app_command=True)
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)

    async def pause(self, ctx: BoultContext):
        """
        Pauses the player."""
        if ctx.interaction:
            await ctx.defer()

        view = MusicView(bot=self.bot, player=ctx.voice_client)

        view.remove_item(view.next)
        view.remove_item(view.stop)

        if ctx.voice_client.paused:
            raise BoultCheckFailure("Player is already paused.")

        await ctx.voice_client.pause(True)

        await ctx.send(
            embed=discord.Embed(color=self.bot.config.color.color).set_author(
                name="Paused the player", icon_url=self.bot.user.display_avatar.url
            ),
            view=view,
        )

    @commands.hybrid_command(name="resume", with_app_command=True, aliases=["unpause"])
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)

    async def resume(self, ctx: BoultContext):
        """
        Resumes the player."""
        if ctx.interaction:
            await ctx.defer()

        view = MusicView(bot=self.bot, player=ctx.voice_client)

        view.remove_item(view.next)
        view.remove_item(view.stop)
        

        if not ctx.voice_client.paused:
            return await ctx.send(
                embed=discord.Embed(
                    color=self.bot.config.color.color,
                ).set_author(
                    name="Player is not paused",
                    icon_url=self.bot.user.display_avatar.url,
                ),
                view=view,
            )

        await ctx.voice_client.pause(False)

        await ctx.send(
            embed=discord.Embed(color=self.bot.config.color.color).set_author(
                name="Resumed the player", icon_url=self.bot.user.display_avatar.url
            ),
            view=view,
        )

    @commands.hybrid_command(name="stop", with_app_command=True)
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)

    async def stop(self, ctx: BoultContext):
        """
        Stops the player.
        """
        if ctx.interaction:
            await ctx.defer()

        conf = await ctx.confirm(
            message="Are you sure you want to stop the player?",
        )

        if conf:
            # ctx.voice_client.cleanup()
            await ctx.voice_client._destroy(with_invalidate=True)

            await ctx.send(
                embed=discord.Embed(color=self.bot.config.color.color).set_author(
                    name="Stopped the player", icon_url=self.bot.user.display_avatar.url
                )
            )
            # ctx.voice_client.disconnect(force=True)

    @commands.hybrid_command(name="skip", with_app_command=True, aliases=["next"])
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)

    async def skip(self, ctx: BoultContext):
        """
        Skips the current track.
        """
        if ctx.interaction:
            await ctx.defer()

        await ctx.voice_client._skip(ctx=ctx)

    @commands.hybrid_command(name="skipto", with_app_command=True)
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)

    # @commands.has_guild_permissions(manage_guild=True)
    async def skipto(self, ctx: BoultContext, index: int):
        """
        Skips to a specific track.
        """
        if ctx.interaction:
            await ctx.defer()

        dj = await ctx.is_dj()

        if not dj:
            raise BoultCheckFailure("You must be a DJ or Admin to use this command.")

        if index > len(ctx.voice_client.queue):
            return await ctx.send(
                embed=discord.Embed(color=self.bot.config.color.color).set_author(
                    name="Invalid index", icon_url=self.bot.user.display_avatar.url
                )
            )

        track = ctx.voice_client.queue.get_at(index - 1)

        await ctx.voice_client.play(track=track)

        await ctx.send(
            embed=discord.Embed(color=self.bot.config.color.color).set_author(
                name=f"Skipped to {track.title}",
                icon_url=self.bot.user.display_avatar.url,
            )
        )

    @commands.hybrid_command(name="loop", with_app_command=True, aliases=["l"])
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)

    async def loop(self, ctx: BoultContext):

        """
        Enables or disables loop mode."""
        if ctx.interaction:
            await ctx.defer()

        embed = discord.Embed(color=self.bot.config.color.color)
        embed.set_author(
            name="Select a loop mode", icon_url=self.bot.user.display_avatar.url
        )

        view = LoopView(self.bot, ctx.voice_client)
        msg = await ctx.send(embed=embed, view=view)
        view.msg = msg

    @commands.hybrid_group(
        name="filter", with_app_command=True, invoke_without_subcommand=True
    )
    @check_home(cls=Player)

    async def _filter(self, ctx: BoultContext):
        """command for managing filters."""
        if ctx.interaction:
            await ctx.defer()
        view = FilterView(player=ctx.voice_client)
        view.msg = await ctx.send(
            embed=discord.Embed(
                color=self.bot.config.color.color, title="Select a filter"
            ),
            view=view,
        )

    def get_volume_color(self, volume: int) -> discord.Color:
        green = max(0, 255 - (volume * 255 // 100))
        red = min(255, volume * 255 // 100)
        return discord.Color.from_rgb(red, green, 0)

    @commands.hybrid_command(name="volume", with_app_command=True, aliases=["vol"])
    @in_voice_channel(user=True, bot=True)
    @check_home(cls=Player)
    async def volume(self, ctx: BoultContext, volume: Optional[int] = None):
        """Sets the volume of the player."""
        if ctx.interaction:
            await ctx.defer()

        if not volume:
            view = VolumeView(self.bot, ctx.voice_client)
            view.msg = await ctx.send(
                embed=discord.Embed(color=self.bot.config.color.color).set_author(
                    name="Select a volume", icon_url=self.bot.user.display_avatar.url
                ),
                view=view,
            )
            return

        # Fix the volume range check
        if not 0 <= volume <= 100:
            raise BoultCheckFailure("Volume must be between 0 and 100")

        await ctx.voice_client.set_volume(volume)
        view = VolumeView(self.bot, ctx.voice_client)
        view.msg = await ctx.send(
            embed=discord.Embed(color=self.get_volume_color(volume)).set_author(
                name=f"Volume set to {volume}",
                icon_url=self.bot.user.display_avatar.url,
            ),
            view=view,
        )


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
            {"name": f"{track.title} - {track.author}", "value": track.uri, "hyperlink": f"[{track.title}]({track.uri}) - {track.author}" } for track in tracks
        ]

        page = SimplePages([track["hyperlink"] for track in tracks_], ctx=ctx, per_page=5)
        select =  SearchTrackSelect(
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
            raise BoultCheckFailure("No song is currently playing.")
        
        try:
            minutes, seconds = map(int, position.split(":"))
            milliseconds = (minutes * 60 + seconds) * 1000
            await ctx.voice_client.seek(milliseconds)
            await ctx.send(f"Jumped to {position}.")
        except ValueError:
            raise BoultCheckFailure("Please provide a valid time format (MM:SS).")


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
            raise BoultCheckFailure("You must be a DJ or Admin to use this command.")

        if index > len(ctx.voice_client.queue):
            return await ctx.send(
                embed=discord.Embed(color=self.bot.config.color.color).set_author(
                    name="Invalid index", icon_url=self.bot.user.display_avatar.url
                )
            )

        if to > len(ctx.voice_client.queue):
            raise BoultCheckFailure("Invalid index")

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
            raise BoultCheckFailure("You must be a DJ or Admin to use this command.")
        
        if index > len(ctx.voice_client.queue):
            raise BoultCheckFailure("Invalid index to remove.")
        
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
                embed=discord.Embed(color=self.bot.config.color.color).set_author(name="Cancelled", icon_url=self.bot.user.display_avatar.url)
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
            raise BoultCheckFailure("Invalid limit")


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
            raise BoultCheckFailure("Queue is empty")

        tracks = []
        for track in ctx.voice_client.queue:
            tracks.append(
                f"[{track.title}]({track.uri}) - {f'<@{track.extras.requester}>' if hasattr(track.extras, 'requester') else '@Unknown'}"
            )

        page = SimplePages(tracks, ctx=ctx, per_page=10)
        view2 = TrackRemoveView(self.bot, ctx.voice_client, ctx.voice_client.queue._items)
        for items in page.children:
            if isinstance(items, discord.ui.Button):
                if items.label == "Skip to page..." or items.label == "Quit":
                    page.remove_item(items)
        page.embed.color = self.bot.config.color.color
        await page.start()

        view2.message = await ctx.send(view=view2)
