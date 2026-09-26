from rest_framework import serializers

from subscriptions.services import get_user_tier

from .models import Category, Comment, Video


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name")


class VideoSerializer(serializers.ModelSerializer):

    video_file = serializers.FileField(write_only=True, required=False)
    has_access = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = (
            "id", "title", "description", "video_file", "category", "min_tier",
            "is_published", "views_count", "ratings_count", "avg_rating",
            "has_access", "created_at",
        )
        read_only_fields = ("views_count", "ratings_count", "avg_rating", "created_at")

    def get_has_access(self, obj) -> bool:
        if obj.min_tier == 0:
            return True
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        # compute the user's tier once per request (avoid N+1 on lists)
        tier = self.context.setdefault("_user_tier", get_user_tier(user))
        return tier >= obj.min_tier


class RatingSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=1, max_value=5)


class ProgressSerializer(serializers.Serializer):
    progress_seconds = serializers.IntegerField(min_value=0)


class CommentSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Comment
        fields = ("id", "user", "body", "created_at")
        read_only_fields = ("id", "user", "created_at")
