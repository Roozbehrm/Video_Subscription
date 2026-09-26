from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from subscriptions import services
from subscriptions.tasks import process_due_subscriptions_task


@pytest.mark.django_db
def test_task_renews_due_subscription(user, basic_plan):
    sub = services.purchase_subscription(user, basic_plan)
    sub.end_date = timezone.now() - timedelta(minutes=1)
    sub.save()

    # .apply() runs the task locally (no broker/worker needed)
    result = process_due_subscriptions_task.apply().get()
    assert result["renewed"] == 1
    sub.refresh_from_db()
    assert sub.status == "active"
    assert sub.end_date > timezone.now()


@pytest.mark.django_db
def test_task_expires_canceled_subscription(user, basic_plan):
    sub = services.purchase_subscription(user, basic_plan)
    services.cancel_subscription(sub)
    sub.end_date = timezone.now() - timedelta(minutes=1)
    sub.save()

    result = process_due_subscriptions_task.apply().get()
    assert result["expired"] == 1


def test_task_is_scheduled_in_beat():
    entry = settings.CELERY_BEAT_SCHEDULE["process-due-subscriptions"]
    assert entry["task"] == "subscriptions.process_due_subscriptions"
    assert process_due_subscriptions_task.name == entry["task"]
