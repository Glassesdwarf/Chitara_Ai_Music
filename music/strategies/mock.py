"""
Mock strategy — does NOT call any external API.

Returns a pre-bundled audio file from media/mock_songs/. Useful for offline
dev, deterministic tests, demos, and grading without burning real Suno credits.
"""
from __future__ import annotations

import random
import uuid
from pathlib import Path

from django.conf import settings
from .base import SongGenerationStrategy, GeneratedSong


class MockStrategy(SongGenerationStrategy):
    name = "mock"

    def _pick_audio(self) -> tuple[str, str | None]:
        mock_dir: Path = settings.MEDIA_ROOT / "mock_songs"
        mock_dir.mkdir(parents=True, exist_ok=True)
        candidates = sorted(mock_dir.glob("*.mp3")) + sorted(mock_dir.glob("*.wav"))
        if not candidates:
            return (
                "https://cdn.pixabay.com/download/audio/2022/03/15/audio_1718e49b14.mp3",
                None,
            )
        chosen = random.choice(candidates)
        rel = chosen.relative_to(settings.MEDIA_ROOT)
        return (settings.MEDIA_URL + str(rel).replace("\\", "/"), str(chosen))

    # ---- Public async-friendly API (parity with SunoStrategy) ----
    def submit_only(self, *, title: str, prompt: str, genre: str) -> str:
        print(f"[MOCK] Generating song with prompt: {prompt!r} (title={title!r}, genre={genre!r})") 
        task_id = f"mock-{uuid.uuid4().hex[:12]}"
        print(f"[MOCK] Returning task_id: {task_id}")  
        return task_id

    def check_status(self, task_id: str) -> dict:
        url, _ = self._pick_audio()
        print(f"[MOCK] check_status for task_id: {task_id} → READY (audio_url={url})")  
        return {
            "status": "READY",
            "progress": 100,
            "audio_url": url,
            "error": "",
        }

    # ---- Strategy interface (sync) ----
    def generate(self, *, title: str, prompt: str, genre: str) -> GeneratedSong:
        print(f"[MOCK] generate() called — title={title!r}, prompt={prompt!r}, genre={genre!r}")  
        url, local = self._pick_audio()
        print(f"[MOCK] generate() returning audio_url={url}")  
        return GeneratedSong(
            title=title, prompt=prompt, genre=genre,
            audio_url=url, local_path=local, strategy_used=self.name,
        )
