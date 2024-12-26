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
import logging
from typing import Dict, Optional, Set, Union

import discord
import wavelink
from wavelink.tracks import Playable

from config import emoji
from core import Boult, Player
from extensions.context import BoultContext
from utils import TimedTask
from utils.cache import CacheManager
from utils.format import truncate_string

logger = logging.getLogger(__name__)

class PlayerState:
    def __init__(self):
        self.last_position: float = 0.0
        self.last_update: datetime.datetime = datetime.datetime.now()
        self.pause_duration: float = 0.0
        self.total_played: float = 0.0

class MusicView(discord.ui.View):
    def __init__(self, bot: Boult, player: Player):
        super().__init__(timeout=None)
        self.bot = bot
        self.player = player
        self._tasks: Dict[int, TimedTask] = {}
        self._track_states: Dict[str, PlayerState] = {}
        self._updated_tracks: Set[str] = set()
        self._cache = CacheManager(max_size=100, ttl=300)
        self._lock = asyncio.Lock()

        # Initialize button states
        self.play.emoji = emoji.pause if player.paused else emoji.play
        self._setup_button_states()

    def _setup_button_states(self):
        """Configure initial button states based on player status"""
        self.previous.disabled = not bool(self.player.queue.history)
        self.next.disabled = not bool(self.player.queue)
        self.stop.disabled = not self.player.current

    async def _update_player_state(self, track_id: str) -> None:
        """Update player state tracking"""
        async with self._lock:
            if track_id not in self._track_states:
                self._track_states[track_id] = PlayerState()
            
            state = self._track_states[track_id]
            current_time = datetime.datetime.now()
            
            if self.player.current:
                elapsed = (current_time - state.last_update).total_seconds()
                if not self.player.paused:
                    state.total_played += elapsed
                else:
                    state.pause_duration += elapsed
                    
            state.last_position = self.player.position
            state.last_update = current_time
            self._updated_tracks.add(track_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Enhanced interaction validation with rate limiting and permissions check"""
        if not await self._cache.get(f"interaction_cooldown:{interaction.user.id}"):
            if interaction.user not in self.player.channel.members:
                await interaction.response.send_message(
                    "You must be in the voice channel to use these controls", 
                    ephemeral=True
                )
                return False
                
        #     await self._cache.set(
        #         f"interaction_cooldown:{interaction.user.id}", 
        #         True, 
        #         expire=1
        #     )
        #     return True
            
        # await interaction.response.send_message(
        #     "Please wait a moment before using controls again",
        #     ephemeral=True
        # )
        # return False

    @discord.ui.button(emoji=emoji.prev, row=1)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle previous track with state management"""
        try:
            if self.player.current:
                await self._update_player_state(self.player.current.identifier)
            await self.player.previous(ctx=interaction)
            self._setup_button_states()
        except Exception as e:
            logger.error(f"Error handling previous track: {e}")
            await interaction.response.send_message(
                "Failed to play previous track", 
                ephemeral=True
            )

    @discord.ui.button(emoji=emoji.pause, row=1) 
    async def play(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Enhanced play/pause handling with state tracking"""
        try:
            async with self._lock:
                if not self.player.paused:
                    button.emoji = emoji.play
                    await self.player.pause(True)
                    if self.player.current:
                        await self._update_player_state(self.player.current.identifier)
                    await interaction.response.send_message("Playback paused", ephemeral=True)
                else:
                    button.emoji = emoji.pause
                    await self.player.pause(False)
                    await interaction.response.send_message("Playback resumed", ephemeral=True)

                await interaction.message.edit(view=self)
        except Exception as e:
            logger.error(f"Error toggling playback state: {e}")
            await interaction.response.send_message(
                "Failed to update playback state",
                ephemeral=True
            )

    @discord.ui.button(emoji=emoji.stop, row=1)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Stop playback with cleanup"""
        try:
            if self.player.current:
                await self._update_player_state(self.player.current.identifier)
            
            # Cancel any pending tasks
            for task in self._tasks.values():
                task.cancel()
            self._tasks.clear()
            
            await self.player.destroy()
            await interaction.response.send_message(
                "Playback stopped and queue cleared",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error stopping playback: {e}")
            await interaction.response.send_message(
                "Failed to stop playback",
                ephemeral=True
            )

    @discord.ui.button(emoji=emoji.next, row=1)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Skip to next track with state management"""
        try:
            if self.player.current:
                await self._update_player_state(self.player.current.identifier)
            await self.player.next(ctx=interaction)
            self._setup_button_states()
        except Exception as e:
            logger.error(f"Error skipping track: {e}")
            await interaction.response.send_message(
                "Failed to skip to next track",
                ephemeral=True
            )
class LoopView(discord.ui.View):
    def __init__(self, bot: Boult, player: Player):
        super().__init__(timeout=30)
        self.bot: Boult = bot
        self.player: Player = player
        self.msg: discord.Message = None
        self._current_mode: wavelink.QueueMode = player.queue.mode
        self._button_states = {
            'track': False,
            'queue': False,
            'disable': True
        }
        self._initialize_button_states()

    def _initialize_button_states(self) -> None:
        """Initialize button states based on current queue mode"""
        if self._current_mode == wavelink.QueueMode.loop:
            self._button_states.update({'track': True, 'queue': False, 'disable': False})
        elif self._current_mode == wavelink.QueueMode.loop_all:
            self._button_states.update({'track': False, 'queue': True, 'disable': False})
        else:
            self._button_states.update({'track': False, 'queue': False, 'disable': True})
        
        self._update_button_states()

    def _update_button_states(self) -> None:
        """Update button disabled states"""
        self.track.disabled = self._button_states['track']
        self.queue.disabled = self._button_states['queue'] 
        self.disable.disabled = self._button_states['disable']

    async def _handle_mode_change(self, interaction: discord.Interaction, new_mode: wavelink.QueueMode, 
                                button_updates: dict, message: str, icon_url: str) -> None:
        """Handle queue mode changes and UI updates"""
        try:
            self.player.queue.mode = new_mode
            self._current_mode = new_mode
            self._button_states.update(button_updates)
            self._update_button_states()

            embed = discord.Embed(color=self.bot.config.color.color)
            embed.set_author(name=message, icon_url=icon_url)
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Failed to change loop mode: {e}")
            await interaction.response.send_message("Failed to update loop mode", ephemeral=True)

    async def on_timeout(self) -> None:
        """Clean up on view timeout"""
        if self.msg:
            try:
                await self.msg.delete()
            except discord.NotFound:
                pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Verify user is in voice channel"""
        if interaction.user not in self.player.channel.members:
            await interaction.response.send_message(
                "You are not in the voice channel", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Queue")
    async def queue(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._handle_mode_change(
            interaction=interaction,
            new_mode=wavelink.QueueMode.loop_all,
            button_updates={'track': False, 'queue': True, 'disable': False},
            message="Looped the queue",
            icon_url="https://cdn.discordapp.com/emojis/1299820129403670568.webp?size=44&quality=lossless"
        )

    @discord.ui.button(label="Track") 
    async def track(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._handle_mode_change(
            interaction=interaction,
            new_mode=wavelink.QueueMode.loop,
            button_updates={'track': True, 'queue': False, 'disable': False},
            message="Looped the current track",
            icon_url="https://cdn.discordapp.com/emojis/1299819953649745942.webp?size=44&quality=lossless"
        )

    @discord.ui.button(label="Disable")
    async def disable(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._handle_mode_change(
            interaction=interaction, 
            new_mode=wavelink.QueueMode.normal,
            button_updates={'track': False, 'queue': False, 'disable': True},
            message="Disabled loop",
            icon_url=self.bot.user.display_avatar.url
        )

class FilterView(discord.ui.View):
    def __init__(self, player: Player):
        super().__init__(timeout=None)
        self.player: Player = player
        self.msg: Optional[discord.Message] = None
        self._active_filters: Set[str] = set()
        self._filter_lock = asyncio.Lock()
        self._last_filter_update = datetime.datetime.now()
        self._filter_cache: Dict[str, wavelink.Filters] = {}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.player or not self.player.channel:
            await interaction.response.send_message("Player is not connected", ephemeral=True)
            return False
            
        if interaction.user not in self.player.channel.members:
            await interaction.response.send_message("You are not in the voice channel", ephemeral=True)
            return False

        return True

    async def set_filter(
        self, 
        interaction: discord.Interaction, 
        filter_name: str, 
        filter_func: callable,
        retry_attempts: int = 3
    ) -> None:
        async with self._filter_lock:
            try:
                # Show applying message
                applying_embed = discord.Embed(color=0x2B2D31)
                applying_embed.set_author(
                    name=f"Applying {filter_name} Filter",
                    icon_url="https://cdn.discordapp.com/emojis/953706012806889503.gif?size=96&quality=lossless"
                )
                await interaction.response.edit_message(embed=applying_embed, view=self)

                # Check filter cache
                cache_key = f"{filter_name}_{self.player.guild.id}"
                if cache_key in self._filter_cache:
                    filters = self._filter_cache[cache_key]
                else:
                    filters = self.player.filters
                    filters.reset()
                    filter_func(filters)
                    self._filter_cache[cache_key] = filters

                # Apply filters with retries
                for attempt in range(retry_attempts):
                    try:
                        await self.player.set_filters(filters, seek=True)
                        break
                    except Exception as e:
                        if attempt == retry_attempts - 1:
                            raise e
                        await asyncio.sleep(1)

                # Update button states
                await self._update_filter_state(filter_name)
                
                # Show success message
                success_embed = discord.Embed(color=0x2B2D31)
                success_embed.set_author(
                    name=f"Applied {filter_name} Filter",
                    icon_url="https://cdn.discordapp.com/emojis/1172524936292741131.webp?size=96&quality=lossless"
                )
                await interaction.edit_original_response(embed=success_embed, view=self)

                # Update timestamp
                self._last_filter_update = datetime.datetime.now()

            except Exception as e:
                logger.error(f"Failed to apply filter {filter_name}: {str(e)}")
                error_embed = discord.Embed(color=discord.Color.red())
                error_embed.set_author(
                    name=f"Failed to apply {filter_name} filter",
                    icon_url="https://cdn.discordapp.com/emojis/1088142067305828372.webp?size=96&quality=lossless"
                )
                await interaction.edit_original_response(embed=error_embed, view=self)

    async def _update_filter_state(self, active_filter: str) -> None:
        """Update button states and active filters tracking"""
        for button in self.children:
            if not isinstance(button, discord.ui.Button):
                continue
                
            if button.label == "Reset Filters":
                continue
                
            if button.label == active_filter:
                button.style = discord.ButtonStyle.green
                self._active_filters.add(active_filter)
            else:
                button.style = discord.ButtonStyle.blurple
                self._active_filters.discard(button.label)

    def _create_filter_button(
        self,
        label: str,
        filter_func: callable,
        row: Optional[int] = None
    ) -> discord.ui.Button:
        """Factory method for creating filter buttons"""
        button = discord.ui.Button(
            label=label,
            style=discord.ButtonStyle.blurple,
            row=row
        )
        
        async def callback(interaction: discord.Interaction):
            await self.set_filter(interaction, label, filter_func)
            
        button.callback = callback
        return button

    def __init_subclass__(cls):
        # Initialize filter buttons
        cls.eight_d = property(lambda self: self._create_filter_button(
            "8D",
            lambda f: f.rotation.set(rotation_hz=0.5)
        ))

        cls.bass_boost = property(lambda self: self._create_filter_button(
            "Bass Boost",
            lambda f: f.equalizer.set(
                bands=[
                    {"band": i, "gain": max(-0.25 * i + 0.5, -0.5)} 
                    for i in range(10)
                ]
            )
        ))

        cls.china = property(lambda self: self._create_filter_button(
            "China",
            lambda f: f.timescale.set(speed=1.25, pitch=1.25)
        ))

        cls.chipmunk = property(lambda self: self._create_filter_button(
            "Chipmunk",
            lambda f: f.timescale.set(pitch=1.8)
        ))

        cls.darth_vader = property(lambda self: self._create_filter_button(
            "Darth Vader",
            lambda f: f.timescale.set(pitch=0.5)
        ))

        cls.karaoke = property(lambda self: self._create_filter_button(
            "Karaoke",
            lambda f: f.karaoke.set(
                level=1.0,
                mono_level=1.0,
                filter_band=220.0,
                filter_width=100.0
            )
        ))

        cls.nightcore = property(lambda self: self._create_filter_button(
            "Nightcore",
            lambda f: f.timescale.set(
                pitch=1.2,
                speed=1.1,
                rate=1
            )
        ))

        cls.party = property(lambda self: self._create_filter_button(
            "Party",
            lambda f: f.rotation.set(rotation_hz=1.0)
        ))

        cls.pitch = property(lambda self: self._create_filter_button(
            "Pitch",
            lambda f: f.timescale.set(pitch=1.5)
        ))

        cls.pop = property(lambda self: self._create_filter_button(
            "Pop",
            lambda f: f.equalizer.set(band=1, gain=0.3)
        ))

        cls.rate = property(lambda self: self._create_filter_button(
            "Rate",
            lambda f: f.timescale.set(rate=1.5)
        ))

        cls.slow_mo = property(lambda self: self._create_filter_button(
            "Slow Mo",
            lambda f: f.timescale.set(
                pitch=1.0,
                speed=0.75,
                rate=1
            )
        ))

        cls.soft = property(lambda self: self._create_filter_button(
            "Soft",
            lambda f: f.equalizer.set(band=1, gain=-0.3)
        ))

        cls.speed = property(lambda self: self._create_filter_button(
            "Speed",
            lambda f: f.timescale.set(speed=1.5)
        ))

        cls.tremolo = property(lambda self: self._create_filter_button(
            "Tremolo",
            lambda f: f.tremolo.set(
                depth=0.5,
                frequency=14.0
            )
        ))

        cls.vaporwave = property(lambda self: self._create_filter_button(
            "Vaporwave",
            lambda f: f.timescale.set(
                speed=0.8,
                pitch=0.8
            )
        ))

        cls.vibrato = property(lambda self: self._create_filter_button(
            "Vibrato",
            lambda f: f.vibrato.set(
                depth=0.5,
                frequency=14.0
            )
        ))

    @discord.ui.button(label="Reset Filters", style=discord.ButtonStyle.red)
    async def reset_filters(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ) -> None:
        await self.set_filter(
            interaction,
            "Reset Filters",
            lambda f: f.reset()
        )
        self._filter_cache.clear()
        self._active_filters.clear()

class VolumeView(discord.ui.View):
    def __init__(self, bot: Boult, player: Player):
        super().__init__(timeout=30)
        self.bot = bot
        self.player = player
        self.msg: discord.Message = None

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.msg.edit(view=self, delete_after=5)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user not in self.player.channel.members:
            return await interaction.response.send_message(
                "You are not in the voice channel", ephemeral=True
            )
        return True
    
    def get_volume_color(self, volume: int) -> discord.Color:
        green = max(0, 255 - (volume * 255 // 100))
        red = min(255, volume * 255 // 100)
        return discord.Color.from_rgb(red, green, 0)
    
    @discord.ui.button(emoji=emoji.voldown, style=discord.ButtonStyle.red)
    async def down(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.player
        vol = player.volume
        if vol <= 0:
            return await interaction.response.send_message(
                "Volume is already at minimum level", ephemeral=True
            )
        new_vol = max(10, vol - 10)
        await player.set_volume(new_vol)
        await self.msg.edit(
            embed=discord.Embed(
                description=f"Volume set to {new_vol}%",
                color=self.get_volume_color(new_vol),
            )
        )
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji=emoji.volup, style=discord.ButtonStyle.green)
    async def up(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.player
        vol = player.volume
        if vol >= 100:
            return await interaction.response.send_message(
                "Volume is already at maximum level", ephemeral=True
            )
        new_vol = min(100, vol + 10)
        await player.set_volume(new_vol)
        await self.msg.edit(
            embed=discord.Embed(
                description=f"Volume set to {new_vol}%",
                color=self.get_volume_color(new_vol),
            )
        )
        await interaction.response.edit_message(view=self)


class SingleTrackRemove(discord.ui.Button):
    def __init__(self, bot: Boult, message: discord.Message, player: Player, item: Playable):
        super().__init__(style=discord.ButtonStyle.red, label="Remove")
        self.bot = bot
        self.player = player
        self.item = item
        self.message = message

    async def callback(self, interaction: discord.Interaction):
        self.player.queue.remove(self.item)
        embed=discord.Embed(
                color=self.bot.config.color.color,
            ).set_author(
                name=f"Removed {self.item.title} from the queue", icon_url="https://cdn.discordapp.com/emojis/1172606399595937913.webp?size=44",
            )
        await interaction.response.edit_message(view=None, embed=embed, delete_after=5)

class TrackRemoveView(discord.ui.View):
    def __init__(self, bot: Boult, player: Player, items: list[Playable]):
        super().__init__(timeout=30)
        self.bot = bot
        self.player = player
        self.items = items
        self.message: discord.Message = None
        self.current_page = 0
        self.page_size = 23  # Max tracks per page
        self.total_pages = (len(items) + self.page_size - 1) // self.page_size
        if len(items) == 1:
            self.add_item(SingleTrackRemove(self.bot, self.message, self.player, self.items[0]))
        else:
            self.update_options()

    def update_options(self):
        """
        Update the menu with current page's tracks and navigation buttons.
        """
        # Filter out the currently playing track
        if self.player.playing:
            filtered_items = self.items
        else:
            self.items.pop(0)
            filtered_items = self.items

        start = self.current_page * self.page_size
        end = start + self.page_size
        track_options = [
            discord.SelectOption(
                label=f"{item.title[:50]} - {item.author[:50]}",
                value=item.uri
            )
            for item in filtered_items[start:end]
        ]

        if self.total_pages > 1:
            # Add navigation buttons
            if self.current_page > 0:
                track_options.insert(
                    0,
                    discord.SelectOption(
                        label="⬆️ Previous Tracks",
                        value="previous_tracks",
                        description="Go to the previous page",
                    )
                )
            if self.current_page < self.total_pages - 1:
                track_options.append(
                    discord.SelectOption(
                        label="⬇️ More Tracks",
                        value="more_tracks",
                        description="Go to the next page",
                    )
                )

        # Validate length and reset options
        if len(track_options) > 25:
            raise ValueError("Options count exceeds the limit of 25.")

        self.clear_items()
        self.add_item(TrackRemoveSelect(self.bot, self.player, self.items, track_options))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user not in self.player.channel.members:
            await interaction.response.send_message(
                "You are not in the voice channel", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        if self.message:
            await self.message.edit(view=None)

class TrackRemoveSelect(discord.ui.Select):
    def __init__(self, bot: Boult, player: Player, items: list[Playable], options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Select tracks to remove",
            min_values=1,
            max_values=len(options) if len(options) < 25 else 25,
            options=options,
        )
        self.bot = bot
        self.player = player
        self.items = items
        self._removal_cache = {}
        self._last_interaction = None
        self._lock = asyncio.Lock()

    async def _handle_navigation(self, interaction: discord.Interaction, direction: str) -> bool:
        """Handle pagination navigation"""
        if direction == "previous" and "previous_tracks" in self.values:
            self.view.current_page = max(0, self.view.current_page - 1)
            await self._refresh_view(interaction)
            return True
        elif direction == "next" and "more_tracks" in self.values:
            self.view.current_page = min(self.view.total_pages - 1, self.view.current_page + 1)
            await self._refresh_view(interaction)
            return True
        return False

    async def _refresh_view(self, interaction: discord.Interaction) -> None:
        """Refresh the view with updated options"""
        self.view.update_options()
        await interaction.response.edit_message(view=self.view)

    async def _process_track_removal(self, selected_uris: list[str]) -> tuple[list[str], int]:
        """Process track removal and return removal details"""
        removed_tracks = []
        removed_count = 0
        
        async with self._lock:
            queue_snapshot = self.player.queue._items.copy()
            for uri in selected_uris:
                cache_key = f"{self.player.guild_id}:{uri}"
                
                if cache_key in self._removal_cache:
                    continue
                    
                for item in queue_snapshot:
                    if item.uri == uri:
                        try:
                            self.player.queue.remove(item)
                            removed_count += 1
                            removed_tracks.append(
                                f"-# [{item.title}]({item.uri}) - {item.author}"
                            )
                            self._removal_cache[cache_key] = {
                                'timestamp': datetime.datetime.now(),
                                'track_info': {
                                    'title': item.title,
                                    'uri': item.uri,
                                    'author': item.author
                                }
                            }
                            break
                        except Exception as e:
                            logger.error(f"Failed to remove track {uri}: {str(e)}")
                            continue

        return removed_tracks, removed_count

    async def _create_removal_embed(self, removed_tracks: list[str], removed_count: int) -> discord.Embed:
        """Create embed for removal confirmation"""
        embed = discord.Embed(
            color=0x2B2D31,
            description="\n".join(removed_tracks) if removed_tracks else "No tracks were removed"
        )
        embed.set_author(
            name=f"Removed {removed_count} track{'s' if removed_count != 1 else ''} from the queue",
            icon_url="https://cdn.discordapp.com/emojis/1172606399595937913.webp?size=44"
        )
        if removed_count > 0:
            embed.set_footer(text=f"Queue length: {len(self.player.queue._items)}")
        return embed

    async def callback(self, interaction: discord.Interaction):
        try:
            current_time = datetime.datetime.now()
            if self._last_interaction and (current_time - self._last_interaction).total_seconds() < 1:
                await interaction.response.send_message("Please wait a moment before removing more tracks", ephemeral=True)
                return
            
            self._last_interaction = current_time

            # Handle navigation
            if await self._handle_navigation(interaction, "previous") or \
               await self._handle_navigation(interaction, "next"):
                return

            # Process track removal
            removed_tracks, removed_count = await self._process_track_removal(self.values)
            
            # Create and send response embed
            embed = await self._create_removal_embed(removed_tracks, removed_count)
            await interaction.response.edit_message(
                embed=embed,
                view=None,
                delete_after=15
            )

            # Cleanup old cache entries
            current_time = datetime.datetime.now()
            self._removal_cache = {
                k: v for k, v in self._removal_cache.items()
                if (current_time - v['timestamp']).total_seconds() < 3600
            }

        except Exception as e:
            logger.error(f"Error in track removal: {str(e)}")
            await interaction.response.send_message(
                "An error occurred while removing tracks",
                ephemeral=True
            )

class SearchEngine(discord.ui.View):
    def __init__(self, ctx: BoultContext):
        super().__init__(timeout=15)
        self.value = None
        self.ctx = ctx
        self.message: discord.Message = None
        self._last_button_press = {}
        self._button_cooldowns = {}
        self._search_history = []
        
    async def on_timeout(self):
        if self.value is None:
            self.value = "spsearch"
            await self._update_message(
                "Using spotify as search engine",
                "https://cdn.discordapp.com/emojis/1220247976354779156.webp?size=96&quality=lossless",
                delete_after=3
            )
        else:
            await self.message.delete()

    async def _update_message(self, name: str, icon_url: str, delete_after: Optional[int] = None) -> None:
        """Update message with new embed"""
        embed = discord.Embed(color=0x2B2D31)
        embed.set_author(name=name, icon_url=icon_url)
        
        if self._search_history:
            embed.add_field(
                name="Recent Searches",
                value="\n".join(f"• {search}" for search in self._search_history[-3:])
            )
            
        await self.message.edit(embed=embed, view=None if delete_after else self)
        if delete_after:
            await self.message.delete(delay=delete_after)

    async def _handle_button_press(
        self,
        interaction: discord.Interaction,
        engine: str,
        name: str,
        icon_url: str,
        cooldown: float = 1.0
    ) -> None:
        """Handle button press with cooldown and history tracking"""
        current_time = datetime.datetime.now()
        user_id = interaction.user.id
        
        if user_id in self._last_button_press:
            time_diff = (current_time - self._last_button_press[user_id]).total_seconds()
            if time_diff < self._button_cooldowns.get(user_id, cooldown):
                await interaction.response.send_message(
                    f"Please wait {cooldown - time_diff:.1f}s before switching again",
                    ephemeral=True
                )
                return

        self._last_button_press[user_id] = current_time
        self._button_cooldowns[user_id] = cooldown
        self.value = engine
        self._search_history.append(name)
        
        await self._update_message(name, icon_url)
        await interaction.response.edit_message(view=self)
        self.stop()
        await self.message.delete(delay=3)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message(
            "This interaction is not for you.", ephemeral=True
        )
        return False

    @discord.ui.button(emoji=emoji.spotify, style=discord.ButtonStyle.blurple)
    async def spsearch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_button_press(
            interaction,
            "spsearch",
            "Using spotify as search engine",
            "https://cdn.discordapp.com/emojis/1220247976354779156.webp?size=96&quality=lossless"
        )

    @discord.ui.button(emoji=emoji.youtube, style=discord.ButtonStyle.blurple)
    async def ytsearch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_button_press(
            interaction,
            "ytsearch",
            "Using youtube as search engine",
            "https://cdn.discordapp.com/emojis/1220247238169595924.webp?size=96&quality=lossless"
        )

    @discord.ui.button(emoji=emoji.soundcloud, style=discord.ButtonStyle.blurple)
    async def scsearch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_button_press(
            interaction,
            "scsearch",
            "Using soundcloud as search engine",
            "https://cdn.discordapp.com/emojis/1220248137268990063.webp?size=96&quality=lossless"
        )

    @discord.ui.button(emoji=emoji.jiosaavn, style=discord.ButtonStyle.blurple)
    async def jiosaavn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_button_press(
            interaction,
            "jssearch",
            "Using jiosaavn as search engine",
            "https://cdn.discordapp.com/emojis/1305942405849288855.webp?size=96&quality=lossless",
            cooldown=2.0
        )
        self.scsearch.disabled = True
        self.spsearch.disabled = True

class SearchTrackSelect(discord.ui.Select):
    def __init__(self, items: list):
        # Validate and process items before creating options
        processed_items = self._process_items(items[:20])
        super().__init__(
            placeholder="Select a track to queue",
            min_values=1,
            max_values=1,
            options=processed_items
        )
        self.bot: Optional[Boult] = None
        self.player: Optional[Player] = None 
        self.message: Optional[discord.Message] = None
        self.source: Optional[str] = None
        self._last_interaction: Optional[datetime.datetime] = None
        self._processing_lock = asyncio.Lock()
        self._cache = {}

    def _process_items(self, items: list) -> list[discord.SelectOption]:
        """Process and validate items for select options"""
        processed = []
        for item in items:
            try:
                # Validate required fields
                if not all(k in item for k in ("name", "value")):
                    continue
                    
                # Clean and truncate label
                label = truncate_string(
                    item["name"].strip(),
                    max_length=100,
                    suffix="..."
                )
                
                option = discord.SelectOption(
                    label=label,
                    value=item["value"],
                    description=f"Click to queue this track"
                )
                processed.append(option)
                
            except Exception as e:
                logger.error(f"Error processing select item: {e}")
                continue
                
        return processed

    async def _validate_state(self, interaction: discord.Interaction) -> bool:
        """Validate interaction state before processing"""
        if not self.player or not self.player.channel:
            await interaction.followup.send("No active player found", ephemeral=True)
            return False
            
        if interaction.user not in self.player.channel.members:
            await interaction.followup.send("You must be in the voice channel", ephemeral=True) 
            return False
            
        if self._last_interaction and (datetime.datetime.now() - self._last_interaction).total_seconds() < 1:
            await interaction.followup.send("Please wait before selecting another track", ephemeral=True)
            return False
            
        return True

    async def _fetch_and_process_track(self, query: str) -> Optional[wavelink.Playable]:
        """Fetch and process track from wavelink"""
        cache_key = f"{self.source}:{query}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        try:
            tracks = await wavelink.Playable.search(query, source=self.source)
            if not tracks:
                return None
                
            track = tracks[0]
            self._cache[cache_key] = track
            return track
            
        except Exception as e:
            logger.error(f"Error fetching track: {e}")
            return None

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        async with self._processing_lock:
            try:
                # Validate state
                if not await self._validate_state(interaction):
                    return
                    
                # Update state
                self._last_interaction = datetime.datetime.now()
                self.player.home = interaction.channel
                
                # Fetch and process track
                track = await self._fetch_and_process_track(self.values[0])
                if not track:
                    return await interaction.followup.send(
                        "Failed to fetch track information",
                        ephemeral=True
                    )
                
                # Set track metadata
                track.extras = wavelink.ExtrasNamespace({
                    "requester": interaction.user.id,
                    "requested_at": datetime.datetime.now().isoformat(),
                    "source_channel": interaction.channel_id
                })
                
                # Queue track
                await self.player.queue.put_wait(track)
                
                # Send confirmation
                embed = discord.Embed(
                    description=f"> [{track.title}]({track.uri})\n> by {track.author}",
                    color=self.bot.config.color.color
                )
                embed.set_author(
                    name="Added to queue",
                    icon_url=self.bot.user.display_avatar.url
                )
                embed.set_footer(
                    text=f"Requested by {interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url
                )
                
                await interaction.channel.send(
                    embed=embed,
                    delete_after=5
                )
                
                # Start playback if not already playing
                if not self.player.playing:
                    next_track = await self.player.queue.get_wait()
                    await self.player.play(next_track)
                    
            except Exception as e:
                logger.error(f"Error processing track selection: {e}")
                await interaction.followup.send(
                    "An error occurred while processing your selection",
                    ephemeral=True
                )


class AutoPlayView(discord.ui.View):
    def __init__(self, player: Player):
        super().__init__(timeout=30)
        self.player = player
        self.msg: Optional[discord.Message] = None
        self._last_update = datetime.datetime.now()
        self._update_lock = asyncio.Lock()
        self._initialize_buttons()

    def _initialize_buttons(self):
        """Initialize button states based on player autoplay mode"""
        is_enabled = self.player.autoplay == wavelink.AutoPlayMode.enabled
        self.enable.disabled = is_enabled
        self.disable.disabled = not is_enabled

    async def on_timeout(self):
        """Handle view timeout"""
        if self.msg:
            try:
                for item in self.children:
                    item.disabled = True
                await self.msg.edit(view=self)
                await asyncio.sleep(3)
                await self.msg.delete()
            except discord.NotFound:
                pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Validate interaction permissions"""
        if not self.player or not self.player.channel:
            await interaction.response.send_message(
                "No active player found",
                ephemeral=True
            )
            return False
            
        if interaction.user not in self.player.channel.members:
            await interaction.response.send_message(
                "You must be in the voice channel to use this control",
                ephemeral=True
            )
            return False
            
        time_since_last = (datetime.datetime.now() - self._last_update).total_seconds()
        if time_since_last < 1:
            await interaction.response.send_message(
                "Please wait before changing autoplay settings again",
                ephemeral=True
            )
            return False
            
        return True

    async def _update_autoplay_state(
        self,
        interaction: discord.Interaction,
        mode: wavelink.AutoPlayMode,
        message: str,
        button_pressed: discord.ui.Button
    ):
        """Update autoplay state and UI"""
        async with self._update_lock:
            try:
                self.player.autoplay = mode
                self._last_update = datetime.datetime.now()
                
                # Update button states
                button_pressed.disabled = True
                other_button = self.enable if button_pressed == self.disable else self.disable
                other_button.disabled = False
                
                # Update message
                embed = discord.Embed(color=0x2B2D31)
                embed.set_author(
                    name=message,
                    icon_url="https://cdn.discordapp.com/emojis/1172524936292741131.png"
                )
                
                await interaction.response.edit_message(view=self)
                await self.msg.edit(embed=embed)
                
            except Exception as e:
                logger.error(f"Error updating autoplay state: {e}")
                await interaction.response.send_message(
                    "Failed to update autoplay settings",
                    ephemeral=True
                )

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.green, disabled=True)
    async def enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_autoplay_state(
            interaction,
            wavelink.AutoPlayMode.enabled,
            "Autoplay is now enabled",
            button
        )

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.red, disabled=False)
    async def disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update_autoplay_state(
            interaction,
            wavelink.AutoPlayMode.partial,
            "Autoplay is now disabled",
            button
        )


class ErrorView(discord.ui.View):
    def __init__(self, bot: Boult):
        super().__init__(timeout=None)
        self.bot = bot
        self._error_count = 0
        self._last_retry = None
        self._retry_lock = asyncio.Lock()

    # @discord.ui.button(
    #     label="Support Server",
    #     style=discord.ButtonStyle.link,
    #     url="https://discord.gg/boult"
    # )
    # async def support(self, interaction: discord.Interaction, button: discord.ui.Button):
    #     pass

    @discord.ui.button(label="Try Again", style=discord.ButtonStyle.green)
    async def retry(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with self._retry_lock:
            try:
                # Validate player state
                if not interaction.guild.voice_client or not isinstance(
                    interaction.guild.voice_client, wavelink.Player
                ):
                    return await interaction.response.send_message(
                        "No active player found.",
                        ephemeral=True
                    )
                
                player: Player = interaction.guild.voice_client
                
                # Check queue
                if not player.queue:
                    return await interaction.response.send_message(
                        "No tracks in queue to retry.",
                        ephemeral=True
                    )
                
                # Rate limit retries
                if self._last_retry and (datetime.datetime.now() - self._last_retry).total_seconds() < 2:
                    return await interaction.response.send_message(
                        "Please wait before retrying again.",
                        ephemeral=True
                    )
                
                # Track retry attempts
                self._error_count += 1
                if self._error_count >= 3:
                    button.disabled = True
                    await interaction.message.edit(view=self)
                    return await interaction.response.send_message(
                        "Maximum retry attempts reached. Please try a different track.",
                        ephemeral=True
                    )
                
                # Attempt retry
                self._last_retry = datetime.datetime.now()
                await player.play(player.queue[0])
                
                await interaction.response.send_message(
                    f"Retrying track... (Attempt {self._error_count}/3)",
                    ephemeral=True
                )
                
            except Exception as e:
                logger.error(f"Error retrying track: {e}")
                await interaction.response.send_message(
                    "Failed to retry track. Please try again later.",
                    ephemeral=True
                )