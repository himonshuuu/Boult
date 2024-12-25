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
import itertools
import json
import logging
import os
import weakref
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import (Any, Callable, Coroutine, Dict, List, Optional, Type,
                    TypeVar, Union)

import aiohttp
import discord
import wavelink
from discord.ext import commands, tasks
from discord.utils import cached_property

import config
from extensions.context import BoultContext
from utils import DatabaseManager, SpotifyClient
from utils.cache import CacheManager
from utils.fetcher import EntityFetcher

from .help import HelpCommand

os.environ.update({
    "JISHAKU_NO_UNDERSCORE": "True",
    "JISHAKU_NO_DM_TRACEBACK": "True",
    "JISHAKU_HIDE": "True",
    "JISHAKU_FORCE_PAGINATOR": "True",
})

T = TypeVar('T')
startup_task: List[Callable[["Boult"], Coroutine[Any, Any, None]]] = []

@dataclass
class BotState:
    uptime: Optional[discord.utils.utcnow] = None
    session: Optional[aiohttp.ClientSession] = None
    prefix_cache: Dict[int, str] = field(default_factory=dict)
    cache: Dict[str, Any] = field(default_factory=lambda: {
        "players": weakref.WeakValueDictionary(),
        "lyrics_tasks": {},
        "msg_seen": 0,
        "cmd_ran": 0
    })
    
class CacheDescriptor:
    def __init__(self, filename: str):
        self.filename = filename
        self._cache = None
    
    def __get__(self, instance: Optional["Boult"], owner: type) -> Dict[str, Any]:
        if self._cache is None:
            with open(self.filename, "r") as f:
                self._cache = json.load(f)
        return self._cache
    
    def __set__(self, instance: "Boult", value: Dict[str, Any]) -> None:
        self._cache = value
        with open(self.filename, "w") as f:
            json.dump(value, f)

    def get_cache(self) -> Dict[str, Any]:
        return self.__get__(None, None)

