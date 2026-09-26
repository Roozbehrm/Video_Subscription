from django.db import transaction
from django.db.models import Avg, Count, F
from django.http import FileResponse, Http404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from history.services import record_watch

from .models import Category, Comment, Rating, Video
from .permissions import HasVideoAccess
from .realtime import broadcast
from .serializers import (
    CategorySerializer,
    CommentSerializer,
    ProgressSerializer,
    RatingSerializer,
    VideoSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


class VideoViewSet(viewsets.ModelViewSet):
    serializer_class = VideoSerializer
    filterset_fields = {"category": ["exact"], "min_tier": ["exact", "lte"]}
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "views_count", "avg_rating"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAdminUser()]
        return super().get_permissions()  # custom actions declare their own

    def get_queryset(self):
        qs = Video.objects.select_related("category")
        if not (self.request.user and self.request.user.is_staff):
            qs = qs.filter(is_published=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    # ---- stream (protected content) ----
    @extend_schema(responses={200: OpenApiResponse(description="Raw video file bytes (video/mp4)")})
    @action(
        detail=True, methods=["get"],
        permission_classes=[permissions.IsAuthenticated, HasVideoAccess],
    )
    def stream(self, request, pk=None):
        """Download/stream the video file. Requires an appropriate active subscription."""
        video = self.get_object()  # runs HasVideoAccess.has_object_permission
        if not video.video_file:
            raise Http404("This video has no file.")

        Video.objects.filter(pk=video.pk).update(views_count=F("views_count") + 1)
        video.refresh_from_db(fields=["views_count"])
        record_watch(request.user, video)
        broadcast(video.pk, "view", {"views_count": video.views_count})

        return FileResponse(video.video_file.open("rb"), content_type="video/mp4")

    @extend_schema(request=ProgressSerializer, responses=ProgressSerializer)
    @action(
        detail=True, methods=["post"],
        permission_classes=[permissions.IsAuthenticated, HasVideoAccess],
    )
    def progress(self, request, pk=None):
        """Save the playback position for the watch history."""
        video = self.get_object()
        ser = ProgressSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        record_watch(request.user, video, ser.validated_data["progress_seconds"])
        return Response({"progress_seconds": ser.validated_data["progress_seconds"]})

    # ---- rating ----
    @extend_schema(
        request=RatingSerializer,
        responses=OpenApiResponse(description="{'score': int, 'avg_rating': float, 'ratings_count': int}"),
    )
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def rate(self, request, pk=None):
        """Create or update the current user's rating (1-5)."""
        video = self.get_object()
        ser = RatingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        score = ser.validated_data["score"]

        with transaction.atomic():
            Rating.objects.update_or_create(
                user=request.user, video=video, defaults={"score": score}
            )
            agg = video.ratings.aggregate(avg=Avg("score"), count=Count("id"))
            video.avg_rating = round(agg["avg"] or 0, 2)
            video.ratings_count = agg["count"]
            video.save(update_fields=["avg_rating", "ratings_count"])
            payload = {"avg_rating": video.avg_rating, "ratings_count": video.ratings_count}
            transaction.on_commit(lambda: broadcast(video.pk, "rating", payload))

        return Response({"score": score, **payload})

  
    @extend_schema(methods=["GET"], responses=CommentSerializer(many=True))
    @extend_schema(methods=["POST"], request=CommentSerializer, responses=CommentSerializer)
    @action(
        detail=True, methods=["get", "post"],
        permission_classes=[permissions.IsAuthenticatedOrReadOnly],
    )
    def comments(self, request, pk=None):
        video = self.get_object()

        if request.method == "GET":
            qs = Comment.objects.filter(video=video).select_related("user")
            page = self.paginate_queryset(qs)
            ser = CommentSerializer(page, many=True)
            return self.get_paginated_response(ser.data)

        ser = CommentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        comment = ser.save(user=request.user, video=video)
        data = CommentSerializer(comment).data
        payload = {
            "id": data["id"],
            "user": data["user"],
            "body": data["body"],
            "created_at": comment.created_at.isoformat(),
        }
        transaction.on_commit(lambda: broadcast(video.pk, "comment", payload))
        return Response(data, status=201)
