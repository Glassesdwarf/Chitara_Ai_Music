from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from music.models import Song
from music.strategies import (
    MusicGenerationContext, MockStrategy, SunoStrategy, get_strategy,
)
from music.strategies.suno import SunoStrategyError


class StrategyFactoryTests(TestCase):
    @override_settings(MUSIC_STRATEGY="mock")
    def test_factory_returns_mock(self):
        self.assertIsInstance(get_strategy(), MockStrategy)

    @override_settings(MUSIC_STRATEGY="suno", SUNO_API_KEY="fake")
    def test_factory_returns_suno(self):
        self.assertIsInstance(get_strategy(), SunoStrategy)

    @override_settings(MUSIC_STRATEGY="suno", SUNO_API_KEY="")
    def test_suno_requires_api_key(self):
        with self.assertRaises(SunoStrategyError):
            get_strategy()

    def test_unknown_strategy_raises(self):
        with self.assertRaises(ValueError):
            get_strategy("does-not-exist")


class ContextTests(TestCase):
    def test_context_uses_mock_by_default(self):
        ctx = MusicGenerationContext(MockStrategy())
        result = ctx.generate(title="Test", prompt="happy beat", genre="pop")
        self.assertEqual(result.strategy_used, "mock")
        self.assertTrue(result.audio_url)

    @override_settings(SUNO_API_KEY="")
    def test_context_can_swap_strategies(self):
        ctx = MusicGenerationContext(MockStrategy())
        self.assertEqual(ctx.strategy.name, "mock")
        with self.assertRaises(SunoStrategyError):
            ctx.set_strategy("suno")


class SharingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="pw")
        self.other = User.objects.create_user("other", password="pw")
        self.song = Song.objects.create(
            user=self.owner, title="T", prompt="p", genre="pop",
            audio_url="https://example.com/x.mp3", strategy_used="mock",
        )

    def test_each_song_gets_unique_token(self):
        s2 = Song.objects.create(
            user=self.owner, title="T2", prompt="p", genre="pop", strategy_used="mock",
        )
        self.assertTrue(self.song.share_token)
        self.assertNotEqual(self.song.share_token, s2.share_token)

    def test_public_share_page_is_accessible_without_login(self):
        r = self.client.get(reverse("share", kwargs={"token": self.song.share_token}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.song.title)

    def test_disabled_share_returns_403(self):
        self.song.is_public = False
        self.song.save()
        r = self.client.get(reverse("share", kwargs={"token": self.song.share_token}))
        self.assertEqual(r.status_code, 403)

    def test_unknown_token_404s(self):
        r = self.client.get(reverse("share", kwargs={"token": "nope-nope"}))
        self.assertEqual(r.status_code, 404)

    def test_only_owner_can_toggle_sharing(self):
        self.client.login(username="other", password="pw")
        r = self.client.post(reverse("share_toggle", kwargs={"pk": self.song.pk}))
        self.assertEqual(r.status_code, 404)  # get_object_or_404(user=request.user)

    def test_owner_can_rotate_token(self):
        old = self.song.share_token
        self.client.login(username="owner", password="pw")
        self.client.post(reverse("rotate_share", kwargs={"pk": self.song.pk}))
        self.song.refresh_from_db()
        self.assertNotEqual(old, self.song.share_token)
