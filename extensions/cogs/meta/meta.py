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
import datetime
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import discord
import distro
import psutil
import wavelink
from discord.ext import commands, tasks
import pytz
import platform
from core import Boult, Cog
from utils import (Link, LinkButton, NodeView, format_relative,
                   truncate_string)

from extensions.context import BoultContext


@dataclass
class SystemMetrics:
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, int]
    process_info: Dict[str, Any]

class MetricsCollector:
    def __init__(self):
        self.metrics_history: List[SystemMetrics] = []
        self.max_history_size = 100
        
    async def collect_metrics(self) -> SystemMetrics:
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()._asdict()
        process = psutil.Process()
        
        return SystemMetrics(
            cpu_usage=cpu,
            memory_usage=memory.percent,
            disk_usage=disk.percent,
            network_io=network,
            process_info={
                'memory': process.memory_info()._asdict(),
                'cpu_percent': process.cpu_percent()
            }
        )

    def add_metrics(self, metrics: SystemMetrics):
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history.pop(0)

class Meta(Cog):
    """Commands that are related to the bot itself."""
 
    def __init__(self, bot: Boult):
        super().__init__(bot)
        self.metrics_collector = MetricsCollector()
        self.logger = logging.getLogger('Meta')
        self.commit_cache: Dict[str, Tuple[List[Any], float]] = {}
        self.cache_ttl = 300  # 5 minutes
        self._start_background_tasks()
        self.github_headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "BoultBot/1.0"
        }

    def _start_background_tasks(self):
        self.collect_metrics_loop.start()
        self.clean_cache_loop.start()

    @tasks.loop(minutes=5)
    async def collect_metrics_loop(self):
        try:
            metrics = await self.metrics_collector.collect_metrics()
            self.metrics_collector.add_metrics(metrics)
        except Exception as e:
            self.logger.error(f"Failed to collect metrics: {e}")

    @tasks.loop(minutes=10)
    async def clean_cache_loop(self):
        current_time = time.time()
        expired_keys = [k for k, v in self.commit_cache.items() 
                       if current_time - v[1] > self.cache_ttl]
        for k in expired_keys:
            del self.commit_cache[k]

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(id=1257989216516837408, name="bot")
  
    async def get_db_latency(self) -> Tuple[Optional[float], Optional[float]]:
        async def measure_operation(operation: str) -> float:
            start = time.perf_counter()
            if operation == "read":
                await self.bot.db.execute("SELECT * FROM test WHERE id = $1", 1)
            else:
                await self.bot.db.execute(
                    "UPDATE test SET test = $1 WHERE id = $2", 
                    "test", 1
                )
            return time.perf_counter() - start

        read_latency = await measure_operation("read")
        write_latency = await measure_operation("write")
        
        return read_latency, write_latency
    
    async def get_contributors(self):
        async with aiohttp.ClientSession(headers=self.github_headers) as session:
            async with session.get("https://api.github.com/repos/0xhimangshu/Boult/contributors") as response:
                contributors = await response.json()
                developers = []
                for contributor in contributors:
                    developers.append(f"[{contributor['login']}]({contributor['html_url']})")
                return developers
    
    async def get_latest_change(self) -> List[Tuple]:
        cache_key = 'github_commits'
        if cache_key in self.commit_cache:
            commits, timestamp = self.commit_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return commits
        
        async with aiohttp.ClientSession(headers=self.github_headers) as session:
            async with session.get(
                "https://api.github.com/repos/0xhimangshu/Boult/commits",
                params={"per_page": 3}
            ) as response:
                if response.status != 200:
                    raise Exception(f"GitHub API returned {response.status}")
                
                data = await response.json()
                commits = [
                    (
                        commit['sha'],
                        commit['commit']['message'],
                        commit['commit']['author']['name'],
                        commit['commit']['author']['date'],
                        commit['html_url']
                    )
                    for commit in data[:3]
                ]
                
                self.commit_cache[cache_key] = (commits, time.time())
                return commits
            
    async def _commits(self) -> str:
        try:
            commits = await self.get_latest_change()
            formatted_commits = []
            
            for commit in commits:
                try:
                    commit_date = datetime.datetime.fromisoformat(commit[3].replace('Z', '+00:00'))
                    commit_date_ist = commit_date.astimezone(pytz.timezone('Asia/Kolkata'))
                    timestamp = int(commit_date_ist.timestamp())
                    
                    formatted_commit = (
                        f"[{truncate_string(commit[0], max_length=6, suffix='')}]({commit[4]}) "
                        f"- `{commit[1]}` by [{commit[2]}](https://github.com/{commit[2]}) "
                        f"<t:{timestamp}:R>"
                    )
                    formatted_commits.append(formatted_commit)
                except Exception as e:
                    self.logger.error(f"Error formatting commit {commit}: {e}")
                    continue
            
            return '\n'.join(formatted_commits)
        except Exception as e:
            self.logger.error(f"Error getting commits: {e}")
            return "Unable to fetch commit history"

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

        metrics = await self.metrics_collector.collect_metrics()
        embed = discord.Embed(color=self.bot.color)
        
        vc: discord.VoiceClient = self.bot.secret_voice_client
        voice_latency = vc.latency if vc else random.randint(6, 100) / 1000

        db_latency = await self.get_db_latency()
        
        system_info = (
            f"> {self.bot.config.emoji.discord} **Discord HTTP**\n"
            f"> {self.bot.config.emoji.icon1} `{round(self.bot.latency*1000)} ms`\n"
            f"> {self.bot.config.emoji.discord} **Discord WS**\n"
            f"> {self.bot.config.emoji.icon1} `{round((time.time() - ctx.message.created_at.timestamp())*1000)} ms`\n"
        )

        voice_info = (
            f"> {self.bot.config.emoji.voice} **Discord Voice WS**\n"
            f"> {self.bot.config.emoji.icon1}`{round(voice_latency * 1000)} ms`\n"
        ) if self.bot.secret_voice_client else ""

        db_info = (
            f"> {self.bot.config.emoji.postgresql} **PostgreSQL**\n"
            f"> {self.bot.config.emoji.icon1} `r: {round(db_latency[0] * 1000)} ms | "
            f"w: {round(db_latency[1] * 1000)} ms`\n"
        )

        embed.description = system_info + voice_info + db_info
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="botinfo", 
        description="Displays information about the bot."
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def botinfo(self, ctx: BoultContext):
        """Displays information about the bot."""
        if ctx.interaction:
            await ctx.defer()

        bot_info = (
            f"> **Servers**: {len(self.bot.guilds)}\n"
            f"> **Users**: {len(self.bot.users)}\n"
            f"> **Commands**: {len([c for c in self.bot.walk_commands() if not c.cog_name == "jishaku"])}\n"
            f"> **Uptime**: {format_relative(self.bot.uptime)}\n"
            f"> **Messages Seen**: {self.bot.cache.get('msg_seen', 0)}\n"
            f"> **Commands Run**: {self.bot.cache.get('cmd_ran', 0)}\n"
        )

        contributors = await self.get_contributors()
        credits = (
            f"> **Developers**: {', '.join(contributors)}\n"
        )

        embed = discord.Embed(
            description=bot_info + "\n" + credits,
            color=0x2C2C34
        )
        embed.set_author(
            name="App Information",
            icon_url=self.bot.user.display_avatar.url
        )

        await ctx.send(embed=embed)

    @commands.hybrid_command(with_app_command=True, name="stats")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def stats(self, ctx: commands.Context):
        """Fetches detailed bot statistics."""
        if ctx.interaction:
            await ctx.defer()

        async with ctx.typing():
            await asyncio.sleep(2)  

            metrics = await self.metrics_collector.collect_metrics()
            
            process = psutil.Process()
            with process.oneshot():
                memory_full = process.memory_full_info()
                cpu_times = process.cpu_times()
                
                memory_stats = (
                    f"> **RAM**: {memory_full.rss / (1024**2):.2f} MB "
                    f"(USS: {memory_full.uss / (1024**2):.2f} MB)\n"
                    f"> **Memory %**: {metrics.memory_usage:.1f}%\n"
                    f"> **Swap**: {memory_full.vms / (1024**2):.2f} MB\n"
                )
                
                cpu_stats = (
                    f"> **CPU Usage**: {metrics.cpu_usage:.1f}%\n"
                    f"> **CPU Times**: User: {cpu_times.user:.1f}s, "
                    f"System: {cpu_times.system:.1f}s\n"
                )

            disk = psutil.disk_usage('./')
            disk_stats = (
                f"> **Total**: {disk.total / (1024**3):.1f} GB\n"
                f"> **Used**: {disk.used / (1024**3):.1f} GB ({disk.percent}%)\n"
                f"> **Free**: {disk.free / (1024**3):.1f} GB\n"
            )

            os_info = (
                f"> **OS**: {distro.name()} {distro.version()}\n"
                f"> **Boot Time**: {datetime.datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            
            cache_data = self.bot.cache
            bot_stats = (
                f"> **Uptime**: {format_relative(self.bot.uptime)}\n"
                f"> **Messages Seen**: {cache_data.get('msg_seen', 0)} "
                f"({len(self.bot.cached_messages)} cached)\n"
                f"> **Commands Run**: {cache_data.get('cmd_ran', 0)}\n"
                f"> **Guilds**: {len(self.bot.guilds)} ({sum(1 for g in self.bot.guilds if g.chunked)} chunked)\n"
                f"> **Users**: {len(self.bot.users)} ({sum(len(g.members) for g in self.bot.guilds)} total)\n"
                f"> **Voice Connections**: {len(self.bot.voice_clients)}\n"
            )

            changes = await self._commits()

            libs = (
                f"> Python: {platform.python_version()}\n"
                f"> Asyncpg: {__import__('asyncpg').__version__}\n"
                f"> Aiohttp: {aiohttp.__version__}\n"
                f"> Discord.py: {discord.__version__}\n"
                f"> Jishaku: {__import__('jishaku').__version__}\n"
                f"> Wavelink: {wavelink.__version__}\n"
            )

            embed = discord.Embed(
                color=self.bot.color,
                description=(
                    f"**System Information**\n{os_info}\n{libs}\n"
                    f"**Memory Statistics**\n{memory_stats}\n"
                    f"**CPU Statistics**\n{cpu_stats}\n"
                    f"**Disk Statistics**\n{disk_stats}\n"
                    f"**Bot Statistics**\n{bot_stats}\n"
                    f"**Latest Changes**\n{changes}"
                )
            )
            
            embed.set_author(
                name="Boult System Stats",
                icon_url=self.bot.user.display_avatar.url
            )
            embed.set_footer(text=f"Process ID: {process.pid} • Generated at {datetime.datetime.now(pytz.UTC).strftime('%H:%M:%S UTC')}")

            await ctx.send(embed=embed)

    def format_size(self, size: float) -> str:
        for unit in ["", "K", "M", "G", "T", "P", "E", "Z", "Y"]:
            if abs(size) < 1024.0:
                return f"{size:.2f}{unit}B"
            size /= 1024.0
        return f"{size:.2f}YB"

    @commands.command(name="node")
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def node(self, ctx: BoultContext):
        """Fetch real-time Lavalink node statistics with detailed metrics."""
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

            # Process uptime
            uptime_ms = getattr(stats, "uptime", 0)
            hours, remainder = divmod(uptime_ms // 1000, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_formatted = f"{hours}h {minutes}m {seconds}s"

            # Memory metrics
            memory = getattr(stats, "memory", None)
            if memory:
                memory_metrics = {
                    "used": self.format_size(memory.used),
                    "free": self.format_size(memory.free),
                    "allocated": self.format_size(memory.allocated),
                    "reservable": self.format_size(memory.reservable)
                }
            else:
                memory_metrics = {k: "N/A" for k in ["used", "free", "allocated", "reservable"]}

            # CPU metrics
            cpu = getattr(stats, "cpu", None)
            if cpu:
                cpu_metrics = {
                    "cores": getattr(cpu, "cores", 0),
                    "system_load": f"{getattr(cpu, 'systemLoad', 0.0) * 100:.1f}%",
                    "lavalink_load": f"{getattr(cpu, 'lavalinkLoad', 0.0) * 100:.1f}%"
                }
            else:
                cpu_metrics = {k: "N/A" for k in ["cores", "system_load", "lavalink_load"]}

            # Version information
            version_info = {
                "semver": info.version.semver,
                "branch": info.git.branch,
                "commit": info.git.commit[:7],
                "build_time": info.build_time.strftime("%Y-%m-%d %H:%M:%S") if info.build_time else "Unknown",
                "commit_time": info.git.commit_time.strftime("%Y-%m-%d %H:%M:%S")
            }

            # Create embeds
            main_embed = discord.Embed(
                title="Node Statistics",
                color=0x2B2D31,
                description=(
                    f"**Status**: Online\n"
                    f"**Players**: {getattr(stats, 'players', 0)}\n"
                    f"**Playing Players**: {getattr(stats, 'playingPlayers', 0)}\n"
                    f"**Uptime**: {uptime_formatted}\n"
                )
            )

            main_embed.add_field(
                name="Memory Usage",
                value=(
                    f"> **Used**: {memory_metrics['used']}\n"
                    f"> **Free**: {memory_metrics['free']}\n"
                    f"> **Allocated**: {memory_metrics['allocated']}\n"
                    f"> **Reservable**: {memory_metrics['reservable']}\n"
                ),
                inline=False
            )

            main_embed.add_field(
                name="CPU Information",
                value=(
                    f"> **Cores**: {cpu_metrics['cores']}\n"
                    f"> **System Load**: {cpu_metrics['system_load']}\n"
                    f"> **Lavalink Load**: {cpu_metrics['lavalink_load']}\n"
                ),
                inline=False
            )

            details_embed = discord.Embed(
                title="Node Details",
                color=0x2B2D31
            )

            details_embed.add_field(
                name="Version Information",
                value=(
                    f"> **Version**: {version_info['semver']}\n"
                    f"> **Branch**: {version_info['branch']}\n"
                    f"> **Commit**: {version_info['commit']}\n"
                    f"> **Build Time**: {version_info['build_time']}\n"
                    f"> **Commit Time**: {version_info['commit_time']}\n"
                ),
                inline=False
            )

            details_embed.add_field(
                name="Runtime Information",
                value=(
                    f"> **JVM Version**: {info.jvm}\n"
                    f"> **Lavaplayer**: {info.lavaplayer}\n"
                ),
                inline=False
            )

            plugins_embed = discord.Embed(
                title="Plugins and Sources",
                color=0x2B2D31
            )

            source_managers = ", ".join(info.source_managers) if info.source_managers else "None"
            plugins = "\n".join(
                f"> **{plugin.name}** (v{plugin.version})"
                for plugin in info.plugins
            ) or "None"

            plugins_embed.add_field(
                name="Source Managers",
                value=f"> {source_managers}",
                inline=False
            )

            plugins_embed.add_field(
                name="Plugins",
                value=plugins,
                inline=False
            )

            view = NodeView(main_embed, details_embed, plugins_embed)
            view.msg = await ctx.send(embed=main_embed, view=view)

        except Exception as e:
            self.logger.error(f"Error fetching node stats: {e}")
            await ctx.send(
                embed=discord.Embed(
                    description="Failed to fetch node statistics. Please try again later.",
                    color=discord.Color.red()
                )
            )

    @commands.hybrid_command(name="source", aliases=["src"], with_app_command=True)
    async def source(self, ctx: BoultContext):
        """Shows the bot source code and related information."""
        if ctx.interaction:
            await ctx.defer()

        embed = discord.Embed(
            title="Boult Source Code",
            description=(
                "Boult is an open-source Discord music bot written in Python. "
                "Feel free to contribute or report issues on GitHub!\n\n"
                "**License**: [MIT](https://github.com/0xhimangshu/Boult/blob/master/LICENSE)\n"
            ),
            color=self.bot.color
        )

        view = LinkButton(links=[
            Link(name="GitHub", url="https://github.com/0xhimangshu/Boult"),
            Link(name="Invite Bot", url=self.bot.config.bot.invite_link),
            Link(name="Support Server", url=self.bot.config.bot.support_invite)
        ])

        await ctx.send(embed=embed, view=view)