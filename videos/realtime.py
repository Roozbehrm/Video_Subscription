import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def group_name(video_id) -> str:
    return f"video_{video_id}"


def broadcast(video_id, event: str, data: dict) -> None:
    try:
        layer = get_channel_layer()
        if layer is None:
            return
        async_to_sync(layer.group_send)(
            group_name(video_id),
            {"type": "video.event", "event": event, "data": data},
        )
    except Exception:
        logger.exception("Could not broadcast %s for video %s", event, video_id)
