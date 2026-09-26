from datetime import timedelta

import pytest
from django.utils import timezone

from subscriptions import services


@pytest.mark.django_db
def test_stream_requires_login(api, make_video):
    v = make_video(min_tier=0)
    assert api.get(f"/api/videos/{v.id}/stream/").status_code == 401


@pytest.mark.django_db
def test_free_video_streams_and_counts_view(api, user, make_video):
    v = make_video(min_tier=0)
    api.force_authenticate(user)
    r = api.get(f"/api/videos/{v.id}/stream/")
    assert r.status_code == 200
    v.refresh_from_db()
    assert v.views_count == 1
    hist = api.get("/api/history/watch/")
    assert hist.data["count"] == 1


@pytest.mark.django_db
def test_paid_video_forbidden_without_subscription(api, user, make_video):
    v = make_video(min_tier=1)
    api.force_authenticate(user)
    assert api.get(f"/api/videos/{v.id}/stream/").status_code == 403


@pytest.mark.django_db
def test_tier_is_respected(api, user, make_video, basic_plan):
    services.purchase_subscription(user, basic_plan)
    tier1 = make_video("t1", min_tier=1)
    tier3 = make_video("t3", min_tier=3)
    api.force_authenticate(user)
    assert api.get(f"/api/videos/{tier1.id}/stream/").status_code == 200
    assert api.get(f"/api/videos/{tier3.id}/stream/").status_code == 403


@pytest.mark.django_db
def test_expired_subscription_loses_access(api, user, make_video, basic_plan):
    sub = services.purchase_subscription(user, basic_plan)
    sub.end_date = timezone.now() - timedelta(hours=1)
    sub.save()
    v = make_video(min_tier=1)
    api.force_authenticate(user)
    assert api.get(f"/api/videos/{v.id}/stream/").status_code == 403


@pytest.mark.django_db
def test_list_shows_has_access_flag(api, user, make_video, basic_plan):
    make_video("free", min_tier=0)
    make_video("paid", min_tier=3)
    api.force_authenticate(user)
    r = api.get("/api/videos/")
    flags = {v["title"]: v["has_access"] for v in r.data["results"]}
    assert flags == {"free": True, "paid": False}
    assert all("video_file" not in v for v in r.data["results"])


@pytest.mark.django_db
def test_only_admin_can_create_video(api, user, admin_user_):
    payload = {"title": "New", "min_tier": 1}
    api.force_authenticate(user)
    assert api.post("/api/videos/", payload, format="json").status_code == 403
    api.force_authenticate(admin_user_)
    assert api.post("/api/videos/", payload, format="json").status_code == 201
