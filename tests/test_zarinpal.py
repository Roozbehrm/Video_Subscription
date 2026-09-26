from unittest.mock import patch

import pytest

from subscriptions import services, zarinpal
from subscriptions.models import Payment, Subscription


@pytest.mark.django_db
@patch("subscriptions.services.zarinpal.request_payment", return_value="A00000000000000000000000000000000001")
def test_start_checkout_returns_pay_url(mock_request, api, user, basic_plan):
    api.force_authenticate(user)
    r = api.post(
        "/api/subscriptions/checkout/zarinpal/", {"plan_id": basic_plan.id}, format="json"
    )
    assert r.status_code == 200
    assert r.data["pay_url"].endswith("A00000000000000000000000000000000001")
    payment = Payment.objects.get(user=user)
    assert payment.status == Payment.Status.PENDING
    assert payment.authority == "A00000000000000000000000000000000001"
    mock_request.assert_called_once()


@pytest.mark.django_db
def test_checkout_blocks_second_active_subscription(api, user, basic_plan):
    services.purchase_subscription(user, basic_plan)  # via mock gateway, instant
    api.force_authenticate(user)
    r = api.post(
        "/api/subscriptions/checkout/zarinpal/", {"plan_id": basic_plan.id}, format="json"
    )
    assert r.status_code == 400


@pytest.mark.django_db
@patch("subscriptions.services.zarinpal.verify_payment", return_value=(True, "REF123", "ok"))
@patch("subscriptions.services.zarinpal.request_payment", return_value="AUTH123")
def test_full_purchase_flow_via_callback(mock_req, mock_verify, api, user, basic_plan):
    api.force_authenticate(user)
    r = api.post(
        "/api/subscriptions/checkout/zarinpal/", {"plan_id": basic_plan.id}, format="json"
    )
    assert r.status_code == 200

    api.force_authenticate(None)  # callback is public: the bank redirects the raw browser
    r = api.get("/api/subscriptions/callback/zarinpal/?Authority=AUTH123&Status=OK")
    assert r.status_code == 200
    assert r.data["ref_id"] == "REF123"

    payment = Payment.objects.get(authority="AUTH123")
    assert payment.status == Payment.Status.SUCCESS
    sub = Subscription.objects.get(user=user)
    assert sub.status == Subscription.Status.ACTIVE
    assert payment.subscription_id == sub.id


@pytest.mark.django_db
@patch("subscriptions.services.zarinpal.request_payment", return_value="AUTH_CANCEL")
def test_callback_when_user_cancels_at_bank(mock_req, api, user, basic_plan):
    api.force_authenticate(user)
    api.post("/api/subscriptions/checkout/zarinpal/", {"plan_id": basic_plan.id}, format="json")

    r = api.get("/api/subscriptions/callback/zarinpal/?Authority=AUTH_CANCEL&Status=NOK")
    assert r.status_code == 402
    assert Payment.objects.get(authority="AUTH_CANCEL").status == Payment.Status.FAILED
    assert not Subscription.objects.filter(user=user).exists()


@pytest.mark.django_db
@patch("subscriptions.services.zarinpal.verify_payment", return_value=(False, "", "declined"))
@patch("subscriptions.services.zarinpal.request_payment", return_value="AUTH_BADVERIFY")
def test_callback_when_verify_fails(mock_req, mock_verify, api, user, basic_plan):
    api.force_authenticate(user)
    api.post("/api/subscriptions/checkout/zarinpal/", {"plan_id": basic_plan.id}, format="json")

    r = api.get("/api/subscriptions/callback/zarinpal/?Authority=AUTH_BADVERIFY&Status=OK")
    assert r.status_code == 402
    assert Payment.objects.get(authority="AUTH_BADVERIFY").status == Payment.Status.FAILED


@pytest.mark.django_db
@patch("subscriptions.services.zarinpal.verify_payment", return_value=(True, "REF999", "ok"))
def test_callback_is_idempotent(mock_verify, user, basic_plan):
    payment = Payment.objects.create(
        user=user, plan=basic_plan, amount=basic_plan.price,
        kind=Payment.Kind.PURCHASE, authority="AUTH_DUP",
    )
    services.confirm_zarinpal_checkout("AUTH_DUP", "OK")
    assert Subscription.objects.filter(user=user).count() == 1

    # user refreshes the callback page / bank re-sends the redirect
    services.confirm_zarinpal_checkout("AUTH_DUP", "OK")
    assert Subscription.objects.filter(user=user).count() == 1
    assert mock_verify.call_count == 1  # not re-verified once already SUCCESS


@pytest.mark.django_db
@patch("subscriptions.services.zarinpal.verify_payment", return_value=(True, "REFRENEW", "ok"))
def test_renewal_flow_via_callback(mock_verify, user, basic_plan):
    sub = services.purchase_subscription(user, basic_plan)
    old_end = sub.end_date

    payment = Payment.objects.create(
        user=user, plan=basic_plan, subscription=sub, amount=basic_plan.price,
        kind=Payment.Kind.RENEWAL, authority="AUTH_RENEW",
    )
    services.confirm_zarinpal_checkout("AUTH_RENEW", "OK")

    sub.refresh_from_db()
    assert sub.end_date > old_end
    assert Subscription.objects.filter(user=user).count() == 1  # extended, not duplicated


@pytest.mark.django_db
def test_callback_with_empty_authority_returns_clean_error(api):
    # No auth needed: this mirrors someone hitting the callback URL directly with no query params.
    r = api.get("/api/subscriptions/callback/zarinpal/")
    assert r.status_code == 400
    assert "authority" in r.data["detail"].lower()


@pytest.mark.django_db
def test_two_pending_mock_payments_dont_break_empty_authority_lookup(user, basic_plan):
    # Two payments made through the (non-Zarinpal) mock gateway both have authority="".
    # Confirming with an empty authority must not raise MultipleObjectsReturned.
    Payment.objects.create(user=user, plan=basic_plan, amount=basic_plan.price, kind=Payment.Kind.PURCHASE)
    Payment.objects.create(user=user, plan=basic_plan, amount=basic_plan.price, kind=Payment.Kind.PURCHASE)
    with pytest.raises(services.SubscriptionError):
        services.confirm_zarinpal_checkout("", "OK")
