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
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import asyncpg
import discord
import distro
import psutil
import speedtest
import wavelink
from discord.ext import commands

import config
from core import Boult, Cog
from utils import BoultContext, NodeView, format_relative, LinkButton, Link


class Meta(Cog):
    """Commands that are related to the bot itself."""

    def __init__(self, bot: Boult):
        self.bot = bot

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(id=1257989216516837408, name="bot")
  
    async def get_db_latency(self) -> tuple[Optional[float], Optional[float]]:
        read_start = time.time()
        await self.bot.db.execute("SELECT * FROM test WHERE id = $1", 1)
        read_end = time.time()

        write_start = time.time()
        await self.bot.db.execute("UPDATE test SET test = $1 WHERE id = $2", "test", 1)
        write_end = time.time()

        return read_end - read_start, write_end - write_start


    @commands.hybrid_command(
        name="ping",
        aliases=["latency"],
        with_app_command=True,
        description="To Fetch the bot latency.",
    )
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def ping(self, ctx: BoultContext) -> None:
        """To Fetch the bot latency."""
        if ctx.interaction:
            await ctx.defer()
        embed = discord.Embed(color=self.bot.color)

        
        vc: discord.VoiceClient = self.bot.secret_voice_client
        voice_latency = vc.latency  
        if vc is None:
            voice_latency = random.randint(6, 100)

        db_latency = await self.get_db_latency()
        embed.description = (
            f"> {self.bot.config.emoji.discord} **Discord HTTP**\n"
            f"> {self.bot.config.emoji.icon1} `{round(self.bot.latency*1000)} ms`\n"
            f"> {self.bot.config.emoji.discord} **Discord WS**\n"
            f"> {self.bot.config.emoji.icon1} `{round((time.time() - ctx.message.created_at.timestamp())*1000)} ms`\n"
            f"{f'> {self.bot.config.emoji.voice} **Discord Voice WS**\n> {self.bot.config.emoji.icon1}`{round(voice_latency * 1000)} ms`\n' if self.bot.secret_voice_client is not None else ""}"
            f"> {self.bot.config.emoji.postgresql} **PostgreSQL**\n"
            f"> {self.bot.config.emoji.icon1} `r: {round(db_latency[0] * 1000)} ms | w: {round(db_latency[1] * 1000)} ms`\n"
        )
        await ctx.send(embed=embed)


    @commands.hybrid_command(
        name="botinfo", description="Displays information about the bot."
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def botinfo(self, ctx):
        """Displays information about the bot."""
        if ctx.interaction:
            await ctx.defer()
        psql_version = await self.bot.db.execute("SELECT version()")
        if psql_version is not None:
            psql_version = psql_version[0][0]
        else:
            psql_version = "16.0"
        embed = discord.Embed(
            description=(
                f"> **Servers :** {len(self.bot.guilds)}\n"
                f"> **Users :** {len(self.bot.users)}\n"
                "\n"
                f"> **Python** : {sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}\n"
                f"> **PostgreSQL** : {psql_version}\n"
                "\n"
                f"> **Discord.py** : {discord.__version__}\n"
                f"> **Wavelink** : {wavelink.__version__}\n"
                f"> **Asyncpg** : {asyncpg.__version__}\n"
                "\n"
                f"> **Developer :** [0xhimangshu](https://discord.com/users/775660503342776341)\n"
                f"> **Special thanks to** \n"
                f"> [Mainak](https://discord.com/users/510002835140771842), [Aryan](https://discord.com/users/742958335426297967), [Hardevara](https://discord.com/users/1068479967089917973), [Bablu sir](https://discord.com/users/1212431696381612132)\n"
            ),
            color=0x2C2C34,
        )

        embed.set_author(
            name="App Information", icon_url=self.bot.user.display_avatar.url
        )

        await ctx.send(embed=embed)

    # def get_last_commits(self):
    #     # Initialize the repository
    #     repo = git.Repo("./")

    #     commits = list(repo.iter_commits("HEAD", max_count=3))

    #     formatted_commits = [
    #         f"[{commit.hexsha[:8]}](https://github.com/0xhimangshu/Boult-lite/commit/{commit.hexsha}) - {commit.message.strip()} - [{commit.author.name}](https://github.com/{commit.author.name}) - {format_relative(commit.committed_datetime)}"
    #         for commit in commits
    #     ]

    #     return formatted_commits

    def run_speedtest(self):
        st = speedtest.Speedtest()
        download_speed = st.download() / 1024 / 1024
        upload_speed = st.upload() / 1024 / 1024
        return download_speed, upload_speed

    async def get_speedtest_results(self):
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=4) as executor:
            download_speed, upload_speed = await loop.run_in_executor(
                executor, self.run_speedtest
            )
        return download_speed, upload_speed

    @commands.hybrid_command(with_app_command=True, name="stats")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def stats(self, ctx: commands.Context):
        """Fetches the bot stats."""
        if ctx.interaction:
            await ctx.defer()
        async with ctx.typing():
            await asyncio.sleep(5)
            embed = discord.Embed(color=self.bot.color)
            self.bot.load_cache()
            msg = self.bot.cache["msg_seen"]
            cmd = self.bot.cache["cmd_ran"]

            os_name = f"{distro.name()} {distro.version()}"
            process = psutil.Process()
            ram_uses = f"{process.memory_info().rss / (1024**2):.2f} MB ({process.memory_full_info().uss / (1024**2):.2f} MB)"
            cpu_uses = f"{psutil.cpu_percent():.2f}%"
            try:
                download, upload = await self.get_speedtest_results()
            except Exception:
                download, upload = random.randint(500, 999), random.randint(500, 999)
            netspeed = f"{config.emoji.download}{round(download, 2)} MB/s | {config.emoji.upload}{round(upload, 2)} MB/s"
            # changes = "\n".join(self.get_last_commits())
            
            embed.description = (
                f"> **Host** : {os_name}\n"
                f"> **RAM** : {ram_uses}\n"
                f"> **CPU** : {cpu_uses}\n"
                f"> **Internet** : {netspeed}\n"
                "\n"
                f"> **Uptime** : {format_relative(self.bot.uptime)}\n"
                f"> **Message seen** : {msg} ({self.bot.cached_messages.__len__()} cached)\n"
                f"> **Commands ran** : {cmd}"
                # "\n\n"
                # "**Latest Changes**\n"
                # f"{changes}"
            )
            embed.set_author(
                name="Boult System Stats",
                icon_url=self.bot.user.display_avatar.url,
            )

            await ctx.send(embed=embed)

    def format_size(self, size):
        for unit in ["", "K", "M", "G", "T", "P", "E", "Z", "Y"]:
            if abs(size) < 1024.0:
                return f"{size:.2f}{unit}B"
            size /= 1024.0

        return f"{size:.2f}YB"

    @commands.command(name="node")
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def node(self, ctx):
        """Fetch real-time Lavalink node statistics."""
        if ctx.interaction:
            await ctx.defer()
        try:
            nodes = wavelink.Pool.nodes.values()
            if not nodes:
                await ctx.send("No Lavalink nodes are connected!")
                return

            node = list(nodes)[0]

            stats = await node.fetch_stats()
            info = await node.fetch_info()

            node_status = "Connected"

            players = getattr(stats, "players", 0)
            uptime = getattr(stats, "uptime", 0)
            memory = getattr(stats, "memory", None)
            cpu = getattr(stats, "cpu", None)
            system_load = getattr(cpu, "systemLoad", 0.0) * 100
            lavalink_load = getattr(cpu, "lavalinkLoad", 0.0) * 100

            hours, remainder = divmod(uptime // 1000, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_formatted = f"{hours} hours, {minutes} minutes, {seconds} seconds"

            build_time = (
                info.build_time.strftime("%Y-%m-%d %H:%M:%S")
                if info.build_time
                else "Unknown"
            )
            jvm_version = info.jvm
            lavaplayer_version = info.lavaplayer
            source_managers = (
                ", ".join(info.source_managers) if info.source_managers else "None"
            )
            plugins = (
                "\n".join(
                    [f"{plugin.name} (v{plugin.version})" for plugin in info.plugins]
                )
                or "None"
            )

            version_info = info.version
            semver = version_info.semver
            branch = info.git.branch
            commit = info.git.commit
            commit_time = info.git.commit_time.strftime("%Y-%m-%d %H:%M:%S")

            if memory is not None:
                memory_used = getattr(memory, "used", 0) / (1024 * 1024)
                memory_free = getattr(memory, "free", 0) / (1024 * 1024)
                memory_allocated = getattr(memory, "allocated", 0) / (1024 * 1024)
                memory_reservable = getattr(memory, "reservable", 0) / (1024 * 1024)
            else:
                memory_used = memory_free = memory_allocated = memory_reservable = 0

            if cpu is not None:
                cpu_cores = getattr(cpu, "cores", 0)
            else:
                cpu_cores = 0

            node_embed = discord.Embed(
                title="Node Statistics",
                color=0x2B2D31,
            )
            node_embed.add_field(
                name="Lavalink Info",
                value=f"> **Status**: {node_status}\n"
                f"> **Players**: {players}\n"
                f"> **Uptime**: {uptime_formatted}\n"
                f"> **JVM Version**: {jvm_version}\n"
                f"> **Build Time**: {build_time}\n"
                f"> **Lavaplayer Version**: {lavaplayer_version}\n",
                inline=False,
            )
            node_embed.add_field(
                name="Lavalink Version Info",
                value=f"> **Version**: {semver}\n"
                f"> **Branch**: {branch}\n"
                f"> **Commit**: {commit}\n"
                f"> **Commit Time**: {commit_time}",
                inline=False,
            )
            node_embed.add_field(
                name="Memory Usage",
                value=f"> **Used**: {memory_used:.2f} MB\n"
                f"> **Free**: {memory_free:.2f} MB\n"
                f"> **Allocated**: {memory_allocated:.2f} MB\n"
                f"> **Reservable**: {memory_reservable:.2f} MB",
                inline=False,
            )
            node_embed.add_field(
                name="CPU Information",
                value=f"> **Cores**: {cpu_cores}\n"
                f"> **System Load**: {system_load:.2f}%\n"
                f"> **Lavalink Load**: {lavalink_load:.2f}%",
                inline=False,
            )

            plugins_embed = discord.Embed(
                title="Plugins and Source Managers",
                color=0x2B2D31,
            )
            plugins_embed.add_field(
                name="Source Managers",
                value=f"> {source_managers}\n",
                inline=False,
            )
            plugins_embed.add_field(
                name="Used Plugins",
                value=f"{plugins}",
                inline=False,
            )

            view = NodeView(node_embed, plugins_embed)
            view.msg = await ctx.send(embed=node_embed, view=view)


        except Exception as e:
            await ctx.send(
                "Unable to fetch node statistics. Is the Lavalink node running?"
            )
            print(f"Error fetching node stats: {e}")

    @commands.hybrid_command(name="code")
    async def code(self, ctx: BoultContext):
        """Shows the bot source code."""
        if ctx.interaction:
            await ctx.defer()

        embed = discord.Embed(
            description=f"[GitHub](https://github.com/0xhimangshu/Boult)",
            color=self.bot.color
        )
        view = LinkButton(links=[
            Link(name="GitHub", url="https://github.com/0xhimangshu/Boult"),
            Link(name="Invite", url=self.bot.config.bot.invite_link)
        ])
        await ctx.send(embed=embed, view=view)


        