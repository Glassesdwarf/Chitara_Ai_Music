from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("music", "0002_song_sharing"),
    ]

    operations = [
        migrations.AddField(
            model_name="song",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("GENERATING", "Generating"),
                    ("READY", "Ready"),
                    ("FAILED", "Failed"),
                ],
                default="READY",
                help_text="READY for finished tracks, GENERATING while Suno is working.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="song",
            name="task_id",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="song",
            name="error_message",
            field=models.TextField(blank=True, default=""),
        ),
    ]
