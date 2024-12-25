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

from collections.abc import Mapping
from typing import Any, Callable, List, Optional

import discord
from discord.ext import commands
from discord.ui import Button, Select, View
from discord import utils

from extensions.context.context import BoultContext


class HelpPaginator(View):
    def __init__(
        self, embeds: List[discord.Embed], main_embed: discord.Embed, main_view: View
    ):
        super().__init__(timeout=120)
        self.embeds = embeds
        self.main_embed = main_embed
        self.main_view = main_view
        self.current_page = 0

        self.prev_button = Button(
            style=discord.ButtonStyle.secondary,
            emoji="◀️",
            custom_id="prev"
        )
        self.next_button = Button(
            style=discord.ButtonStyle.secondary, 
            emoji="▶️",
            custom_id="next"
        )
        self.home_button = Button(
            style=discord.ButtonStyle.success,
            emoji="🏠",
            custom_id="home"
        )

        self.prev_button.callback = self.go_previous
        self.next_button.callback = self.go_next
        self.home_button.callback = self.go_home

        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self.add_item(self.home_button)
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page <= 0
        self.next_button.disabled = self.current_page >= len(self.embeds) - 1

    async def go_previous(self, interaction: discord.Interaction):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page], view=self
        )

    async def go_next(self, interaction: discord.Interaction):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(
            embed=self.embeds[self.current_page], view=self
        )

    async def go_home(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=self.main_embed, view=self.main_view
        )


class HelpSelect(Select):
    def __init__(self, bot: commands.Bot, main_embed: discord.Embed, main_view: View):
        options = [
            discord.SelectOption(
                emoji=getattr(cog, "display_emoji", "📦"),
                label=cog_name,
                description=getattr(cog, "description", "No description provided")[:100],
            )
            for cog_name, cog in bot.cogs.items()
            if getattr(cog, "__cog_commands__", None)
            and cog_name not in ["Jishaku", "Help"]
        ]
        super().__init__(
            placeholder="Select a category to view commands...",
            options=options,
            custom_id="category_select"
        )
        self.bot = bot
        self.main_embed = main_embed
        self.main_view = main_view

    def flatten_commands(self, cog: commands.Cog) -> List[commands.Command]:
        flattened = []
        for command in cog.walk_commands():
            if not isinstance(command, commands.Group) and not command.hidden:
                flattened.append(command)
        return flattened

    async def callback(self, interaction: discord.Interaction):
        cog_name = self.values[0]
        cog = self.bot.get_cog(cog_name)

        if not cog:
            await interaction.response.send_message(
                "❌ Category not found.", ephemeral=True
            )
            return

        commands_list = self.flatten_commands(cog)
        embeds = []
        prefix = "b?"

        for i in range(0, len(commands_list), 3):
            commands_chunk = commands_list[i : i + 3]
            embed = discord.Embed(
                title=f"{getattr(cog, 'display_emoji', '📦')} {cog.__cog_name__} Commands",
                description=f"{cog.description or 'No description provided'}\n\n**Page {i // 3 + 1}/{(len(commands_list) + 2) // 3}**",
                color=0x2b2d31
            )

            for command in commands_chunk:
                usage = f"{prefix}{command.qualified_name} {command.signature}"
                aliases = ", ".join(f"`{a}`" for a in command.aliases) if command.aliases else "None"
                description = command.help or "No description provided"

                embed.add_field(
                    name=f"/{command.qualified_name}",
                    value=(
                        f"{description}\n"
                        f"**Prefix:** `{prefix}{command.qualified_name}`\n"
                        f"**Usage:** `{usage}`\n"
                        f"**Aliases:** {aliases}"
                    ),
                    inline=False,
                )

            embed.set_author(
                name=f"{self.bot.user.name} Help",
                icon_url=self.bot.user.display_avatar.url,
            )
            embed.set_footer(
                text=f"Requested by {interaction.user}",
                icon_url=interaction.user.display_avatar.url,
            )
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embeds.append(embed)

        paginator = HelpPaginator(
            embeds, main_embed=self.main_embed, main_view=self.main_view
        )
        await interaction.response.edit_message(embed=embeds[0], view=paginator)


class HelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__(
            command_attrs={
                "help": "Shows help about the bot, a command, or a category",
                "cooldown": commands.CooldownMapping.from_cooldown(1, 3, commands.BucketType.user),
                "name": "help",
            }
        )
        self.prefix = "b?"

    def flatten_commands(self, cog: commands.Cog) -> List[commands.Command]:
        flattened = []
        for command in cog.walk_commands():
            if not isinstance(command, commands.Group) and not command.hidden:
                flattened.append(command)
        return flattened

    async def command_callback(self, ctx: BoultContext, *, command: Optional[str] = None):
        if command:
            cmd = ctx.bot.get_command(command)
            if cmd:
                await self.send_command_help(cmd)
                return
            
            for cog_name, cog in ctx.bot.cogs.items():
                if cog_name.lower() == command.lower():
                    await self.send_cog_help(cog)
                    return
            
            await ctx.send(f'❌ No command or category called "{command}" found.')
            return

        await self.send_bot_help(self.get_bot_mapping())

    async def send_bot_help(
        self, mapping: Mapping[Optional[commands.Cog], list[commands.Command]]
    ):
        embed = discord.Embed(
            title="Bot Help",
            description=(
                f"👋 Hey {self.context.author.mention}! I'm {self.context.bot.user.name}\n"
                f"A feature-rich Discord bot with music, moderation and more!\n\n"
                f"**Quick Links**\n"
                f"• [Support Server](https://discord.gg/boult)\n"
                f"• [Invite Bot]({utils.oauth_url(self.context.bot.user.id)})\n\n"
                f"**Getting Started**\n"
                f"• Use the dropdown below to browse commands\n" 
                f"• Both slash (`/`) and prefix commands work\n"
                f"• Default prefix is `{self.prefix}`"
            ),
            color=0x2b2d31,
        )
        embed.set_author(
            name=f"{self.context.bot.user.name} Help",
            icon_url=self.context.bot.user.display_avatar.url,
        )
        embed.set_footer(
            text=f"Requested by {self.context.author}",
            icon_url=self.context.author.display_avatar.url,
        )
        embed.set_thumbnail(url=self.context.bot.user.display_avatar.url)

        view = View(timeout=180)
        help_select = HelpSelect(self.context.bot, main_embed=embed, main_view=view)
        view.add_item(help_select)

        await self.get_destination().send(embed=embed, view=view)

    async def send_command_help(self, command: commands.Command):
        embed = discord.Embed(
            color=0x2b2d31,
            title=f"Command: /{command.qualified_name}"
        )
        
        description = command.help or "No description provided"
        usage = f"{self.prefix}{command.qualified_name} {command.signature}"
        aliases = ", ".join(f"`{a}`" for a in command.aliases) if command.aliases else "None"
        
        embed.description = f"{description}"
        
        embed.add_field(
            name="Usage",
            value=f"{usage}",
            inline=False
        )
        
        if command.aliases:
            embed.add_field(
                name="Aliases", 
                value=aliases,
                inline=False
            )

        if isinstance(command, commands.Group):
            subcommands = []
            for subcmd in command.commands:
                if not subcmd.hidden:
                    subcommands.append(
                        f"• `/{subcmd.qualified_name}` - {subcmd.short_doc or 'No description'}"
                    )
            if subcommands:
                embed.add_field(
                    name="Subcommands",
                    value="\n".join(subcommands),
                    inline=False
                )

        embed.set_author(
            name=f"{self.context.bot.user.name} Help",
            icon_url=self.context.bot.user.display_avatar.url
        )
        embed.set_footer(
            text=f"Requested by {self.context.author}",
            icon_url=self.context.author.display_avatar.url
        )
        embed.set_thumbnail(url=self.context.bot.user.display_avatar.url)

        await self.get_destination().send(embed=embed)

    async def send_group_help(
        self, group: commands.Group[Any, Callable[..., Any], Any]
    ) -> None:
        embed = discord.Embed(
            title=f"Command Group: /{group.qualified_name}",
            description=f"{group.help or 'No description provided'}",
            color=0x2b2d31,
        )

        embed.set_author(
            name=f"{self.context.bot.user.name} Help",
            icon_url=self.context.bot.user.display_avatar.url,
        )
        embed.set_footer(
            text=f"Requested by {self.context.author}",
            icon_url=self.context.author.display_avatar.url,
        )
        embed.set_thumbnail(url=self.context.bot.user.display_avatar.url)

        commands_list = self.flatten_commands(group)
        if len(commands_list) <= 3:
            for cmd in commands_list:
                embed.add_field(
                    name=f"/{cmd.qualified_name}",
                    value=f"{cmd.short_doc or 'No description'}\n**Usage:** `{self.prefix}{cmd.qualified_name} {cmd.signature}`",
                    inline=False
                )
            await self.get_destination().send(embed=embed)
        else:
            embeds = []
            current_embed = embed.copy()

            for i, cmd in enumerate(commands_list, 1):
                current_embed.add_field(
                    name=f"/{cmd.qualified_name}",
                    value=f"{cmd.short_doc or 'No description'}\n**Usage:** `{self.prefix}{cmd.qualified_name} {cmd.signature}`",
                    inline=False
                )

                if i % 3 == 0 or i == len(commands_list):
                    embeds.append(current_embed)
                    current_embed = embed.copy()

            paginator = HelpPaginator(embeds=embeds, main_embed=embed, main_view=None)
            paginator.remove_item(paginator.home_button)
            await self.get_destination().send(embed=embeds[0], view=paginator)

    async def send_cog_help(self, cog: commands.Cog) -> None:
        embed = discord.Embed(
            title=f"{getattr(cog, 'display_emoji', '📦')} {cog.__cog_name__}",
            description=f"{cog.description or 'No description provided'}",
            color=0x2b2d31,
        )

        embed.set_author(
            name=f"{self.context.bot.user.name} Help",
            icon_url=self.context.bot.user.display_avatar.url,
        )
        embed.set_footer(
            text=f"Requested by {self.context.author}",
            icon_url=self.context.author.display_avatar.url,
        )
        embed.set_thumbnail(url=self.context.bot.user.display_avatar.url)

        commands_list = self.flatten_commands(cog)
        if len(commands_list) <= 3:
            for cmd in commands_list:
                embed.add_field(
                    name=f"/{cmd.qualified_name}",
                    value=f"{cmd.short_doc or 'No description'}\n**Usage:** `{self.prefix}{cmd.qualified_name} {cmd.signature}`",
                    inline=False
                )
            await self.get_destination().send(embed=embed)
        else:
            embeds = []
            current_embed = embed.copy()
            
            for i, cmd in enumerate(commands_list, 1):
                current_embed.add_field(
                    name=f"/{cmd.qualified_name}",
                    value=f"{cmd.short_doc or 'No description'}\n**Usage:** `{self.prefix}{cmd.qualified_name} {cmd.signature}`",
                    inline=False
                )

                if i % 3 == 0 or i == len(commands_list):
                    embeds.append(current_embed)
                    current_embed = embed.copy()

            paginator = HelpPaginator(embeds=embeds, main_embed=embed, main_view=None)
            paginator.remove_item(paginator.home_button)
            await self.get_destination().send(embed=embeds[0], view=paginator)
