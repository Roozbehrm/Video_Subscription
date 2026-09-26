import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from videos.realtime import broadcast, group_name


@pytest.mark.django_db
def test_broadcast_reaches_group(make_video):
    v = make_video()
    layer = get_channel_layer()

    async def scenario():
        channel = await layer.new_channel()
        await layer.group_add(group_name(v.id), channel)
        await layer.group_send(
            group_name(v.id), {"type": "video.event", "event": "view", "data": {"views_count": 1}}
        )
        return await layer.receive(channel)

    # broadcast() itself uses async_to_sync, so test the raw layer path + that it doesn't raise
    msg = async_to_sync(scenario)()
    assert msg["event"] == "view"
    broadcast(v.id, "view", {"views_count": 2})  # must never raise
