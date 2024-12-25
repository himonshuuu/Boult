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




class Error(Cog):
    def __init__(self, bot: Boult):
        super().__init__(bot)

    @Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Handle command errors with logging and user feedback"""
        # Log the error with context
        self.bot.logger.error(
            f"Command error in {ctx.command} invoked by {ctx.author} (ID: {ctx.author.id})\n"
            f"Guild: {ctx.guild} (ID: {ctx.guild.id if ctx.guild else 'DM'})\n"
            f"Error: {error.__class__.__name__}: {str(error)}",
        )

        if isinstance(error, commands.CommandNotFound):
            return

        error_embed = discord.Embed(color=self.bot.color)
        error_embed.set_author(
            name="An error occurred",
            icon_url=self.bot.user.display_avatar.url
        )

        if isinstance(error, commands.MissingRequiredArgument):
            error_embed.description = f"Missing required argument: `{error.param.name}`"
            error_embed.set_footer(text=f"Tip: Use {ctx.prefix}help {ctx.command} to see proper usage")

        elif isinstance(error, commands.BadArgument):
            error_embed.description = f"Invalid argument provided: {str(error)}"
            error_embed.set_footer(text=f"Tip: Use {ctx.prefix}help {ctx.command} to see proper usage")

        elif isinstance(error, commands.MissingPermissions):
            error_embed.description = f"You're missing the following permissions:\n`{', '.join(error.missing_permissions)}`"

        elif isinstance(error, commands.BotMissingPermissions):
            error_embed.description = f"I'm missing the following permissions:\n`{', '.join(error.missing_permissions)}`"
            # Log critical permission issues
            self.bot.logger.warning(
                f"Missing permissions in {ctx.guild} (ID: {ctx.guild.id}): {', '.join(error.missing_permissions)}"
            )

        elif isinstance(error, commands.NotOwner):
            error_embed.description = "This command is restricted to bot owners only"

        elif isinstance(error, commands.CommandOnCooldown):
            error_embed.description = f"This command is on cooldown\nTry again in {error.retry_after:.1f}s"

        elif isinstance(error, commands.MaxConcurrencyReached):
            error_embed.description = f"This command is already running at maximum capacity\nPlease wait and try again"

        elif isinstance(error, commands.CommandError):
            error_embed.description = f"{str(error)}"

        try:
            await ctx.send(embed=error_embed)
            if hasattr(ctx, 'message') and ctx.message:
                await ctx.message.add_reaction('<:xsign:1172524698081427477>')
        except discord.HTTPException as e:
            pass

    @Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error):
        """Handle application command errors with logging and user feedback"""
        # Log the error with context
        self.bot.logger.error(
            f"App command error in {interaction.command.name} invoked by {interaction.user} (ID: {interaction.user.id})\n"
            f"Guild: {interaction.guild} (ID: {interaction.guild.id if interaction.guild else 'DM'})\n"
            f"Error: {error.__class__.__name__}: {str(error)}",
        )

        error_embed = discord.Embed(
            description=f"{str(error)}",
            color=self.bot.color
        )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except discord.HTTPException as e:
            self.bot.logger.error(f"Failed to send error message: {e}")

async def setup(bot: Boult):
    await bot.add_cog(Error(bot))