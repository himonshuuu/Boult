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



from __future__ import annotations

from typing import (Any, Callable, Generic, List, NamedTuple, Optional,
                    TypeVar, Union)

import discord
from discord.ext.commands import Context

T = TypeVar("T")

class NodeView(discord.ui.View):
    def __init__(self, node_embed, plugins_embed):
        super().__init__(timeout=60)
        self.msg = None
        self.node_embed = node_embed
        self.plugins_embed = plugins_embed
        
    async def on_timeout(self) -> None:
        try:
            await self.msg.delete()
        except:
            pass

    @discord.ui.button(label="Node", style=discord.ButtonStyle.gray)
    async def node_info_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.edit_message(embed=self.node_embed)

    @discord.ui.button(label="Plugins", style=discord.ButtonStyle.gray)
    async def plugins_info_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.edit_message(embed=self.plugins_embed)



class Link(NamedTuple):
    name: Optional[str] = None
    url: Optional[str] = None
    emoji: Optional[str] = None


class LinkButton(discord.ui.View): 

    def __init__(self, links: Union[Link, List[Link]]):
        super().__init__()

        links = links if isinstance(links, list) else [links]

        for link in links:
            self.add_item(
                discord.ui.Button(label=link.name, url=link.url, emoji=link.emoji)
            )


class ConfirmationView(discord.ui.View):

    def __init__(self, *, timeout: float, author_id: int, delete_after: bool) -> None:
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self.delete_after: bool = delete_after
        self.author_id: int = author_id
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        else:
            await interaction.response.send_message(
                "This confirmation dialog is not for you.", ephemeral=True
            )
            return False

    async def on_timeout(self) -> None:
        if self.delete_after and self.message:
            await self.message.delete()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.value = True
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_response()

        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_response()
        self.stop()


class DisambiguatorView(discord.ui.View, Generic[T]):
    message: discord.Message
    selected: T

    def __init__(self, ctx: Context, data: list[T], entry: Callable[[T], Any]):
        super().__init__()
        self.ctx: Context = ctx
        self.data: list[T] = data

        options = []
        for i, x in enumerate(data):
            opt = entry(x)
            if not isinstance(opt, discord.SelectOption):
                opt = discord.SelectOption(label=str(opt))
            opt.value = str(i)
            options.append(opt)

        select = discord.ui.Select(options=options)

        select.callback = self.on_select_submit
        self.select = select
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "This select menu is not meant for you, sorry.", ephemeral=True
            )
            return False
        return True

    async def on_select_submit(self, interaction: discord.Interaction):
        index = int(self.select.values[0])
        self.selected = self.data[index]
        await interaction.response.defer()
        if not self.message.flags.ephemeral:
            await self.message.delete()

        self.stop()
