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
import wavelink
from wavelink.tracks import Playable

from config import emoji
from core import Boult, Player
from utils import BoultContext
from utils.format import truncate_string


class MusicView(discord.ui.View):
    def __init__(self, bot: Boult, player: Player):
        super().__init__(timeout=None)
        self.bot = bot
        self.player = player

        if player.paused:
            self.play.emoji = emoji.pause
        else:
            self.play.emoji = emoji.play

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user not in self.player.channel.members:
            return await interaction.response.send_message(
                "You are not in the voice channel", ephemeral=True
            )

        return True
    
    @discord.ui.button(emoji=emoji.prev, row=1)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.previous(ctx=interaction)

    
    @discord.ui.button(emoji=emoji.pause, row=1)
    async def play(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.player

        if not player.paused:
            button.emoji = emoji.play
            await player.pause(True)
            await interaction.response.send_message("Paused", ephemeral=True)
        else:
            button.emoji = emoji.pause
            await player.pause(False)
            await interaction.response.send_message("Resumed", ephemeral=True)

        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji=emoji.stop, row=1)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.player
        await player.destroy()
        await interaction.response.send_message(
            "Stopped and cleared the queue", ephemeral=True
        )

    @discord.ui.button(emoji=emoji.next, row=1)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.player

        await player.next(ctx=interaction)

    # @discord.ui.button(emoji, row=1)


