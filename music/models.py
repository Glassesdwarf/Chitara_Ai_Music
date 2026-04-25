import secrets
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse


class Genre(models.TextChoices):
    POP = "pop", "Pop"
    ROCK = "rock", "Rock"
    JAZZ = "jazz", "Jazz"
    CLASSICAL = "classical", "Classical"
    HIPHOP = "hiphop", "Hip-Hop"
    ELECTRONIC = "electronic", "Electronic"
    LOFI = "lofi", "Lo-Fi"
    AMBIENT = "ambient", "Ambient"


def _make_share_token() -> str:
    
    return secrets.token_urlsafe(16)


class SongStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    GENERATING = "GENERATING", "Generating"
    READY = "READY", "Ready"
    FAILED = "FAILED", "Failed"


class Song(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="songs")
    title = models.CharField(max_length=200)
    prompt = models.TextField()
    genre = models.CharField(max_length=20, choices=Genre.choices, default=Genre.POP)
    audio_file = models.FileField(upload_to="songs/", blank=True, null=True)
    audio_url = models.URLField(blank=True)
    strategy_used = models.CharField(max_length=20, default="mock")
    created_at = models.DateTimeField(auto_now_add=True)

    # --- Async generation tracking ---
    status = models.CharField(
        max_length=20, choices=SongStatus.choices, default=SongStatus.READY,
        help_text="READY for finished tracks, GENERATING while Suno is working.",
    )
    task_id = models.CharField(max_length=128, blank=True, default="")
    error_message = models.TextField(blank=True, default="")

    # --- Sharing ---
    is_public = models.BooleanField(
        default=True,
        help_text="If true, anyone with the share link can view and play the song.",
    )
    share_token = models.CharField(
        max_length=32,
        unique=True,
        default=_make_share_token,
        editable=False,
        help_text="Opaque, unguessable token used in public share URLs.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.get_genre_display()})"

    @property
    def playable_url(self) -> str:
        """Return whichever URL is available (uploaded file or remote)."""
        if self.audio_file:
            return self.audio_file.url
        return self.audio_url or ""

    def get_share_path(self) -> str:
        """Relative URL of the public share page."""
        return reverse("share", kwargs={"token": self.share_token})

    def build_share_url(self, request) -> str:
        """Absolute share URL, suitable for copy-to-clipboard."""
        return request.build_absolute_uri(self.get_share_path())

    def rotate_share_token(self) -> str:
        """Invalidate any previously shared link by minting a new token."""
        self.share_token = _make_share_token()
        self.save(update_fields=["share_token"])
        return self.share_token
