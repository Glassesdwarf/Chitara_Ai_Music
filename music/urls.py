from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("generate/", views.generate, name="generate"),
    path("songs/<int:pk>/", views.song_detail, name="song_detail"),
    path("songs/<int:pk>/status/", views.song_status, name="song_status"),
    path("songs/<int:pk>/download/", views.download, name="download"),

    # Sharing
    path("songs/<int:pk>/share-toggle/", views.share_toggle, name="share_toggle"),
    path("songs/<int:pk>/rotate-share/", views.rotate_share, name="rotate_share"),
    path("s/<str:token>/", views.share_view, name="share"),
    path("s/<str:token>/download/", views.share_download, name="share_download"),
]
