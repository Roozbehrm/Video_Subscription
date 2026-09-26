from datetime import timedelta

import pytest
from django.utils import timezone

from subscriptions import services
from subscriptions.models import Payment, Subscription


@pytest.mark.django_db
def test_plans_are_public(api, basic_plan):
    r = api.get("/api/plans/")
    assert r.status_code == 200
    assert len(r.data) == 1


@pytest.mark.django_db
def test_buy_subscription(api, user, basic_plan):
    api.force_authenticate(user)
    r = api.post("/api/subscriptions/", {"plan_id": basic_plan.id}, format="json")
    assert r.status_code == 201
    assert r.data["status"] == "active"
    assert Payment.objects.filter(user=user, status="success").count() == 1

    me = api.get("/api/subscriptions/me/")
    assert me.status_code == 200
    assert me.data["plan"]["tier"] == 1


@pytest.mark.django_db
def test_cannot_buy_twice(api, user, basic_plan, premium_plan):
    api.force_authenticate(user)
    assert api.post("/api/subscriptions/", {"plan_id": basic_plan.id}, format="json").status_code == 201
    r = api.post("/api/subscriptions/", {"plan_id": premium_plan.id}, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_failed_payment_creates_no_subscription(api, user, basic_plan):
    api.force_authenticate(user)
    r = api.post(
        "/api/subscriptions/", {"plan_id": basic_plan.id, "payment_token": "fail"}, format="json"
    )
    assert r.status_code == 402
    assert not Subscription.objects.filter(user=user).exists()
    assert Payment.objects.get(user=user).status == "failed"


@pytest.mark.django_db
def test_cancel_keeps_access_until_end(api, user, basic_plan):
    sub = services.purchase_subscription(user, basic_plan)
    api.force_authenticate(user)
    r = api.post(f"/api/subscriptions/{sub.id}/cancel/")
    assert r.status_code == 200
    assert r.data["auto_renew"] is False
    assert r.data["is_canceled"] is True
    assert api.get("/api/subscriptions/me/").status_code == 200  # still active
    assert api.post(f"/api/subscriptions/{sub.id}/cancel/").status_code == 400  # already canceled


@pytest.mark.django_db
def test_cannot_touch_someone_elses_subscription(api, user, make_user, basic_plan):
    sub = services.purchase_subscription(user, basic_plan)
    api.force_authenticate(make_user("other@example.com"))
    assert api.post(f"/api/subscriptions/{sub.id}/cancel/").status_code == 404


@pytest.mark.django_db
def test_manual_renew_extends_end_date(api, user, basic_plan):
    sub = services.purchase_subscription(user, basic_plan)
    old_end = sub.end_date
    api.force_authenticate(user)
    r = api.post(f"/api/subscriptions/{sub.id}/renew/", {}, format="json")
    assert r.status_code == 200
    sub.refresh_from_db()
    assert sub.end_date == old_end + timedelta(days=30)
    assert Payment.objects.filter(user=user, kind="renewal", status="success").count() == 1


@pytest.mark.django_db
def test_process_due_auto_renews(user, basic_plan):
    sub = services.purchase_subscription(user, basic_plan)
    sub.end_date = timezone.now() - timedelta(minutes=1)
    sub.save()
    stats = services.process_due_subscriptions()
    assert stats["renewed"] == 1
    sub.refresh_from_db()
    assert sub.status == "active"
    assert sub.end_date > timezone.now()


@pytest.mark.django_db
def test_process_due_expires_canceled(user, basic_plan):
    sub = services.purchase_subscription(user, basic_plan)
    services.cancel_subscription(sub)
    sub.end_date = timezone.now() - timedelta(minutes=1)
    sub.save()
    stats = services.process_due_subscriptions()
    assert stats["expired"] == 1
    sub.refresh_from_db()
    assert sub.status == "expired"


@pytest.mark.django_db
def test_process_due_expires_on_failed_renewal(user, basic_plan, settings):
    sub = services.purchase_subscription(user, basic_plan)
    sub.end_date = timezone.now() - timedelta(minutes=1)
    sub.save()
    settings.PAYMENT_GATEWAY = "subscriptions.gateway.AlwaysFailGateway"
    stats = services.process_due_subscriptions()
    assert stats == {"renewed": 0, "expired": 1, "failed_payments": 1}
    sub.refresh_from_db()
    assert sub.status == "expired"


@pytest.mark.django_db
def test_can_rebuy_after_expiry(user, basic_plan):
    sub = services.purchase_subscription(user, basic_plan)
    sub.end_date = timezone.now() - timedelta(minutes=1)
    sub.save()
    new = services.purchase_subscription(user, basic_plan)
    assert new.pk != sub.pk
    sub.refresh_from_db()
    assert sub.status == "expired"


@pytest.mark.django_db
def test_payment_history(api, user, basic_plan):
    services.purchase_subscription(user, basic_plan)
    api.force_authenticate(user)
    r = api.get("/api/history/payments/")
    assert r.status_code == 200
    assert r.data["count"] == 1
    assert r.data["results"][0]["status"] == "success"
