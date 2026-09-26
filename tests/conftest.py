import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from subscriptions.models import Plan
from videos.models import Video


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def make_user(django_user_model):
    def _make(email="u@example.com", **kwargs):
        return django_user_model.objects.create_user(
            email=email, username=email.split("@")[0], password="pass12345!", **kwargs
        )

    return _make


@pytest.fixture
def user(make_user):
    return make_user()


@pytest.fixture
def admin_user_(make_user):
    return make_user("admin@example.com", is_staff=True)


@pytest.fixture
def basic_plan(db):
    return Plan.objects.create(name="Basic", tier=1, price="10.00", duration_days=30)


@pytest.fixture
def premium_plan(db):
    return Plan.objects.create(name="Premium", tier=3, price="30.00", duration_days=30)


@pytest.fixture
def make_video(db):
    def _make(title="Video", min_tier=0, **kwargs):
        return Video.objects.create(
            title=title,
            min_tier=min_tier,
            video_file=SimpleUploadedFile("a.mp4", b"fake-video-bytes", content_type="video/mp4"),
            **kwargs,
        )

    return _make
