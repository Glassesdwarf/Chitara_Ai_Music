"""Abstract base for all song-generation strategies."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class GeneratedSong:
    """Uniform return shape for every strategy."""
    title: str
    prompt: str
    genre: str
    audio_url: str = ""           # for remote results (Suno)
    local_path: Optional[str] = None  # for local files (Mock)
    strategy_used: str = ""


class SongGenerationStrategy(ABC):
    """
    The Strategy interface. Every concrete generator (Mock, Suno, future
    backends like Udio/Riffusion/Local-Diffusion) must implement `generate`.
    """

    name: str = "base"

    @abstractmethod
    def generate(self, *, title: str, prompt: str, genre: str) -> GeneratedSong:
        """Produce a song from a text prompt + genre tag."""
        raise NotImplementedError
