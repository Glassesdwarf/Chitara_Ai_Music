from django.db import migrations, models
import music.models


def backfill_share_tokens(apps, schema_editor):
    Song = apps.get_model("music", "Song")
    for song in Song.objects.all():
        # Each row needs its own unique token.
        song.share_token = music.models._make_share_token()
        song.save(update_fields=["share_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("music", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="song",
            name="is_public",
            field=models.BooleanField(
                default=True,
                help_text="If true, anyone with the share link can view and play the song.",
            ),
        ),
        # Step 1: add token column nullable so we can backfill unique values.
        migrations.AddField(
            model_name="song",
            name="share_token",
            field=models.CharField(max_length=32, null=True, editable=False),
        ),
        migrations.RunPython(backfill_share_tokens, migrations.RunPython.noop),
        # Step 2: enforce uniqueness + default for new rows.
        migrations.AlterField(
            model_name="song",
            name="share_token",
            field=models.CharField(
                max_length=32,
                unique=True,
                editable=False,
                default=music.models._make_share_token,
                help_text="Opaque, unguessable token used in public share URLs.",
            ),
        ),
    ]
