"""
Suno strategy — real generation via the sunoapi.org gateway.

This implementation targets the sunoapi.org contract:
    POST {base}/api/v1/generate                       -> { code, msg, data: { taskId } }
    GET  {base}/api/v1/generate/record-info?taskId=X  -> { code, msg, data: { status, response: { sunoData: [{ audioUrl, ... }] } } }

Required env:
    SUNO_API_KEY   — bearer token from your sunoapi.org "API Key" page
    SUNO_API_BASE  — https://api.sunoapi.org

If you switch to a different gateway later, change the URL paths below
and the response field accessors — no changes needed in the rest of the
codebase, because the Strategy contract is preserved.
"""
from __future__ import annotations
import time
import requests
from django.conf import settings
from .base import SongGenerationStrategy, GeneratedSong


class SunoStrategyError(RuntimeError):
    pass


# Maps sunoapi.org status enum -> 0..100 progress hint for the UI.
_PROGRESS_MAP = {
    "PENDING": 10,
    "TEXT_SUCCESS": 40,
    "FIRST_SUCCESS": 80,
    "SUCCESS": 100,
}

_FAILURE_STATUSES = {
    "CREATE_TASK_FAILED",
    "GENERATE_AUDIO_FAILED",
    "CALLBACK_EXCEPTION",
    "SENSITIVE_WORD_ERROR",
}


class SunoStrategy(SongGenerationStrategy):
    name = "suno"
    poll_interval = 4       # seconds between polls (sync mode)
    poll_timeout = 240      # seconds total wait (sync mode)
    model = "V4"
    # sunoapi.org requires a callBackUrl field in the payload. We poll
    # instead of receiving callbacks, so a placeholder is fine.
    callback_url = "https://example.com/suno-callback"

    def __init__(self, api_key: str | None = None, api_base: str | None = None):
        self.api_key = api_key or settings.SUNO_API_KEY
        self.api_base = (api_base or settings.SUNO_API_BASE).rstrip("/")
        if not self.api_key:
            raise SunoStrategyError(
                "SUNO_API_KEY is not set. Add it to .env or switch "
                "MUSIC_STRATEGY=mock for local dev."
            )

    # ---- HTTP helpers ----
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _submit(self, *, prompt: str, title: str, genre: str) -> str:
        print(f"[SUNO] Calling Suno API with prompt: {prompt!r} (title={title!r}, genre={genre!r})")
        payload = {
            "prompt": prompt,
            "style": genre,
            "title": title,
            "customMode": True,
            "instrumental": False,
            "model": self.model,
            "callBackUrl": self.callback_url,
        }
        r = requests.post(
            f"{self.api_base}/api/v1/generate",
            json=payload, headers=self._headers(), timeout=30,
        )
        print(f"[SUNO] POST /generate → HTTP {r.status_code}")

        if r.status_code >= 500:
            raise SunoStrategyError(
                f"Suno provider is temporarily unavailable (HTTP {r.status_code}). "
                "Please try again in a few minutes."
            )
        try:
            data = r.json()
        except ValueError:
            raise SunoStrategyError(
                f"Suno returned a non-JSON response (HTTP {r.status_code}). "
                "Check that SUNO_API_BASE is correct."
            )
        if r.status_code >= 400:
            raise SunoStrategyError(
                f"Suno submit failed [{r.status_code}]: {data.get('msg', data)}"
            )
        if data.get("code") and data["code"] != 200:
            raise SunoStrategyError(f"Suno submit error: {data.get('msg', data)}")

        task_id = (
            (data.get("data") or {}).get("taskId")
            or data.get("taskId")
            or data.get("id")
        )
        if not task_id:
            raise SunoStrategyError(f"No taskId in Suno response: {data}")
        print(f"[SUNO] Got task_id from Suno: {task_id}")

        return task_id

    def _check(self, task_id: str) -> dict:
        """Single status check. Returns a normalized dict for the UI."""
        r = requests.get(
            f"{self.api_base}/api/v1/generate/record-info",
            params={"taskId": task_id},
            headers=self._headers(),
            timeout=30,
        )
        if r.status_code >= 500:
            print(f"[SUNO] Polling status for task_id: {task_id} → server busy (HTTP {r.status_code})")
            return {"status": "PENDING", "progress": 5, "audio_url": "", "error": ""}
        try:
            payload = r.json()
        except ValueError:
            raise SunoStrategyError(
                f"Suno poll returned non-JSON (HTTP {r.status_code})."
            )
        if r.status_code >= 400:
            raise SunoStrategyError(
                f"Suno poll failed [{r.status_code}]: {payload.get('msg', payload)}"
            )

        data = payload.get("data") or {}
        status = (data.get("status") or "PENDING").upper()
        response = data.get("response") or {}
        suno_items = response.get("sunoData") or []

        audio_url = ""
        if suno_items:
            first = suno_items[0]
            audio_url = (
                first.get("audioUrl")
                or first.get("streamAudioUrl")
                or first.get("sourceAudioUrl")
                or ""
            )

        print(f"[SUNO] Polling status for task_id: {task_id} → {status} (audio_url={'yes' if audio_url else 'not yet'})")

        return {
            "status": status,
            "progress": _PROGRESS_MAP.get(status, 5),
            "audio_url": audio_url,
            "error": data.get("errorMessage", "") or "",
        }


    # ---- Public async-friendly API (used by views for progress polling) ----
    def submit_only(self, *, title: str, prompt: str, genre: str) -> str:
        """Submit and return task_id. No polling — return immediately."""
        return self._submit(prompt=prompt, title=title, genre=genre)

    def check_status(self, task_id: str) -> dict:
        """One status check. Used by the /status/ JSON endpoint."""
        result = self._check(task_id)
        if result["status"] in _FAILURE_STATUSES:
            return {
                "status": "FAILED",
                "progress": 0,
                "audio_url": "",
                "error": result.get("error") or result["status"],
            }
        if result["status"] == "SUCCESS" and result["audio_url"]:
            print(f"[SUNO] task_id {task_id} READY → {result['audio_url']}")

            return {
                "status": "READY",
                "progress": 100,
                "audio_url": result["audio_url"],
                "error": "",
            }
        return {
            "status": "GENERATING",
            "progress": result["progress"],
            "audio_url": result["audio_url"],
            "error": "",
        }

    # ---- Strategy interface (sync; kept for backward compat / tests) ----
    def generate(self, *, title: str, prompt: str, genre: str) -> GeneratedSong:
        task_id = self._submit(prompt=prompt, title=title, genre=genre)
        deadline = time.time() + self.poll_timeout
        while time.time() < deadline:
            r = self._check(task_id)
            if r["status"] in _FAILURE_STATUSES:
                raise SunoStrategyError(
                    f"Suno generation failed: {r['status']} — {r.get('error', '')}"
                )
            if r["status"] == "SUCCESS" and r["audio_url"]:
                return GeneratedSong(
                    title=title, prompt=prompt, genre=genre,
                    audio_url=r["audio_url"], strategy_used=self.name,
                )
            time.sleep(self.poll_interval)
        raise SunoStrategyError(
            f"Suno generation timed out after {self.poll_timeout}s"
        )
