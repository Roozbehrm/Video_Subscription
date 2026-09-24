from rest_framework import serializers

from .models import WatchHistory


class WatchHistorySerializer(serializers.ModelSerializer):
    video_title = serializers.CharField(source="video.title", read_only=True)

    class Meta:
        model = WatchHistory
        fields = ("id", "video", "video_title", "progress_seconds", "watched_at")