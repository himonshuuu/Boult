from core import Boult

from .meta import Meta

async def setup(bot: Boult):
    await bot.add_cog(Meta(bot))