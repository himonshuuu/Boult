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
import json
import logging
import os
import weakref
from logging.handlers import RotatingFileHandler
from typing import Callable, Coroutine, List

import aiohttp
import discord
import wavelink
from discord.ext import commands
from discord.utils import cached_property
from urllib.parse import quote
import config
from utils import BoultContext as Context
from utils import DatabaseManager, SpotifyClient
from utils.cache import Strategy
from utils.cache import cache as _cache
from utils.fetcher import EntityFetcher

from .help import HelpCommand

os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_NO_DM_TRACEBACK"] = "True" 
os.environ["JISHAKU_HIDE"] = "True"

startup_task: List[Callable[["Boult"], Coroutine]] = []

class Boult(commands.AutoShardedBot):
    """Custom bot class that extends the discord.ext.commands.Bot class."""

    def __init__(self, dev: bool, *args, **kwargs):
        super().__init__(
            command_prefix=self.get_prefix,
            intents=discord.Intents.all(),
            strip_after_prefix=True,
            case_insensitive=True,
            owner_ids=(775660503342776341, 1035108943485222912),
            help_command=HelpCommand(),
            help_attrs=dict(hidden=True),
            chunk_guilds_at_startup=False,
            *args,
            **kwargs,
        )

        self._dev = dev
        self._uptime = None
        self._prefix_cache = {}
        self._session = None
        
        self.db = DatabaseManager()
        self.fetcher = EntityFetcher(self)

        self.secret_voice_client : discord.VoiceClient = None
        self.nodes: List[wavelink.Node] = []
        
        self.setup_logging()

    def load_cache(self):
        with open("cache.json", "r") as f:
            self._cache = json.load(f)
        
    def dump_cache(self):
        with open("cache.json", "w") as f:
            json.dump(self._cache, f)

    @cached_property
    def config(self):
        return config

    @cached_property
    def color(self):
        return 0x2b2d31

    @cached_property
    def spotify(self):
        return SpotifyClient(
            self.config.api_keys.spotify_client_id,
            self.config.api_keys.spotify_client_secret,
        )

    
    @cached_property
    def cache(self):
        if not hasattr(self, '_cache'):
            self._cache = {
                "players": weakref.WeakValueDictionary(),  # weak references for players
                "lyrics_tasks": {},
                "msg_seen": 0,
                "cmd_ran": 0,
            }
            self.load_cache()
        return self._cache

    @property
    def session(self):
        return self._session

    @property
    def uptime(self):
        return self._uptime

    @uptime.setter
    def uptime(self, value):
        self._uptime = value

    @property
    def dev(self):
        return self._dev

    @_cache(maxsize=1000, strategy=Strategy.lru)
    async def get_prefix(self, message: discord.Message) -> List[str] | str:
        if self.dev:
            return commands.when_mentioned_or(config.bot.canary_prefix)(self, message)

        guild_id = message.guild.id if message.guild else None
        prefixes = [config.bot.default_prefix]

        if guild_id:
            try:
                row = await self.db.fetch_one(
                    "SELECT prefix FROM guild_config WHERE guild_id = $1",
                    guild_id
                )
                if row:
                    prefixes.append(row['prefix'])
            except Exception:
                pass

        # Check no prefix users
        try:
            np = await self.db.fetch_one(
                "SELECT no_prefix FROM user_config WHERE user_id = $1",
                message.author.id,
            )
            if np and np.no_prefix:
                prefixes.append("")
        except Exception:
            pass

        return commands.when_mentioned_or(*prefixes)(self, message)

    def invalidate_cache(self, guild_id: int = None):
        """Invalidate prefix cache for a guild or all guilds."""
        if guild_id:
            self.get_prefix.invalidate_containing(str(guild_id))
        else:
            self.get_prefix.cache.clear()

    async def setup_hook(self):
        self._uptime = discord.utils.utcnow()
        self._session = aiohttp.ClientSession()

        # Run startup tasks concurrently
        await asyncio.gather(*(task(self) for task in startup_task))

    async def process_commands(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        ctx = await self.get_context(message, cls=Context)
        if not ctx.command:
            return

        if self.dev and ctx.author.id not in self.owner_ids:
            await message.channel.send(
                embed=discord.Embed(
                    description="🛠️ My developer is working on adding more features. Stay tuned!",
                    color=self.color,
                )
            )
            return

        await self.invoke(ctx)
        
        self.cache["cmd_ran"] += 1
        self.dump_cache()

    async def on_message(self, message: discord.Message):

        if message.author.bot:
            return

        self.cache["msg_seen"] += 1
        self.dump_cache()

        if message.content == self.user.mention:
            await message.channel.send(
                embed=discord.Embed(
                    description=f"`{config.bot.default_prefix}help` to get started",
                    color=config.color.color,
                ).set_author(icon_url=self.user.display_avatar.url, name=self.user.name)
            )

        await self.process_commands(message)

    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        self.logger.info(f"Wavelink node {payload.node.identifier} ready")

    @startup_task.append
    async def setup_db(self):
        dsn = f"postgres://{config.pgsql.pg_user}:{quote(config.pgsql.pg_auth)}@{config.pgsql.pg_host}:{config.pgsql.pg_port}/{config.pgsql.pg_dbname}"
        await self.db.initialize(dsn)
        
        self.logger.info("Connected to database")

    @startup_task.append 
    async def setup_cogs(self):
        try:
            await self.load_extension("jishaku")
            self.logger.info("Loaded jishaku")
        except Exception as e:
            self.logger.error(f"Failed to load jishaku: {e}")

        for ext in config.bot.extensions:
            try:
                await self.load_extension(ext)
                self.logger.info(f"Loaded extension {ext}")
            except Exception as e:
                self.logger.error(f"Failed to load extension {ext}: {e}")

    @startup_task.append
    async def setup_wavelink(self):
        await asyncio.sleep(5)
        
        for i, node in enumerate(config.lavalink.nodes, start=1):
            uri = f"http://{node['host']}" + (f":{node['port']}" if node.get("port") else "")
            
            node_config = wavelink.Node(
                identifier=f"node-{i}",
                uri=uri,
                password=node["auth"],
                client=self,
                retries=3
            )
            
            try:
                await wavelink.Pool.connect(client=self, nodes=[node_config])
                self.nodes.append(node_config)
            except Exception as e:
                self.logger.error(f"Failed to connect to node {i}: {e}")

    @startup_task.append
    async def setup_application_commands(self):
        await asyncio.sleep(5)
        try:
            cmds = await self.tree.sync()
            self.logger.info(f"Loaded {len(cmds)} application commands")
        except Exception as e:
            self.logger.error(f"Failed to sync commands: {e}")

    def setup_logging(self):
        self.logger = logging.getLogger(f"{'Boult-dev' if self.dev else 'Boult'}")
        self.logger.setLevel(logging.INFO)
        
        dt_fmt = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(
            "{asctime} {levelname:<8} {name} {message}", dt_fmt, style="{"
        )

        handlers = [
            logging.StreamHandler(),
            RotatingFileHandler(
                filename="boult.log",
                mode="a", 
                maxBytes=1024 * 1024 * 5,
                backupCount=5
            )
        ]

        for handler in handlers:
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # Set levels for noisy loggers
        for logger_name in ('asyncio', 'wavelink', 'discord.voice_state'):
            logging.getLogger(logger_name).setLevel(logging.CRITICAL)

    def boot(self):
        self.logger.info("Booting up...")
        try:
            super().run(config.bot.canary_token if self.dev else config.bot.token)
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
            os._exit(0)


