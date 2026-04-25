"""
Contextual class (the "Context" in the Strategy pattern).

The view layer only ever talks to MusicGenerationContext. Swapping
strategies is a one-line config change in .env, not a code change.
"""
from __future__ import annotations
from django.conf import settings
from .base import SongGenerationStrategy, GeneratedSong
from .mock import MockStrategy
from .suno import SunoStrategy


_REGISTRY: dict[str, type[SongGenerationStrategy]] = {
    "mock": MockStrategy,
    "suno": SunoStrategy,
}


def get_strategy(name: str | None = None) -> SongGenerationStrategy:
    """Factory: resolve a strategy by name, defaulting to settings.MUSIC_STRATEGY."""
    key = (name or settings.MUSIC_STRATEGY or "mock").lower()
    if key not in _REGISTRY:
        raise ValueError(
            f"Unknown MUSIC_STRATEGY '{key}'. Valid options: {list(_REGISTRY)}"
        )
    return _REGISTRY[key]()


class MusicGenerationContext:
    """
    Holds a SongGenerationStrategy and forwards work to it. Lets callers
    swap the strategy at runtime (`set_strategy`) without changing call
    sites — the canonical Strategy-pattern Context.
    """

    def __init__(self, strategy: SongGenerationStrategy | None = None):
        self._strategy: SongGenerationStrategy = strategy or get_strategy()

    @property
    def strategy(self) -> SongGenerationStrategy:
        return self._strategy

    def set_strategy(self, strategy: SongGenerationStrategy | str) -> None:
        self._strategy = get_strategy(strategy) if isinstance(strategy, str) else strategy

    def generate(self, *, title: str, prompt: str, genre: str) -> GeneratedSong:
        return self._strategy.generate(title=title, prompt=prompt, genre=genre)
