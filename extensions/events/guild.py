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



import re
import discord
from discord.ext import commands

from core import Boult, Cog
from utils.buttons import LinkButton, Link


class Guild(Cog):

    def __init__(self, bot: Boult):
        super().__init__(bot)

    @Cog.listener("on_guild_join")
    async def _on_guild_join(self, guild: discord.Guild):
        try:
            await self.bot.db.execute(
                "INSERT INTO guild_config (guild_id, prefix, vc_channel) VALUES ($1, $2, $3)",
                guild.id,
                self.bot.config.bot.default_prefix,
                0,
            )
        except:
            pass
        log = await self.bot.fetch_channel(self.bot.config.channels.join_log)
        embed = discord.Embed(
            title="Joined a new guild!",
            description=(
                f"**{guild.name}** ({guild.id})\n"
                f"Owner: {guild.owner.name} - {guild.owner.id}\n"
                f"Members: {guild.member_count}\n"
                f"Created: {guild.created_at.strftime('%b %d, %Y')}\n"
            ),
            color=self.bot.color,
        )
        try:
            invite = await guild.text_channels[0].create_invite(unique=True)
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label=guild.name, url=invite.url))
            await log.send(embed=embed, view=view)
        except:
            await log.send(embed=embed)

        # add a pettern for cheking chats like general, chats, check if channel names contains chat check every possible pattern and ignore emojis in channel name

        channel = discord.utils.get(guild.text_channels, name="general")
        if not channel:
            channels = [
                channel
                for channel in guild.text_channels
                if channel.permissions_for(guild.me).send_messages
                if re.search(r"\bchat\b", channel.name.lower()).group(1)
            ]
            channel = channels[0]

        view = discord.ui.View()
        view.add_item(LinkButton(links=[
            Link(name="Invite", url=self.bot.config.bot.invite_link),
            Link(name="Support", url=self.bot.config.bot.support_invite)
            ]
        ))
        await channel.send(
            embed=discord.Embed(
                description=(
                    "Hey there! I'm Boult, your friendly music bot.\n"
                    "To get started, type `>help` to see all the commands I have to offer.\n"
                    "If you need any assistance, feel free to ask in our support server.\n"
                ),
                color=self.bot.color,
            )
        )


    @Cog.listener("on_guild_remove")
    async def _on_guild_remove(self, guild: discord.Guild):
        log = await self.bot.fetch_channel(self.bot.config.channels.leave_log)
        embed = discord.Embed(
            title="Left a guild!",
            description=f"**{guild.name}** ({guild.id})\n",
            color=self.bot.color,
        )
        await log.send(embed=embed)
        try:
            await self.bot.db.execute(
                "DELETE FROM guild_config WHERE guild_id = $1", guild.id
            )
        except:
            pass

        try:
            owner = await self.bot.fetch_user(guild.owner_id)
            await owner.send(
                embed=discord.Embed(
                    title="Sorry to see you go!",
                    description=(
                        "I'm sorry to see you go, but I understand that sometimes it's for the best.\n"
                        "If you have any feedback, please let me know. I'm always looking to improve."
                    ),
                    color=self.bot.color,
                ),
                view=discord.ui.View().add_item(
                    discord.ui.Button(
                        label="Support Server", url=self.bot.config.support_invite
                    )
                ),
            )
        except:
            pass

async def setup(bot: Boult):
    await bot.add_cog(Guild(bot))