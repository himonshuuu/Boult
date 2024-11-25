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
from core import Cog, Boult
from discord.ext import commands
from core.player import Player
from utils import BoultContext
from typing import Literal, Optional


class Utility(Cog):
    """This cog provides utility functions and commands for the bot."""

    def __init__(self, bot: Boult):
        self.bot = bot

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(id=1257989664418168932, name="utility")

    @commands.hybrid_command(name="join", aliases=["connect"], with_app_command=True)
    # @in_voice_channel(user=True)
    async def join(self, ctx: BoultContext, channel: Optional[discord.VoiceChannel]):
        """
        Join a voice channel.

        If no channel is specified, it will join your current voice channel.
        """
        if ctx.interaction:
            await ctx.defer()

        if channel is None:
            channel = ctx.author.voice.channel
            if channel is None:
                return await ctx.send(
                    embed=discord.Embed(color=self.bot.config.color.color).set_author(
                        name="You are not connected to a voice channel",
                        icon_url=self.bot.user.display_avatar.url,
                    )
                )
            else:
                await ctx.author.voice.channel.connect(self_deaf=True, cls=Player)
                return await ctx.send(
                    embed=discord.Embed(color=self.bot.config.color.color).set_author(
                        name="Joined the voice channel",
                        icon_url=self.bot.user.display_avatar.url,
                    )
                )

        else:
            await channel.connect(self_deaf=True, cls=Player)
            return await ctx.send(
                embed=discord.Embed(color=self.bot.config.color.color).set_author(
                    name="Joined the voice channel",
                    icon_url=self.bot.user.display_avatar.url,
                )
            )

    @commands.hybrid_command(
        name="leave", aliases=["disconnect"], with_app_command=True
    )
    async def leave(self, ctx: BoultContext):
        """Leave the voice channel."""
        if ctx.interaction:
            await ctx.defer()

        if ctx.voice_client is None:
            return await ctx.send(
                embed=discord.Embed(color=self.bot.config.color.color).set_author(
                    name="Not connected to a voice channel",
                    icon_url=self.bot.user.display_avatar.url,
                )
            )

        else:
            await ctx.voice_client.disconnect()
            return await ctx.send(
                embed=discord.Embed(color=self.bot.config.color.color).set_author(
                    name="Left the voice channel",
                    icon_url=self.bot.user.display_avatar.url,
                )
            )

    @commands.hybrid_group(name="config", with_app_command=True)
    async def _config(self, ctx: BoultContext):
        """user configuration for the bot."""
        if ctx.interaction:
            await ctx.defer()

        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

        else:
            await ctx.send_help(ctx.command)

    @_config.command(name="prefix", with_app_command=True)
    @commands.has_permissions(administrator=True)
    async def prefix(self, ctx: BoultContext, prefix: Optional[str]):
        """Set the bot's prefix."""
        if ctx.interaction:
            await ctx.defer()
        if prefix is None:
            return await ctx.send(
                f"Current prefix: `{self.bot.config.bot.default_prefix}`"
            )
        else:
            await self.bot.db.execute(
                "UPDATE guild_config SET prefix = $1 WHERE guild_id = $2",
                prefix,
                ctx.guild.id,
            )
            await ctx.send(f"Set prefix to `{prefix}`")

    @_config.group(name="247", with_app_command=True, invoke_without_command=True)
    async def _247(self, ctx: BoultContext):
        """command for managing 24/7 mode."""
        await ctx.send(
            "Please specify a subcommand. Use `/247 enable` or `/247 disable`."
        )

    @_247.command(name="enable")
    async def _enable(self, ctx: BoultContext):
        """Enable 24/7 mode."""
        if ctx.interaction:
            await ctx.defer()
        data = await self.bot.db.fetch_one(
            "SELECT vc_channel FROM guild_config WHERE guild_id = $1", ctx.guild.id
        )

        if data is None:
            await self.bot.db.execute(
                "INSERT INTO guild_config (guild_id, prefix, vc_channel) VALUES ($1, $2, $3)",
                ctx.guild.id,
                self.bot.config.bot.default_prefix,
                0,
            )

        if ctx.voice_client is None:
            return await ctx.send(
                embed=discord.Embed(color=self.bot.config.color.color).set_author(
                    name="Not connected to a voice channel",
                    icon_url=self.bot.user.display_avatar.url,
                )
            )

        channel = ctx.voice_client.channel.id
        await self.bot.db.execute(
            "UPDATE guild_config SET vc_channel = $1 WHERE guild_id = $2",
            channel,
            ctx.guild.id,
        )

        embed = discord.Embed(color=self.bot.config.color.color)
        embed.description = f"Enabled 24/7 mode in <#{channel}>"
        await ctx.send(embed=embed)

    @_247.command(name="disable")
    async def _disable(self, ctx: BoultContext):
        """Disable 24/7 mode."""
        if ctx.interaction:
            await ctx.defer()
        data = await self.bot.db.fetch_one(
            "SELECT vc_channel FROM guild_config WHERE guild_id = $1", ctx.guild.id
        )

        if data is None or data.vc_channel == 0:
            return await ctx.send(
                embed=discord.Embed(color=self.bot.config.color.color).set_author(
                    name="24/7 mode is not enabled",
                    icon_url=self.bot.user.display_avatar.url,
                )
            )

        await self.bot.db.execute(
            "UPDATE guild_config SET vc_channel = $1 WHERE guild_id = $2",
            0,
            ctx.guild.id,
        )

        embed = discord.Embed(color=self.bot.config.color.color)
        embed.description = "Disabled 24/7 mode."
        await ctx.send(embed=embed)

    @_config.command(name="search", with_app_command=True)
    async def _search(
        self,
        ctx: BoultContext,
        search_engine: Literal[
            "spotify", "youtube", "soundcloud", "youtube-music", "jiosaavn", "none"
        ],
    ):
        """set search engine for the bot."""
        if ctx.interaction:
            await ctx.defer()

        u = await self.bot.db.fetch_one(
            "SELECT * FROM user_config WHERE user_id=$1", ctx.author.id
        )

        if search_engine == "youtube-music":
            s = "ytmsearch"
        if search_engine == "soundcloud":
            s = "scsearch"
        if search_engine == "youtube":
            s = "ytsearch"
        if search_engine == "spotify":
            s = "spsearch"
        if search_engine == "jiosaavn":
            s = "jssearch"
        if search_engine == "none":
            await self.bot.db.execute(
                "UPDATE user_config SET search_engine = $1 WHERE user_id = $2",
                None,
                ctx.author.id,
            )
            return await ctx.send(
                embed=discord.Embed(
                    color=self.bot.config.color.color,
                    description="When playing a song , the bot will prompt you to choose a search engine",
                )
            )

        if u is None:

            await self.bot.db.execute(
                "INSERT INTO user_config (user_id, search_engine) VALUES ($1, $2)",
                ctx.author.id,
                s,
            )
        else:
            await self.bot.db.execute(
                "UPDATE user_config SET search_engine = $1 WHERE user_id = $2",
                s,
                ctx.author.id,
            )
        await ctx.send(
            embed=discord.Embed(color=self.bot.config.color.color).set_author(
                name=f"Search engine set to {search_engine}",
                icon_url=self.bot.user.display_avatar.url,
            )
        )

    @_config.group(name="noprefix", aliases=["np"], hidden=True)
    @commands.is_owner()
    async def _noprefix(self, ctx: BoultContext):
        """command for managing no prefix mode."""
        pass

    @_noprefix.command(name="add", aliases=["a"], hidden=True)
    @commands.is_owner()
    async def _add(self, ctx: BoultContext, user: discord.User):
        """Add a user to the no prefix list."""
        d = await self.bot.db.fetch_one(
            "SELECT no_prefix FROM user_config WHERE user_id=$1", user.id
        )
        if d is None:
            await self.bot.db.execute(
                "INSERT INTO user_config (user_id, no_prefix) VALUES ($1, $2)",
                user.id,
                True,
            )
        else:
            await self.bot.db.execute(
                "UPDATE user_config SET no_prefix = $1 WHERE user_id = $2",
                True,
                user.id,
            )

        await ctx.send(
            embed=discord.Embed(color=self.bot.config.color.color).set_author(
                name=f"Added {user.mention} to the no prefix list",
                icon_url=self.bot.user.display_avatar.url,
            )
        )

    @_noprefix.command(name="remove", aliases=["r"], hidden=True)
    @commands.is_owner()
    async def _remove(self, ctx: BoultContext, user: discord.User):
        """Remove a user from the no prefix list."""
        d = await self.bot.db.fetch_one(
            "SELECT no_prefix FROM user_config WHERE user_id=$1", user.id
        )
        if d is None:
            await self.bot.db.execute(
                "INSERT INTO user_config (user_id, no_prefix) VALUES ($1, $2)",
                user.id,
                False,
            )
        else:
            await self.bot.db.execute(
                "UPDATE user_config SET no_prefix = $1 WHERE user_id = $2",
                False,
                user.id,
            )

        await ctx.send(
            embed=discord.Embed(color=self.bot.config.color.color).set_author(
                name=f"Removed {user.mention} from the no prefix list",
                icon_url=self.bot.user.display_avatar.url,
            )
        )
