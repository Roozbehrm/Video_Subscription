from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Video
from .realtime import group_name


class VideoConsumer(AsyncJsonWebsocketConsumer):
    """ws://host/ws/videos/<id>/  ->  live views / ratings / comments for one video."""

    async def connect(self):
        self.video_id = int(self.scope["url_route"]["kwargs"]["video_id"])
        self.group = group_name(self.video_id)
        stats = await self.get_stats()
        if stats is None:
            await self.close(code=4404)
            return
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send_json({"event": "snapshot", "data": stats})

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def video_event(self, event):
        await self.send_json({"event": event["event"], "data": event["data"]})

    @database_sync_to_async
    def get_stats(self):
        video = Video.objects.filter(pk=self.video_id, is_published=True).first()
        if video is None:
            return None
        return {
            "views_count": video.views_count,
            "avg_rating": video.avg_rating,
            "ratings_count": video.ratings_count,
            "comments_count": video.comments.count(),
        }
