import os
import mimetypes
import requests
from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import GenerateSongForm
from .models import Genre, Song, SongStatus
from .strategies import MusicGenerationContext


# ---------- helpers ----------

def _stream_song_as_attachment(song: Song):
    """Shared download helper used by both authenticated + share routes."""
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in song.title) or "song"

    if song.audio_file:
        f = song.audio_file.open("rb")
        ext = os.path.splitext(song.audio_file.name)[1] or ".mp3"
        return FileResponse(f, as_attachment=True, filename=f"{safe_name}{ext}")

    if song.audio_url:
        try:
            r = requests.get(song.audio_url, stream=True, timeout=60)
            r.raise_for_status()
        except requests.RequestException as exc:
            raise Http404(f"Could not fetch remote audio: {exc}")
        path = urlparse(song.audio_url).path
        ext = os.path.splitext(path)[1] or ".mp3"
        content_type = (
            r.headers.get("Content-Type")
            or mimetypes.guess_type(f"x{ext}")[0]
            or "audio/mpeg"
        )
        resp = HttpResponse(r.iter_content(chunk_size=8192), content_type=content_type)
        resp["Content-Disposition"] = f'attachment; filename="{safe_name}{ext}"'
        return resp

    raise Http404("This song has no audio attached.")


# ---------- public + auth views ----------

def home(request):
    """Public landing page — shows recent public songs + the genre filter."""
    genre = request.GET.get("genre", "")
    songs = Song.objects.all()
    if genre:
        songs = songs.filter(genre=genre)
    return render(request, "music/home.html", {
        "songs": songs[:30],
        "genres": Genre.choices,
        "selected_genre": genre,
    })


@login_required
def generate(request):
    """
    Submit a generation job and redirect immediately to the song detail
    page. The detail page polls /songs/<id>/status/ for progress and
    triggers a browser notification when ready.
    """
    if request.method == "POST":
        form = GenerateSongForm(request.POST)
        if form.is_valid():
            ctx = MusicGenerationContext()  # uses settings.MUSIC_STRATEGY
            try:
                task_id = ctx.strategy.submit_only(
                    title=form.cleaned_data["title"],
                    prompt=form.cleaned_data["prompt"],
                    genre=form.cleaned_data["genre"],
                )
            except Exception as exc:  # noqa: BLE001
                messages.error(request, f"Generation failed: {exc}")
                return render(request, "music/generate.html", {
                    "form": form, "strategy": settings.MUSIC_STRATEGY,
                })

            song = Song.objects.create(
                user=request.user,
                title=form.cleaned_data["title"],
                prompt=form.cleaned_data["prompt"],
                genre=form.cleaned_data["genre"],
                strategy_used=ctx.strategy.name,
                task_id=task_id,
                status=SongStatus.GENERATING,
            )
            return redirect("song_detail", pk=song.pk)
    else:
        form = GenerateSongForm()

    return render(request, "music/generate.html", {
        "form": form, "strategy": settings.MUSIC_STRATEGY,
    })


def song_detail(request, pk: int):
    song = get_object_or_404(Song, pk=pk)
    share_url = song.build_share_url(request) if song.is_public else ""
    return render(request, "music/song_detail.html", {
        "song": song,
        "share_url": share_url,
        "is_owner": request.user.is_authenticated and song.user_id == request.user.id,
    })


@login_required
def song_status(request, pk: int):
    """
    JSON endpoint polled by the song detail page to render a progress bar.
    Returns: { status, progress, audio_url, error }
    """
    song = get_object_or_404(Song, pk=pk, user=request.user)

    # Already finalized — return cached values.
    if song.status in (SongStatus.READY, SongStatus.FAILED):
        return JsonResponse({
            "status": song.status,
            "progress": 100 if song.status == SongStatus.READY else 0,
            "audio_url": song.playable_url,
            "error": song.error_message,
        })

    # Otherwise, ask the active strategy for an update.
    ctx = MusicGenerationContext()
    try:
        result = ctx.strategy.check_status(song.task_id)
    except Exception as exc:  # noqa: BLE001
        song.status = SongStatus.FAILED
        song.error_message = str(exc)
        song.save(update_fields=["status", "error_message"])
        return JsonResponse({
            "status": "FAILED", "progress": 0, "audio_url": "", "error": str(exc),
        })

    if result["status"] == "READY" and result["audio_url"]:
        song.audio_url = result["audio_url"]
        song.status = SongStatus.READY
        song.save(update_fields=["audio_url", "status"])
    elif result["status"] == "FAILED":
        song.status = SongStatus.FAILED
        song.error_message = result.get("error", "")
        song.save(update_fields=["status", "error_message"])

    return JsonResponse({
        "status": song.status,
        "progress": result["progress"],
        "audio_url": song.playable_url,
        "error": song.error_message,
    })


def download(request, pk: int):
    """
    Stream the song to the browser as an attachment (owner / authenticated route).
    """
    song = get_object_or_404(Song, pk=pk)
    return _stream_song_as_attachment(song)


# ---------- sharing ----------

@login_required
@require_POST
def share_toggle(request, pk: int):
    """Owner-only: enable or disable public sharing for a song."""
    song = get_object_or_404(Song, pk=pk, user=request.user)
    song.is_public = not song.is_public
    song.save(update_fields=["is_public"])
    messages.success(
        request,
        "Sharing enabled — anyone with the link can listen." if song.is_public
        else "Sharing disabled — the share link no longer works.",
    )
    return redirect("song_detail", pk=song.pk)


@login_required
@require_POST
def rotate_share(request, pk: int):
    """Owner-only: invalidate the old share link and mint a new one."""
    song = get_object_or_404(Song, pk=pk, user=request.user)
    song.rotate_share_token()
    messages.success(request, "Share link rotated. The previous link no longer works.")
    return redirect("song_detail", pk=song.pk)


def share_view(request, token: str):
    """
    Public, no-login page for a shared song. Resolves by opaque token,
    so song IDs are not enumerable from the share URL.
    """
    song = get_object_or_404(Song, share_token=token)
    if not song.is_public:
        return HttpResponseForbidden(
            "This share link has been disabled by the owner."
        )
    return render(request, "music/share.html", {"song": song})


def share_download(request, token: str):
    """Public download via share token."""
    song = get_object_or_404(Song, share_token=token)
    if not song.is_public:
        return HttpResponseForbidden("This share link has been disabled by the owner.")
    return _stream_song_as_attachment(song)
