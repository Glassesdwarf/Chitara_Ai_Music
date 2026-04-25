"""
Strategy pattern for song generation.

Public API:
    from music.strategies import get_strategy, MusicGenerationContext

The `get_strategy()` factory reads settings.MUSIC_STRATEGY and returns a
ready-to-use SongGenerationStrategy. The `MusicGenerationContext` is the
contextual class that holds a strategy and exposes `.generate(...)` to
callers. Callers never instantiate strategies directly — they go through
the context. This keeps view code unaware of which backend is in use.
"""
from .base import SongGenerationStrategy, GeneratedSong
from .mock import MockStrategy
from .suno import SunoStrategy
from .context import MusicGenerationContext, get_strategy

__all__ = [
    "SongGenerationStrategy",
    "GeneratedSong",
    "MockStrategy",
    "SunoStrategy",
    "MusicGenerationContext",
    "get_strategy",
]
