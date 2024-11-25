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



from core import Boult, Cog
from core.player import Player

class Voice(Cog):
    def __init__(self, bot: Boult):
        self.bot = bot
        self.active_sessions = {}

    @Cog.listener("on_ready")
    async def join_voice_channels(self):
        await self.secret_voice_client_setup()
        await self.connect_to_voice_channels()

    async def secret_voice_client_setup(self):
        guild = self.bot.get_guild(1054659078808403998)
        channel = guild.get_channel(1299383834948931594)

        vc = await channel.connect(self_deaf=True)
        self.bot.secret_voice_client = vc

    async def connect_to_voice_channels(self):
        while True:
            try:
                data = await self.bot.db.fetch_all(
                    "SELECT guild_id, vc_channel FROM guild_config"
                )

                for row in data:
                    guild = self.bot.get_guild(row.guild_id)

                    if guild is None:
                        continue

                    channel = guild.get_channel(row.vc_channel)
                    if channel is None:
                        continue

                    vc = guild.voice_client
                    if vc is None:
                        try:
                            await channel.connect(cls=Player, self_deaf=True)
                        except Exception as e:
                            continue

            except Exception as e:
                self.bot.logger.error(
                    f"Error fetching guilds or connecting to voice channels: {e}"
                )