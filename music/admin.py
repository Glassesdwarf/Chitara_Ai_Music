from django.contrib import admin
from .models import Song


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "genre", "strategy_used", "is_public", "created_at")
    list_filter = ("genre", "strategy_used", "is_public", "created_at")
    search_fields = ("title", "prompt", "user__username", "share_token")
    readonly_fields = ("share_token", "created_at")
