from core import Boult, Cog

from .error import Error
from .guild import Guild
from .ready import Ready
from .voice import Voice


async def setup(bot: Boult):
    await bot.add_cog(Voice(bot))
    await bot.add_cog(Guild(bot))
    await bot.add_cog(Error(bot))
    await bot.add_cog(Ready(bot))
