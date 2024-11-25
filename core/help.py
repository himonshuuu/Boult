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

from utils.context import BoultContext


class HelpPaginator(View):
    def __init__(
        self, embeds: List[discord.Embed], main_embed: discord.Embed, main_view: View
    ):
        super().__init__(timeout=120)
        self.embeds = embeds
        self.main_embed = main_embed
        self.main_view = main_view
        self.current_page = 0

        self.prev_button = Button(label="Previous", style=discord.ButtonStyle.blurple)
        self.next_button = Button(label="Next", style=discord.ButtonStyle.blurple)
        self.home_button = Button(label="Home", style=discord.ButtonStyle.green)

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
                emoji=getattr(cog, "display_emoji", None),
                label=cog_name,
                description=getattr(cog, "description", "No description provided"),
            )
            for cog_name, cog in bot.cogs.items()
            if getattr(cog, "__cog_commands__", None)
            and cog_name not in ["Jishaku", "Help"]
        ]
        super().__init__(placeholder="Choose a category", options=options)
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
                "Category not found.", ephemeral=True
            )
            return

        commands_list = self.flatten_commands(cog)
        embeds = []
        prefix = "b?"  # You might want to get this dynamically

        for i in range(0, len(commands_list), 3):
            commands_chunk = commands_list[i : i + 3]
            embed = discord.Embed(
                title=f"{cog.__cog_name__} Commands - Page {i // 3 + 1}", color=0x2b2d31
            )

            for command in commands_chunk:
                usage = f"{prefix}{command.qualified_name} {' '.join(f'<{param}>' for param in command.clean_params.keys())}"
                aliases = ", ".join(command.aliases) if command.aliases else "None"
                description = command.help or "No description provided"

                embed.add_field(
                    name=f"**{prefix}{command.qualified_name}**",
                    value=f"> {description}\n"
                    f"> **Aliases:** {aliases}\n"
                    f"> **Usage:** `{usage}`",
                    inline=False,
                )

            embed.set_author(
                name=f"{self.bot.user.name}'s Help Menu",
                icon_url=self.bot.user.display_avatar.url,
            )
            embed.set_footer(
                text=f"Requested by {interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )
            embeds.append(embed)

        paginator = HelpPaginator(
            embeds, main_embed=self.main_embed, main_view=self.main_view
        )
        await interaction.response.edit_message(embed=embeds[0], view=paginator)


class HelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__(
            command_attrs={
                "help": "Show help about the bot, a command, or a cog.",
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

    async def command_callback(self, ctx: BoultContext, *, command: Optional[str] = None): # NOT RECOMMENDED :)
        if command:
            cmd = ctx.bot.get_command(command)
            if cmd:
                await self.send_command_help(cmd)
                return
            
            for cog_name, cog in ctx.bot.cogs.items():
                if cog_name.lower() == command.lower():
                    await self.send_cog_help(cog)
                    return
            
            await ctx.send(f'No command or category called "{command}" found.')
            return

        await self.send_bot_help(self.get_bot_mapping())

    async def send_bot_help(
        self, mapping: Mapping[Optional[commands.Cog], list[commands.Command]]
    ):
        embed = discord.Embed(
            description=f"Hey {self.context.author.mention}! I'm {self.context.bot.user.name}\n"
            f"A decent music bot with some cool features\n\n"
            f"To get more info use the dropdown menu below",
            color=0x2b2d31,
        )
        embed.set_author(
            name=f"{self.context.bot.user.name}'s Help Menu",
            icon_url=self.context.bot.user.display_avatar.url,
        )
        embed.set_footer(
            text=f"Requested by {self.context.author.name}",
            icon_url=self.context.author.display_avatar.url,
        )
        embed.set_thumbnail(url=self.context.bot.user.display_avatar.url)

        view = View()
        help_select = HelpSelect(self.context.bot, main_embed=embed, main_view=view)
        view.add_item(help_select)

        await self.get_destination().send(embed=embed, view=view)

    async def send_command_help(self, command: commands.Command):
        aliases = ", ".join(command.aliases) if command.aliases else "None"
        description = command.help or "No description provided"
        usage = f"{self.prefix}{command.qualified_name} {command.signature}"

        embed = discord.Embed(
            title=f"Command: {self.prefix}{command.qualified_name}",
            description=f"> {description}\n"
            f"> **Aliases:** {aliases}\n"
            f"> **Usage:** `{usage}`",
            color=0x2b2d31,
        )

        if isinstance(command, commands.Group):
            for subcommand in command.commands:
                if not subcommand.hidden:
                    embed.add_field(
                        name=f"{self.prefix}{subcommand.qualified_name}",
                        value=(
                            f"> {subcommand.short_doc or 'No description provided'}\n"
                            f"> **Usage:** `{self.prefix}{subcommand.qualified_name} {' '.join(f'<{param}>' for param in subcommand.clean_params.keys())}`"
                            f"> **Aliases:** {', '.join(subcommand.aliases) if subcommand.aliases else 'None'}"
                        ),
                        inline=False,
                    )

        embed.set_author(
            name=self.context.bot.user.name,
            icon_url=self.context.bot.user.display_avatar.url,
        )
        embed.set_footer(
            text=f"Requested by {self.context.author.name}",
            icon_url=self.context.author.display_avatar.url,
        )

        await self.get_destination().send(embed=embed)

    async def send_group_help(
        self, group: commands.Group[Any, Callable[..., Any], Any]
    ) -> None:
        embed = discord.Embed(
            title=f"Command: {self.prefix}{group.qualified_name}",
            description=f"> {group.help or 'No description provided'}\n",
            color=0x2b2d31,
        )

        embed.set_author(
            name=self.context.bot.user.name,
            icon_url=self.context.bot.user.display_avatar.url,
        )

        embed.set_footer(
            text=f"Requested by {self.context.author.name}",
            icon_url=self.context.author.display_avatar.url,
        )

        commands_list = self.flatten_commands(group)
        if len(commands_list) <= 3:
            subcommands = ", ".join(f"`{c.name}`" for c in commands_list)
            if subcommands:
                embed.add_field(name="Subcommands", value=subcommands, inline=False)
            await self.get_destination().send(embed=embed)
        else:
            embeds = []
            current_embed = embed.copy()

            for i, cmd in enumerate(commands_list, 1):
                aliases = ", ".join(cmd.aliases) if cmd.aliases else "None"
                description = cmd.help or "No description provided"
                usage = f"{self.prefix}{cmd.qualified_name} {cmd.signature}"

                current_embed.add_field(
                    name=f"{cmd.name}",
                    value=(
                        f"> {cmd.help or 'No description provided'}\n"
                        f"> **Aliases:** {aliases}\n"
                        f"> **Usage:** `{usage}`"
                    ),
                    inline=False,
                )

                if i % 3 == 0 or i == len(commands_list):
                    embeds.append(current_embed)
                    current_embed = embed.copy()

            paginator = HelpPaginator(embeds=embeds, main_embed=embed, main_view=None)
            paginator.remove_item(paginator.home_button)
            await self.get_destination().send(embed=embeds[0], view=paginator)

    async def send_cog_help(self, cog: commands.Cog) -> None:
        embed = discord.Embed(
            title=f"Cog: {cog.__cog_name__}",
            description=f"> {cog.description or 'No description provided'}\n",
            color=0x2b2d31,
        )

        embed.set_author(
            name=self.context.bot.user.name,
            icon_url=self.context.bot.user.display_avatar.url,
        )

        embed.set_footer(
            text=f"Requested by {self.context.author.name}",
            icon_url=self.context.author.display_avatar.url,
        )

        commands_list = self.flatten_commands(cog)
        if len(commands_list) <= 3:
            commands = ", ".join(f"> `{c.qualified_name}`" for c in commands_list)
            if commands:
                embed.add_field(name="Commands", value=commands, inline=False)
            await self.get_destination().send(embed=embed)
        else:
            embeds = []
            current_embed = embed.copy()
            
            for i, command in enumerate(commands_list, 1):
                aliases = ", ".join(command.aliases) if command.aliases else "None"
                description = command.short_doc or "No description provided"
                usage = f"{self.prefix}{command.qualified_name} {' '.join(f'<{param}>' for param in command.clean_params.keys())}"

                current_embed.add_field(
                    name=f"> {self.prefix}{command.qualified_name}",
                    value=(
                        f"> {description}\n"
                        f"> **Aliases:** {aliases}\n"
                        f"> **Usage:** `{usage}`"
                    ),
                    inline=False,
                )

                if i % 3 == 0 or i == len(commands_list):
                    embeds.append(current_embed)
                    current_embed = embed.copy()

            paginator = HelpPaginator(embeds=embeds, main_embed=embed, main_view=None)
            paginator.remove_item(paginator.home_button)
            await self.get_destination().send(embed=embeds[0], view=paginator)
