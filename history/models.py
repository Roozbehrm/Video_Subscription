from django.conf import settings
from django.db import models


class WatchHistory(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watch_history"
    )
    video = models.ForeignKey("videos.Video", on_delete=models.CASCADE, related_name="watch_history")
    progress_seconds = models.PositiveIntegerField(default=0)
    watched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-watched_at"]
        verbose_name_plural = "watch history"
        constraints = [
            models.UniqueConstraint(fields=["user", "video"], name="unique_history_per_user_video")
        ]
