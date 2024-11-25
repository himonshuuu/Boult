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
from discord.ext import commands

from core import Boult, Cog
from utils.exceptions import (IncorrectChannelError, NoChannelProvided,
                              NoDJRole, NotBotInVoice, NotInVoice,
                              NotSameVoice)


class Error(Cog):

    def __init__(self, bot: Boult):
        self.bot = bot

    @Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandNotFound):
            return

        error_embed = discord.Embed(color=0x2b2d31)

        if isinstance(error, commands.MissingRequiredArgument):
            error_embed.author.name = f"Missing required argument: `{error.param.name}`"
        
        elif isinstance(error, commands.BadArgument):
            error_embed.author.name = f"Bad argument: `{error}`"

        elif isinstance(error, commands.MissingPermissions):
            error_embed.author.name = f"Missing permissions: `{', '.join(error.missing_permissions)}`"

        elif isinstance(error, commands.BotMissingPermissions):
            error_embed.author.name = f"Bot missing permissions: `{', '.join(error.missing_permissions)}`"

        elif isinstance(error, commands.NotOwner):
            error_embed.author.name = "You are not the owner of this bot."

        elif isinstance(error, commands.CommandOnCooldown):
            error_embed.author.name = f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds."

        elif isinstance(error, commands.MaxConcurrencyReached):
            error_embed.author.name = "Max concurrency reached. Try again later."

        elif isinstance(error, (NotInVoice, NotSameVoice, NoDJRole, NotBotInVoice, NoChannelProvided, IncorrectChannelError)):
            error_embed.author.name = str(error)

        else:
            return
        
        error_embed.author.icon_url = self.bot.user.display_avatar.url

        await ctx.send(embed=error_embed)

    @Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error):
        try:
            await interaction.response.send_message(
                embed=discord.Embed(description=f"An error occurred\n```{error}```")
            )
        except:
            await interaction.followup.send(
                embed=discord.Embed(description=f"An error occurred\n```{error}```")
            )
