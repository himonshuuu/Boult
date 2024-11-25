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
import io
from contextlib import suppress
from functools import wraps
from typing import (TYPE_CHECKING, Any, Callable, Generic, List, Optional,
                    TypeVar, Union)

import discord
from asyncpg.pool import Pool
from discord.ext import commands

import config

if TYPE_CHECKING:
    from core import Boult
    from core import Player

from utils.buttons import ConfirmationView, DisambiguatorView

T = TypeVar("T")


class BoultContext(commands.Context["Boult"], Generic[T]):
    bot: "Boult"
    voice_client: 'Player["VoiceClient"]'
    author: discord.Member
    guild: discord.Guild

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.pool: Pool = self.bot.db.pool

    def __repr__(self) -> str:
        return f"<{self.__class__}>"

    @discord.utils.cached_property
    def replied_reference(self) -> Optional[discord.MessageReference]:
        ref = self.message.reference
        if ref and isinstance(ref.resolved, discord.Message):
            return ref.resolved.to_reference()
        return None

    @discord.utils.cached_property
    def replied_message(self) -> Optional[discord.Message]:
        ref = self.message.reference
        if ref and isinstance(ref.resolved, discord.Message):
            return ref.resolved
        return None

    async def send(
        self, content: Optional[str] = None, **kwargs: Any
    ) -> Optional[discord.Message]:
        perms: discord.Permissions = self.channel.permissions_for(self.me)
        if not (perms.send_messages and perms.embed_links):
            with suppress(discord.Forbidden):
                await self.author.send(
                    (
                        "Bot doesn't have either Embed Links or Send Messages permission in that channel. "
                        "Please give sufficient permissions to the bot."
                    )
                )
                return None

        embeds: Union[discord.Embed, List[discord.Embed]] = kwargs.get(
            "embed"
        ) or kwargs.get("embeds")

        def __set_embed_defaults(embed: discord.Embed):
            if not embed.color:
                embed.color = config.color.color

        if isinstance(embeds, (list, tuple)):
            for embed in embeds:
                if isinstance(embed, discord.Embed):
                    __set_embed_defaults(embed)
        else:
            if isinstance(embeds, discord.Embed):
                __set_embed_defaults(embeds)

        if self.interaction is not None:
            try:
                return await self.interaction.followup.send(
                    str(content)[:1990] if content else None, **kwargs
                )
            except discord.HTTPException:
                pass
        if self.interaction:
            await super().interaction.followup.send(
                str(content)[:1990] if content else None, **kwargs
                )
        return await super().send(str(content)[:1990] if content else None, **kwargs)

    async def error(
        self, message: str, delete_after: bool = None, **kwargs: Any
    ) -> Optional[discord.Message]:
        with suppress(discord.HTTPException):
            msg: Optional[discord.Message] = await self.reply(
                embed=discord.Embed(description=message, color=discord.Color.red()),
                delete_after=delete_after,
                **kwargs,
            )
            try:
                await self.bot.wait_for(
                    "message_delete",
                    check=lambda m: m.id == self.message.id,
                    timeout=30,
                )
            except asyncio.TimeoutError:
                pass
            else:
                if msg is not None:
                    await msg.delete(delay=0)
            finally:
                return msg

        return None

    async def confirm(
        self,
        message: str,
        *,
        timeout: float = 60.0,
        delete_after: bool = True,
        author_id: Optional[int] = None,
    ) -> Optional[bool]:
        author_id = author_id or self.author.id
        view = ConfirmationView(
            timeout=timeout,
            delete_after=delete_after,
            author_id=author_id,
        )
        view.message = await self.send(message, view=view, ephemeral=delete_after)
        await view.wait()
        return view.value
    
   
    def tick(self, opt: Optional[bool], label: Optional[str] = None) -> str:
        lookup = {
            True: "<:greentick:1172524936292741131>",
            False: "<:xsign:1172524698081427477>",
            None: "<:grey_tick:1310580954045218816>",
        }
        emoji = lookup.get(opt, "<:xsign:1172524698081427477>")
        if label is not None:
            return f"{emoji}: {label}"
        return emoji
    
    

    async def disambiguate(
        self, matches: List[T], entry: Callable[[T], Any], *, ephemeral: bool = False
    ) -> T:
        if len(matches) == 0:
            raise ValueError("No results found.")

        if len(matches) == 1:
            return matches[0]

        if len(matches) > 25:
            raise ValueError("Too many results... sorry.")

        view = DisambiguatorView(self, matches, entry)
        view.message = await self.send(
            "There are too many matches... Which one did you mean?",
            view=view,
            ephemeral=ephemeral,
        )
        await view.wait()
        return view.selected

    async def show_help(self, command: Any = None) -> None:
        """Shows the help command for the specified command if given.

        If no command is given, then it'll show help for the current
        command.
        """
        cmd = self.bot.get_command("help")
        command = command or self.command.qualified_name
        await self.invoke(cmd, command=command)  # type: ignore

    async def safe_send(
        self, content: str, *, escape_mentions: bool = True, **kwargs
    ) -> discord.Message:
        """Same as send except with some safeguards.

        1) If the message is too long then it sends a file with the results instead.
        2) If ``escape_mentions`` is ``True`` then it escapes mentions.
        """
        if escape_mentions:
            content = discord.utils.escape_mentions(content)

        if len(content) > 2000:
            fp = io.BytesIO(content.encode())
            kwargs.pop("file", None)
            return await self.send(
                file=discord.File(fp, filename="message_too_long.txt"), **kwargs
            )
        else:
            return await self.send(content)

    async def is_dj(self) -> bool:
        if (
            self.author.guild_permissions.administrator
            or self.author.guild_permissions.ban_members
            or self.author.guild_permissions.manage_messages
            or self.author.guild_permissions.manage_channels
        ):
            return True

        if (
            self.author.voice
            and self.author.voice.channel
            and len(self.author.voice.channel.members) < 3
            and self.voice_client
            and self.voice_client.channel == self.author.voice.channel
        ):
            return True

        query = "SELECT role_id FROM dj_config WHERE guild_id = $1"

        dj_role = await self.bot.db.fetch_one(query, self.guild.id)

        if dj_role is None:
            return True

        dj_role = self.guild.get_role(dj_role.role_id)
        return True if dj_role is None else dj_role in self.author.roles

    async def on_command_error(self, error: Exception) -> None:
        await self.error(f"```py\n{error}\n```")

    @staticmethod
    def dj_only():
        async def predicate(ctx: "BoultContext") -> bool:
            dj = await ctx.is_dj()
            if not dj:
                raise commands.CheckFailure("You must be a DJ to use this command.")
            return True

        return commands.check(predicate)

    @staticmethod
    def with_typing(func: Callable):
        @wraps(func)
        async def wrapped(*args, **kwargs) -> Optional[discord.Message]:
            context: "BoultContext" = (
                args[0] if isinstance(args[0], BoultContext) else args[1]
            )
            async with context.typing():
                return await func(*args, **kwargs)

        return wrapped


class GuildContext(BoultContext):
    author: discord.Member
    guild: discord.Guild
    channel: Union[discord.VoiceChannel, discord.TextChannel, discord.Thread]
    me: discord.Member
    prefix: str