class LoopView(discord.ui.View):
    def __init__(self, bot: Boult, player: Player):
        super().__init__(timeout=30)
        self.bot: Boult = bot
        self.player: Player = player
        self.msg: discord.Message = None
        self.disable.disabled = True
        self.loop_mode : wavelink.QueueMode
        if player.queue.mode == wavelink.QueueMode.loop:
            self.track.disabled = True
            self.queue.disabled = False
        elif player.queue.mode == wavelink.QueueMode.loop_all:
            self.queue.disabled = True
            self.track.disabled = False

    async def on_timeout(self):
        await self.msg.delete()


    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user not in self.player.channel.members:
            return await interaction.response.send_message(
                "You are not in the voice channel", ephemeral=True
            )

        return True

    @discord.ui.button(label="Queue")
    async def queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.player
        player.queue.mode = wavelink.QueueMode.loop_all
        self.track.disabled = False
        self.queue.disabled = True
        self.disable.disabled = False

        embed = discord.Embed(color=self.bot.config.color.color)
        embed.set_author(
            name="Looped the queue",
            icon_url="https://cdn.discordapp.com/emojis/1299820129403670568.webp?size=44&quality=lossless",
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Track")
    async def track(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.player
        player.queue.mode = wavelink.QueueMode.loop
        self.queue.disabled = False
        self.track.disabled = True
        self.disable.disabled = False

        embed = discord.Embed(color=self.bot.config.color.color)
        embed.set_author(
            name="Looped the current track",
            icon_url="https://cdn.discordapp.com/emojis/1299819953649745942.webp?size=44&quality=lossless",
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Disable")
    async def disable(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        player = self.player
        player.queue.mode = wavelink.QueueMode.normal
        self.track.disabled = False
        self.queue.disabled = False
        self.disable.disabled = True

        embed = discord.Embed(color=self.bot.config.color.color)
        embed.set_author(
            name=f"Disabled loop", icon_url=self.bot.user.display_avatar.url
        )

        await interaction.response.edit_message(embed=embed, view=self)


class FilterView(discord.ui.View):
    def __init__(self, player: Player):
        super().__init__(timeout=None)
        self.player: Player = player
        self.msg: discord.Message = None
        self.active_filters = set()  # Track active filters

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user not in self.player.channel.members:
            return await interaction.response.send_message(
                "You are not in the voice channel", ephemeral=True
            )

        return True

    async def set_filter(
        self, interaction: discord.Interaction, filter_name: str, filter_func: callable
    ):
        # Show "Applying {filter_name} Filter" message
        embed = discord.Embed(color=0x2B2D31).set_author(
            name=f"Applying {filter_name} Filter",
            icon_url="https://cdn.discordapp.com/emojis/953706012806889503.gif?size=96&quality=lossless",
        )
        await interaction.response.edit_message(embed=embed, view=self)

        # Apply the filter
        filters = self.player.filters  # Get the current filters applied to the player
        filters.reset()  # Reset all filters first
        filter_func(filters)  # Apply the selected filter using the passed function

        await self.player.set_filters(
            filters, seek=True
        )  # Apply the updated filters to the player

        # Update buttons and show success message after filter is applied
        self.update_buttons(filter_name)

        # Update the message after the filter is applied
        embed = discord.Embed(color=0x2B2D31).set_author(
            name=f"Applied {filter_name} Filter",
            icon_url="https://cdn.discordapp.com/emojis/1172524936292741131.webp?size=96&quality=lossless",
        )
        await interaction.edit_original_response(embed=embed, view=self)

    def update_buttons(self, filter_name: str):
        """Update the button styles based on active filters."""
        for button in self.children:
            if button.label == "Reset Filters":
                continue
            if button.label == filter_name:
                button.style = (
                    discord.ButtonStyle.green
                )  # Turn the selected button green
                self.active_filters.add(filter_name)
            else:
                button.style = (
                    discord.ButtonStyle.blurple
                )  # Reset other buttons to default color
                self.active_filters.discard(filter_name)

    # Explicitly defining each filter button with their respective callback functions

    @discord.ui.button(label="8D", style=discord.ButtonStyle.blurple)
    async def eight_d(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.set_filter(
            interaction, "8D", lambda f: f.rotation.set(rotation_hz=0.5)
        )

    @discord.ui.button(label="Bass Boost", style=discord.ButtonStyle.blurple)
    async def bass_boost(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.set_filter(
            interaction,
            "Bass Boost",
            lambda f: f.equalizer.set(
                bands=[
                    {"band": 0, "gain": 0.6},
                    {"band": 1, "gain": 0.45},
                    {"band": 2, "gain": 0.3},
                    {"band": 3, "gain": 0.15},
                    {"band": 4, "gain": 0.0},
                    {"band": 5, "gain": -0.1},
                    {"band": 6, "gain": -0.2},
                    {"band": 7, "gain": -0.3},
                    {"band": 8, "gain": -0.4},
                    {"band": 9, "gain": -0.5},
                ]
            ),
        )

    @discord.ui.button(label="China", style=discord.ButtonStyle.blurple)
    async def china(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_filter(
            interaction, "China", lambda f: f.timescale.set(speed=1.25, pitch=1.25)
        )

    @discord.ui.button(label="Chipmunk", style=discord.ButtonStyle.blurple)
    async def chipmunk(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.set_filter(
            interaction, "Chipmunk", lambda f: f.timescale.set(pitch=1.8)
        )

    @discord.ui.button(label="Darth Vader", style=discord.ButtonStyle.blurple)
    async def darth_vader(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.set_filter(
            interaction, "Darth Vader", lambda f: f.timescale.set(pitch=0.5)
        )

    @discord.ui.button(label="Karaoke", style=discord.ButtonStyle.blurple)
    async def karaoke(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.set_filter(
            interaction,
            "Karaoke",
            lambda f: f.karaoke.set(
                level=1.0, mono_level=1.0, filter_band=220.0, filter_width=100.0
            ),
        )

    @discord.ui.button(label="Nightcore", style=discord.ButtonStyle.blurple)
    async def nightcore(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.set_filter(
            interaction,
            "Nightcore",
            lambda f: f.timescale.set(pitch=1.2, speed=1.1, rate=1),
        )

    @discord.ui.button(label="Party", style=discord.ButtonStyle.blurple)
    async def party(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_filter(
            interaction, "Party", lambda f: f.rotation.set(rotation_hz=1.0)
        )

    @discord.ui.button(label="Pitch", style=discord.ButtonStyle.blurple)
    async def pitch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_filter(
            interaction, "Pitch", lambda f: f.timescale.set(pitch=1.5)
        )

    @discord.ui.button(label="Pop", style=discord.ButtonStyle.blurple)
    async def pop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_filter(
            interaction, "Pop", lambda f: f.equalizer.set(band=1, gain=0.3)
        )

    @discord.ui.button(label="Rate", style=discord.ButtonStyle.blurple)
    async def rate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_filter(interaction, "Rate", lambda f: f.timescale.set(rate=1.5))

    @discord.ui.button(label="Slow Mo", style=discord.ButtonStyle.blurple)
    async def slow_mo(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.set_filter(
            interaction,
            "Slow Mo",
            lambda f: f.timescale.set(pitch=1.0, speed=0.75, rate=1),
        )

    @discord.ui.button(label="Soft", style=discord.ButtonStyle.blurple)
    async def soft(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_filter(
            interaction, "Soft", lambda f: f.equalizer.set(band=1, gain=-0.3)
        )

    @discord.ui.button(label="Speed", style=discord.ButtonStyle.blurple)
    async def speed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_filter(
            interaction, "Speed", lambda f: f.timescale.set(speed=1.5)
        )

    @discord.ui.button(label="Tremolo", style=discord.ButtonStyle.blurple)
    async def tremolo(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.set_filter(
            interaction, "Tremolo", lambda f: f.tremolo.set(depth=0.5, frequency=14.0)
        )

    @discord.ui.button(label="Vaporwave", style=discord.ButtonStyle.blurple)
    async def vaporwave(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.set_filter(
            interaction, "Vaporwave", lambda f: f.timescale.set(speed=0.8, pitch=0.8)
        )

    @discord.ui.button(label="Vibrato", style=discord.ButtonStyle.blurple)
    async def vibrato(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.set_filter(
            interaction, "Vibrato", lambda f: f.vibrato.set(depth=0.5, frequency=14.0)
        )

    @discord.ui.button(label="Reset Filters", style=discord.ButtonStyle.red)
    async def reset_filters(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.set_filter(interaction, "Reset Filters", lambda f: f.reset())


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

    async def callback(self, interaction: discord.Interaction):
        if "previous_tracks" in self.values:
            self.view.current_page -= 1
            self.view.update_options()
            await interaction.response.edit_message(view=self.view)
            return

        if "more_tracks" in self.values:
            self.view.current_page += 1
            self.view.update_options()
            await interaction.response.edit_message(view=self.view)
            return

        # Track removal logic
        removed_count = 0
        removed = []
        for selected_uri in self.values:
            for item in self.player.queue._items:
                if item.uri == selected_uri:
                    self.player.queue.remove(item)
                    removed_count += 1
                    removed.append(f"-# [{item.title}]({item.uri}) - {item.author}")
        
        await interaction.response.edit_message(
            embed=discord.Embed(
                color=0x2B2D31,
                description=f"{'\n'.join(removed)}"
            ).set_author(
                name=f"Removed {removed_count} tracks from the queue",
                icon_url="https://cdn.discordapp.com/emojis/1172606399595937913.webp?size=44",
            ),
            view=None,
            delete_after=15
        )          
            
class SearchEngine(discord.ui.View):
    def __init__(self, ctx: BoultContext):
        super().__init__(timeout=15)
        self.value = None
        self.ctx = ctx
        self.message: discord.Message = None
        
    async def on_timeout(self):
        if self.value is None:
            self.value = "spsearch"
            await self.message.edit(
                embed=discord.Embed(color=0x2B2D31).set_author(
                    name="Using spotify as search engine",
                    icon_url="https://cdn.discordapp.com/emojis/1220247976354779156.webp?size=96&quality=lossless",
                    view=None,
                ), delete_after=3
            )
        else:
            await self.message.delete()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.ctx.author.id:
            return True
        else:
            await interaction.response.send_message(
                "This interaction is not for you.", ephemeral=True
            )
            return False

    @discord.ui.button(emoji=emoji.spotify, style=discord.ButtonStyle.blurple)
    async def spsearch(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.value = "spsearch"
        
        await self.message.edit(
            embed=discord.Embed(
                color=0x2B2D31,
            ).set_author(
                name="Using spotify as search engine",
                icon_url="https://cdn.discordapp.com/emojis/1220247976354779156.webp?size=96&quality=lossless",
            )
        )
        await interaction.response.edit_message(view=self)
        self.stop()
        await self.message.delete(delay=3)

    @discord.ui.button(emoji=emoji.youtube, style=discord.ButtonStyle.blurple)
    async def ytsearch(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.value = "ytsearch"
        
        await self.message.edit(
            embed=discord.Embed(color=0x2B2D31).set_author(
                name="Using youtube as search engine",
                icon_url="https://cdn.discordapp.com/emojis/1220247238169595924.webp?size=96&quality=lossless",
            )
        )
        await interaction.response.edit_message(view=self)
        self.stop()
        await self.message.delete(delay=3)

    @discord.ui.button(emoji=emoji.soundcloud, style=discord.ButtonStyle.blurple)
    async def scsearch(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.value = "scsearch"
        
        await self.message.edit(
            embed=discord.Embed(color=0x2B2D31).set_author(
                name="Using soundcloud as search engine",
                icon_url="https://cdn.discordapp.com/emojis/1220248137268990063.webp?size=96&quality=lossless",
            )
        )
        await interaction.response.edit_message(view=self)
        self.stop()
        await self.message.delete(delay=3)

    @discord.ui.button(emoji=emoji.jiosaavn, style=discord.ButtonStyle.blurple)
    async def jiosaavn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.value = "jssearch"
        self.scsearch.disabled = True
        self.spsearch.disabled = True
        await self.message.edit(
            embed=discord.Embed(color=0x2B2D31).set_author(
                name="Using jiosaavn as search engine",
                icon_url="https://cdn.discordapp.com/emojis/1305942405849288855.webp?size=96&quality=lossless",
            )
        )
        await interaction.response.edit_message(view=self)
        self.stop()
        await self.message.delete(delay=3)


class SearchTrackSelect(discord.ui.Select):
    def __init__(self, items: list):
        super().__init__(
            placeholder="Select a track",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=truncate_string(item["name"], max_length=100, suffix=""),
                    value=item["value"],
                )
                for item in items[:20]
            ],
        )
        self.bot: Boult = None
        self.player: Player = None
        self.message: discord.Message = None
        self.source: str = None

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            if interaction.user not in self.player.channel.members:
                return await interaction.followup.send(
                    "You are not in the voice channel", ephemeral=True
                )
            if self.player is None:
                return await interaction.followup.send(
                    "Player is not connected", ephemeral=True
                )
            player = self.player
            player.home = interaction.channel
            tracks = await wavelink.Playable.search(self.values[0], source=self.source)

            track = tracks[0]

            track.extras = wavelink.ExtrasNamespace({"requester": interaction.user.id})

            await player.queue.put_wait(track)

            await interaction.channel.send(
                embed=discord.Embed(
                    description=f"> [{track.title}]({track.uri}) by {track.author}"
                ).set_author(
                    name="Enqueued track",
                    icon_url=self.bot.user.display_avatar.url,
                ),
                delete_after=5,
            )

            if not player.playing:
                track = await player.queue.get_wait()
                await player.play(track)

        except Exception as e:
            print(e)


class AutoPlayView(discord.ui.View):
    def __init__(self, player: Player):
        super().__init__(timeout=30)
        self.player = player
        self.msg: discord.Message = None
        if player.autoplay == wavelink.AutoPlayMode.enabled:
            self.enable.disabled = True
            self.disable.disabled = False
        else:
            self.enable.disabled = False
            self.disable.disabled = True

    async def on_timeout(self):
        if self.msg:
            await self.msg.delete()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user not in self.player.channel.members:
            await interaction.response.send_message(
                "You are not in the voice channel", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Enable", style=discord.ButtonStyle.green, disabled=True)
    async def enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        # await interaction.response.defer()
        self.player.autoplay = wavelink.AutoPlayMode.enabled
        button.disabled = True
        await interaction.response.edit_message(view=self)
        self.disable.disabled = False
        await self.msg.edit(
            embed=discord.Embed(
                color=0x2B2D31,
            ).set_author(
                name="Autoplay is now enabled",
                icon_url="https://cdn.discordapp.com/emojis/1172524936292741131.png",
            )
        )

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.red, disabled=False)
    async def disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        # await interaction.response.defer()
        self.player.autoplay = wavelink.AutoPlayMode.partial
        button.disabled = True
        self.enable.disabled = False
        await interaction.response.edit_message(view=self)
        await self.msg.edit(
            embed=discord.Embed(
                color=0x2B2D31,
            ).set_author(
                name="Autoplay is now disabled",
                icon_url="https://cdn.discordapp.com/emojis/1172524936292741131.png",
            )
        )
