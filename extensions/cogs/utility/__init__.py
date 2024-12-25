from .utility import Utility
from core import Boult


async def setup(bot: Boult):
    await bot.add_cog(Utility(bot))