class Boult(commands.AutoShardedBot):
    """Advanced bot implementation extending discord.ext.commands.Bot with enhanced functionality."""

    def __init__(self, dev: bool, db_manager: DatabaseManager, *args, **kwargs):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=self.get_prefix,
            intents=intents,
            strip_after_prefix=True,
            case_insensitive=True,
            owner_ids=frozenset({775660503342776341, 1035108943485222912}),
            help_command=HelpCommand(),
            help_attrs={"hidden": True},
            chunk_guilds_at_startup=False,
            *args,
            **kwargs,
        )

        self._state = BotState()
        self._dev = dev
        self._executor = ThreadPoolExecutor(max_workers=os.cpu_count())
        self._prefix_invalidation_events = defaultdict(asyncio.Event)
        
        self.cache_manager = CacheManager(max_size=1000, ttl=3600)
        self.db = db_manager
        self.fetcher = EntityFetcher(self)
        
        self.secret_voice_client: Optional[discord.VoiceClient] = None
        self.nodes: List[wavelink.Node] = []
        
        self.context: Type[BoultContext] = BoultContext
        self.logger = logging.getLogger()
        self._persistent_cache = CacheDescriptor("cache.json")
        
        self._task_loops = []
        self._setup_background_tasks()

    def _setup_background_tasks(self):
        @tasks.loop(minutes=5)
        async def cache_cleanup():
            self.cache_manager.cleanup_expired()
            
        @tasks.loop(minutes=15)
        async def status_rotation():
            activities = itertools.cycle([
                discord.Activity(type=discord.ActivityType.listening, name="your commands"),
                discord.Activity(type=discord.ActivityType.watching, name=f"{len(self.guilds)} servers"),
                discord.Activity(type=discord.ActivityType.playing, name="with music")
            ])
            await self.change_presence(activity=next(activities))
            
        self._task_loops.extend([cache_cleanup, status_rotation])

    @cached_property
    def config(self) -> config:
        return config

    @cached_property
    def color(self) -> int:
        return 0x2b2d31

    @cached_property
    def spotify(self) -> SpotifyClient:
        return SpotifyClient(
            client_id=self.config.api_keys.spotify_client_id,
            client_secret=self.config.api_keys.spotify_client_secret,
        )

    @property
    def cache(self) -> CacheDescriptor:
        return self._persistent_cache.get_cache()

    @cache.setter 
    def cache(self, value: Dict[str, Any]) -> None:
        self._persistent_cache = value

    @property
    def session(self) -> Optional[aiohttp.ClientSession]:
        return self._state.session

    @property
    def uptime(self) -> Optional[discord.utils.utcnow]:
        return self._state.uptime

    @uptime.setter
    def uptime(self, value: discord.utils.utcnow) -> None:
        self._state.uptime = value

    @property
    def dev(self) -> bool:
        return self._dev

    async def get_prefix(self, message: discord.Message) -> Union[List[str], str]:
        if self.dev:
            return commands.when_mentioned_or(self.config.bot.canary_prefix)(self, message)

        guild_id = getattr(message.guild, 'id', None)
        prefixes = [self.config.bot.default_prefix]

        if guild_id:
            try:
                cached_prefix = self._state.prefix_cache.get(guild_id)
                if cached_prefix is None:
                    row = await self.db.fetch_one(
                        "SELECT prefix FROM guild_config WHERE guild_id = $1",
                        guild_id
                    )
                    if row:
                        cached_prefix = row.prefix
                        self._state.prefix_cache[guild_id] = cached_prefix
                if cached_prefix:
                    prefixes.append(cached_prefix)
            except Exception as e:
                self.logger.error(f"Error fetching prefix: {e}")

        try:
            np = await self.db.fetch_one(
                "SELECT no_prefix FROM user_config WHERE user_id = $1",
                message.author.id,
            )
            if np and np.get('no_prefix'):
                prefixes.append("")
        except Exception as e:
            self.logger.error(f"Error checking no_prefix: {e}")

        return commands.when_mentioned_or(*prefixes)(self, message)

    def invalidate_cache(self, guild_id: Optional[int] = None) -> None:
        """Invalidate prefix cache with advanced event handling."""
        if guild_id:
            self._state.prefix_cache.pop(guild_id, None)
            event = self._prefix_invalidation_events[guild_id]
            event.set()
            event.clear()
        else:
            self._state.prefix_cache.clear()
            for event in self._prefix_invalidation_events.values():
                event.set()
                event.clear()

    async def setup_hook(self) -> None:
        self._state.uptime = discord.utils.utcnow()
        self._state.session = aiohttp.ClientSession()

        startup_coros = (task(self) for task in startup_task)
        results = await asyncio.gather(*startup_coros, return_exceptions=True)
        
        for task, result in zip(startup_task, results):
            if isinstance(result, Exception):
                self.logger.error(f"Startup task {task.__name__} failed: {result}")

        for loop in self._task_loops:
            loop.start()

    async def get_context(
        self,
        origin: discord.Message | discord.Interaction,
        *,
        cls: Type[BoultContext] | None = None,
    ) -> BoultContext:
        return await super().get_context(origin, cls=cls or self.context)  

    async def process_commands(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return

        ctx = await self.get_context(message, cls=BoultContext)
        if not ctx.command:
            return

        if self.dev and ctx.author.id not in self.owner_ids:
            await message.channel.send(
                embed=discord.Embed(
                    description="🛠️ Development mode active - commands restricted to bot owners",
                    color=self.color,
                )
            )
            return

        try:
            await self.invoke(ctx)
            self.cache["cmd_ran"] += 1
        except Exception as e:
            self.logger.error(f"Command error in {ctx.command}: {e}")
            await self.on_command_error(ctx, e)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        
        try:
            self.cache["msg_seen"] += 1
        except Exception as e:
            self.logger.error(f"Error incrementing message count: {e}")

        if message.content == self.user.mention:
            embed = discord.Embed(
                title="Hi there! 👋",
                description=f"I'm {self.user.name}, your music bot companion!\n\n"
                           f"• Use `{config.bot.default_prefix}help` to see all commands\n"
                           f"• `{config.bot.default_prefix}play` to start playing music\n"
                           f"• Join a voice channel first before using music commands",
                color=config.color.color,
            ).set_author(
                icon_url=self.user.display_avatar.url,
                name=self.user.name
            )
            await message.channel.send(embed=embed)

        await self.process_commands(message)

    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        self.logger.info(f"Wavelink node {payload.node.identifier} ready | {payload.node.session_id}")

    @startup_task.append
    async def setup_extensions(self) -> None:
        """Initialize and load all bot extensions including core modules and custom cogs."""
        extensions = {
            "Core": ["jishaku"],
            "Cogs": config.bot.cogs,
            "Events": config.bot.events
        }

        self.logger.info("Starting extension loading process...")

        for category, ext_list in extensions.items():
            self.logger.info(f"\nLoading {category} extensions:")
            for ext in ext_list:
                try:
                    await self.load_extension(ext)
                    self.logger.info(f"✓ Successfully loaded {ext}")
                except Exception as e:
                    self.logger.error(f"✗ Failed to load {ext}: {e}")
                    if ext == "jishaku":  # Critical extension
                        self.logger.critical("Failed to load critical extension jishaku")
                    raise  

        total_loaded = sum(len(ext_list) for ext_list in extensions.values())
        self.logger.info(f"\nExtension loading complete. Loaded {total_loaded} extensions.")

    @startup_task.append
    async def setup_wavelink(self) -> None:
        await asyncio.sleep(5)  
        
        for i, node_config in enumerate(self.config.lavalink.nodes, 1):
            uri = f"http://{node_config['host']}"
            if port := node_config.get("port"):
                uri = f"{uri}:{port}"
            
            node = wavelink.Node(
                identifier=f"node-{i}",
                uri=uri,
                password=node_config["auth"],
                client=self,
                retries=3,
            )
            
            try:
                await wavelink.Pool.connect(client=self, nodes=[node])
                self.nodes.append(node)
                self.logger.info(f"Connected to Lavalink node {i} at {uri}")
            except Exception as e:
                self.logger.error(f"Failed connecting to node {i}: {e}")

    @startup_task.append
    async def setup_application_commands(self) -> None:
        await asyncio.sleep(5)  # Allow guild cache to populate
        try:
            commands = await self.tree.sync()
            self.logger.info(f"Synced {len(commands)} application commands")
        except discord.HTTPException as e:
            self.logger.error(f"Failed to sync commands: {e}")
            raise

    async def boot(self) -> None:
        self.logger.info("Starting boot process...")
        self.logger.info(f"Booting up in {'development' if self.dev else 'production'} mode...")
        try:
            token = self.config.bot.canary_token if self.dev else self.config.bot.token
            await super().start(token)
        except KeyboardInterrupt:
            self.logger.info("Shutdown initiated via KeyboardInterrupt")
            self._cleanup()
        except Exception as e:
            self.logger.critical(f"Fatal error during runtime: {e}")
            self._cleanup()
            raise
        finally:
            self.logger.info("Shutting down...")
            await self.close()
        self.logger.info("Boot process completed.")

    def _cleanup(self) -> None:
        """Perform cleanup operations before shutdown."""
        self.logger.info("Performing cleanup operations...")
        for task in asyncio.all_tasks():
            task.cancel()
        self._executor.shutdown(wait=False)
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)

    def __enter__(self):
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the runtime context related to this object."""
        self.close()
