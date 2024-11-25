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



import discord
from discord.ext import commands

from core import Boult, Cog

from utils import BoultContext


class Playlist(Cog): # TODO: Implement
    def __init__(self, bot: Boult):
        self.bot = bot

    @commands.hybrid_group(name="playlist", with_app_command=True)
    async def playlist(self, ctx: BoultContext):
        """
        Manage your playlists.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @playlist.command(name="create", with_app_command=True)
    async def create(self, ctx: BoultContext, *, name: str):
        ... # TODO

    @playlist.command(name="delete", with_app_command=True)
    async def delete(self, ctx: BoultContext, *, name: str):
        ... # TODO

