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



from datetime import datetime

import discord
import wavelink

from utils.context import BoultContext


class Player(wavelink.Player):
    """
    wavelink.Player extended .
    """

    ctx: "BoultContext"
    home: discord.TextChannel | discord.VoiceChannel | discord.Thread
    message: discord.Message
    start_time: datetime

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.skip_votes = {}
        self.previous_votes = {}
        self.current_track_info = {}

    async def is_dj(self) -> bool:
        """Shortcut from ctx.is_dj."""
        return await self.ctx.is_dj()

    async def destroy(self) -> None:
        
        self.queue.clear()
        await self.stop()
        self.skip_votes = {}
        self.previous_votes = {}
        self.current_track_info = {}
        self.start_time = None

        await self.home.send(
            embed=discord.Embed(
                color=self.ctx.bot.config.color.color,
                description="Stopped the player",
            ).set_author(
                name="Stopped the player", icon_url=self.ctx.bot.user.display_avatar.url
            ),
            delete_after=15,
        )

    async def next(self, ctx: BoultContext | discord.Interaction) -> None:

        if self.queue.is_empty or len(self.queue._items) == 0:
            if isinstance(ctx, discord.Interaction):
                return await ctx.response.send_message(
                    content="-# </play:1310295137586384989> to add more songs",
                    embed=discord.Embed().set_author(
                        name="Queue empty",
                        icon_url=self.ctx.bot.user.display_avatar.url,
                    ), ephemeral=True
                )
            else:
                return await ctx.send(
                    content="-# </play:1310295137586384989> to add more songs",
                    embed=discord.Embed().set_author(
                        name="Queue empty",
                        icon_url=self.ctx.bot.user.display_avatar.url,
                    ), delete_after=10
                )
        if isinstance(ctx, discord.Interaction):
            if (
                ctx.user.guild_permissions.administrator
                or ctx.user.guild_permissions.ban_members
                or ctx.user.guild_permissions.manage_messages
                or ctx.user.guild_permissions.manage_channels
                or ctx.user.id == self.current.extras.requester
                or await self.is_dj()
            ):
                await self.home.send(
                    embed=discord.Embed(
                        color=self.ctx.bot.config.color.color,
                        description=f"> [{self.current.title}]({self.current.uri}) - {self.current.author}",
                    )
                    .set_footer(
                        text=f"{len(self.queue._items) -1} tracks in queue",
                    )
                    .set_author(
                        name="Skipped track",
                        icon_url=self.ctx.bot.user.display_avatar.url,
                    ), delete_after=15,
                )
                await self.stop()
                return

        if (
            ctx.author.guild_permissions.administrator
            or ctx.author.guild_permissions.ban_members
            or ctx.author.guild_permissions.manage_messages
            or ctx.author.guild_permissions.manage_channels
            or ctx.author.id == self.current.extras.requester
            or await self.is_dj()
        ):
            await self.home.send(
                embed=discord.Embed(
                    color=self.ctx.bot.config.color.color,
                    description=f"> [{self.current.title}]({self.current.uri}) - {self.current.author}",
                )
                .set_footer(
                    text=f"{len(self.queue._items) -1} tracks in queue",
                )
                .set_author(
                    name="Skipped track", icon_url=self.ctx.bot.user.display_avatar.url
                ),
                delete_after=15,
            )
            await self.stop()
            return

        guild_id = ctx.guild.id
        self.skip_votes.setdefault(guild_id, [])

        user_id = ctx.user.id if isinstance(ctx, discord.Interaction) else ctx.author.id

        if user_id in self.skip_votes[guild_id]:
            response = discord.Embed().set_author(
                name="Already voted to skip",
                icon_url=self.ctx.bot.user.display_avatar.url,
            )
            return await self._send_response(ctx, response)

        self.skip_votes[guild_id].append(user_id)

        total_votes = len(self.skip_votes[guild_id])
        real = [m for m in self.channel.members if not m.bot]
        needed_votes = len(real)

        if total_votes >= needed_votes:
            await self.home.send(
                embed=discord.Embed(
                    color=self.ctx.bot.config.color.color,
                    description=f"> [{self.current.title}]({self.current.uri}) - {self.current.author}",
                )
                .set_footer(
                    text=f"{len(self.queue._items)} tracks in queue",
                )
                .set_author(
                    name="Skipped track", icon_url=self.ctx.bot.user.display_avatar.url
                ),
                delete_after=15,
            )
            await self.stop()

            return

        vote_status = discord.Embed().set_author(
            name=f"Voted to skip. {total_votes}/{needed_votes} required",
            icon_url=self.ctx.bot.user.display_avatar.url,
        )
        await self._send_response(ctx, vote_status)

    async def previous(self, ctx: BoultContext | discord.Interaction) -> None:
        if not self.current:
            response = discord.Embed().set_author(
                name="No track is playing",
                icon_url=self.ctx.bot.user.display_avatar.url,
            )
            await self._send_response(ctx, response)
            return

        if self.queue.history.is_empty:
            response = discord.Embed().set_author(
                name="No previous tracks in history",
                icon_url=self.ctx.bot.user.display_avatar.url,
            )
            await self._send_response(ctx, response)
            return

        # Check if user has DJ permissions
        if isinstance(ctx, discord.Interaction):
            if (
                ctx.user.guild_permissions.administrator
                or ctx.user.guild_permissions.ban_members
                or ctx.user.guild_permissions.manage_messages
                or ctx.user.guild_permissions.manage_channels
                or ctx.user.id == self.current.extras.requester
                or await self.is_dj()
            ):
                track = self.queue.history.get()
                await self.play(track)
                await self._send_previous_message()
                return
        else:
            if (
                ctx.author.guild_permissions.administrator
                or ctx.author.guild_permissions.ban_members
                or ctx.author.guild_permissions.manage_messages
                or ctx.author.guild_permissions.manage_channels
                or ctx.author.id == self.current.extras.requester
                or await self.is_dj()
            ):
                track = self.queue.history.get()
                await self.play(track)
                await self._send_previous_message()
                return

        # Handle voting
        guild_id = ctx.guild.id
        self.previous_votes.setdefault(guild_id, [])

        user_id = ctx.user.id if isinstance(ctx, discord.Interaction) else ctx.author.id

        if user_id in self.previous_votes[guild_id]:
            response = discord.Embed().set_author(
                name="Already voted to play previous track",
                icon_url=self.ctx.bot.user.display_avatar.url,
            )
            return await self._send_response(ctx, response)

        self.previous_votes[guild_id].append(user_id)

        total_votes = len(self.previous_votes[guild_id])
        real = [m for m in self.channel.members if not m.bot]
        needed_votes = len(real)

        if total_votes >= needed_votes:
            track = self.queue.history.get()
            await self.play(track)
            await self._send_previous_message()
            self.previous_votes[guild_id] = []  # Reset votes after successful vote
            return

        vote_status = discord.Embed().set_author(
            name=f"Voted to play previous track. {total_votes}/{needed_votes} required",
            icon_url=self.ctx.bot.user.display_avatar.url,
        )
        await self._send_response(ctx, vote_status)

    async def _send_previous_message(self):
        """Helper method to send the previous track message."""
        await self.home.send(
            embed=discord.Embed(
                color=self.ctx.bot.config.color.color,
                description=f"> [{self.current.title}]({self.current.uri}) - {self.current.author}",
            )
            .set_footer(
                text=f"{len(self.queue._items)} tracks in queue",
            )
            .set_author(
                name="Playing previous track",
                icon_url=self.ctx.bot.user.display_avatar.url,
            ),
            delete_after=15,
        )

    async def _send_response(self, ctx, embed):
        if isinstance(ctx, discord.Interaction):
            await ctx.response.send_message(embed=embed)
        else:
            await ctx.send(embed=embed, delete_after=30)
