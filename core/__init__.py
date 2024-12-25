"""
Core module initialization providing essential bot components.
Handles dynamic imports and type exports for the main bot framework.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Tuple, Type, TypeVar, cast

if TYPE_CHECKING:
    from .bot import Boult as BoultType
    from .cog import Cog as CogType
    from .player import Player as PlayerType

try:
    from .bot import Boult
except ImportError as e:
    raise ImportError(f"Failed to import Boult: {e}")

try:
    from .cog import Cog
except ImportError as e:
    raise ImportError(f"Failed to import Cog: {e}")

try:
    from .player import Player
except ImportError as e:
    raise ImportError(f"Failed to import Player: {e}")

T = TypeVar('T')
CoreComponent = TypeVar('CoreComponent', bound='Boult | Cog | Player')

# Export core types with type checking
__all__: Tuple[str, ...] = ('Boult', 'Cog', 'Player')

# Version info
VERSION: str = '1.0.0'
__version__ = VERSION

_registry: dict[str, Type[CoreComponent]] = {
    'Boult': cast(Type[CoreComponent], Boult),
    'Cog': cast(Type[CoreComponent], Cog),
    'Player': cast(Type[CoreComponent], Player)
}
