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



import random

import discord
from discord.ext import tasks

from core import Boult, Cog


class Ready(Cog):
    def __init__(self, bot: Boult):
        self.bot = bot

    @tasks.loop(seconds=15)
    async def status_task(self):
        choice = random.choice(self.bot.config.bot.statuses)
        activity_type = next((k for k in ["listening", "watching", "playing"] if choice.get(k)), "listening")
        activity_name = choice.get(activity_type, "Boult Boults")
        await self.bot.change_presence(activity=discord.Activity(type=getattr(discord.ActivityType, activity_type), name=activity_name))

    @Cog.listener("on_ready")
    async def status_task_start(self):
        try:
            await self.status_task.start()
        except RuntimeError:
            pass

    