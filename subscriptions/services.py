from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from . import zarinpal
from .gateway import PaymentResult, get_gateway
from .models import Payment, Plan, Subscription


class SubscriptionError(Exception):
    """Business rule violation (HTTP 400)."""


class PaymentFailed(SubscriptionError):
    """The gateway declined / failed (HTTP 402)."""



def active_subscriptions(user, now=None):
    now = now or timezone.now()
    return Subscription.objects.filter(
        user=user, status=Subscription.Status.ACTIVE, end_date__gt=now
    )


def get_user_tier(user, now=None) -> int:
    if not user or not user.is_authenticated:
        return 0
    sub = active_subscriptions(user, now).select_related("plan").order_by("-plan__tier").first()
    return sub.plan.tier if sub else 0


def user_can_access(user, video) -> bool:
    if video.min_tier == 0:
        return True
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return get_user_tier(user) >= video.min_tier



def _charge(user, plan: Plan, kind: str, token=None) -> Payment:
    """Charge the gateway and persist the Payment (success OR failure)."""
    payment = Payment.objects.create(user=user, plan=plan, amount=plan.price, kind=kind)
    try:
        result = get_gateway().charge(
            user=user, amount=plan.price, token=token, description=f"{kind}: {plan.name}"
        )
    except Exception as exc: 
        result = PaymentResult(False, "", str(exc))
    payment.gateway_ref = result.reference
    payment.status = Payment.Status.SUCCESS if result.success else Payment.Status.FAILED
    payment.save(update_fields=["gateway_ref", "status"])
    if not result.success:
        payment._failure_message = result.message
    return payment


def _failure_message(payment: Payment) -> str:
    return getattr(payment, "_failure_message", "") or "Payment failed."



def expire_stale_subscriptions(user=None, now=None) -> int:
    now = now or timezone.now()
    qs = Subscription.objects.filter(status=Subscription.Status.ACTIVE, end_date__lte=now)
    if user is not None:
        qs = qs.filter(user=user)
    return qs.update(status=Subscription.Status.EXPIRED)


def purchase_subscription(user, plan: Plan, payment_token=None, auto_renew=True) -> Subscription:
    if not plan.is_active:
        raise SubscriptionError("This plan is not available.")

    now = timezone.now()
    expire_stale_subscriptions(user, now)
    if active_subscriptions(user, now).exists():
        raise SubscriptionError("You already have an active subscription.")

    payment = _charge(user, plan, Payment.Kind.PURCHASE, payment_token)
    if payment.status != Payment.Status.SUCCESS:
        raise PaymentFailed(_failure_message(payment))

    try:
        with transaction.atomic():
            sub = Subscription.objects.create(
                user=user,
                plan=plan,
                start_date=now,
                end_date=now + timedelta(days=plan.duration_days),
                auto_renew=auto_renew,
            )
            payment.subscription = sub
            payment.save(update_fields=["subscription"])
    except IntegrityError:

        raise SubscriptionError("You already have an active subscription.")
    return sub


def cancel_subscription(sub: Subscription) -> Subscription:
    """Cancel = stop auto renewal. Access stays until end_date."""
    if sub.status != Subscription.Status.ACTIVE or sub.end_date <= timezone.now():
        raise SubscriptionError("Only an active subscription can be canceled.")
    if sub.is_canceled:
        raise SubscriptionError("Subscription is already canceled.")
    sub.auto_renew = False
    sub.canceled_at = timezone.now()
    sub.save(update_fields=["auto_renew", "canceled_at"])
    return sub


def renew_subscription(sub: Subscription, payment_token=None) -> Subscription:

    now = timezone.now()
    if sub.status != Subscription.Status.ACTIVE or sub.end_date <= now:
        raise SubscriptionError("Only an active subscription can be renewed. Buy a new one instead.")

    payment = _charge(sub.user, sub.plan, Payment.Kind.RENEWAL, payment_token)
    if payment.status != Payment.Status.SUCCESS:
        raise PaymentFailed(_failure_message(payment))

    with transaction.atomic():
        locked = Subscription.objects.select_for_update().get(pk=sub.pk)
        locked.end_date = locked.end_date + timedelta(days=locked.plan.duration_days)
        locked.auto_renew = True
        locked.canceled_at = None
        locked.save(update_fields=["end_date", "auto_renew", "canceled_at"])
        payment.subscription = locked
        payment.save(update_fields=["subscription"])
    return locked


def _rial_amount(plan: Plan) -> int:
    return int(plan.price) * settings.TOMAN_TO_RIAL


def start_zarinpal_checkout(user, plan: Plan, kind: str, subscription: Subscription = None) -> str:

    if not plan.is_active:
        raise SubscriptionError("This plan is not available.")

    now = timezone.now()
    if kind == Payment.Kind.PURCHASE:
        expire_stale_subscriptions(user, now)
        if active_subscriptions(user, now).exists():
            raise SubscriptionError("You already have an active subscription.")
    else:
        if subscription is None or subscription.user_id != user.id:
            raise SubscriptionError("Subscription not found.")
        if subscription.status != Subscription.Status.ACTIVE or subscription.end_date <= now:
            raise SubscriptionError("Only an active subscription can be renewed.")

    payment = Payment.objects.create(
        user=user, plan=plan, subscription=subscription, amount=plan.price, kind=kind
    )
    callback_url = settings.SITE_BASE_URL + reverse("zarinpal-callback")
    try:
        authority = zarinpal.request_payment(
            amount_rial=_rial_amount(plan),
            description=f"{plan.name} subscription ({kind})",
            callback_url=callback_url,
            email=getattr(user, "email", ""),
        )
    except zarinpal.ZarinpalError as exc:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
        raise PaymentFailed(str(exc))

    payment.authority = authority
    payment.save(update_fields=["authority"])
    return zarinpal.start_pay_url(authority)


def confirm_zarinpal_checkout(authority: str, bank_status: str) -> Payment:

    if not authority:
        raise SubscriptionError("Missing or invalid payment authority.")

    try:
        payment = Payment.objects.select_related("plan", "user", "subscription").get(
            authority=authority
        )
    except Payment.DoesNotExist:
        raise SubscriptionError("Unknown payment authority.")

    if payment.status == Payment.Status.SUCCESS:
        return payment 

    if bank_status != "OK":
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
        raise PaymentFailed("Payment was canceled or declined at the bank.")

    ok, ref_id, message = zarinpal.verify_payment(
        amount_rial=_rial_amount(payment.plan), authority=authority
    )
    if not ok:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
        raise PaymentFailed(message)

    now = timezone.now()
    with transaction.atomic():
        payment.status = Payment.Status.SUCCESS
        payment.gateway_ref = ref_id
        if payment.kind == Payment.Kind.PURCHASE:
            expire_stale_subscriptions(payment.user, now)
            if active_subscriptions(payment.user, now).exists():
                
                payment.save(update_fields=["status", "gateway_ref"])
                raise SubscriptionError(
                    "You already have an active subscription; this payment was recorded "
                    "but no new subscription was created."
                )
            sub = Subscription.objects.create(
                user=payment.user,
                plan=payment.plan,
                start_date=now,
                end_date=now + timedelta(days=payment.plan.duration_days),
            )
            payment.subscription = sub
        else:
            sub = Subscription.objects.select_for_update().get(pk=payment.subscription_id)
            sub.end_date = sub.end_date + timedelta(days=payment.plan.duration_days)
            sub.auto_renew = True
            sub.canceled_at = None
            sub.save(update_fields=["end_date", "auto_renew", "canceled_at"])
        payment.save(update_fields=["status", "gateway_ref", "subscription"])
    return payment


def process_due_subscriptions(now=None) -> dict:

    now = now or timezone.now()
    stats = {"renewed": 0, "expired": 0, "failed_payments": 0}
    due_ids = list(
        Subscription.objects.filter(
            status=Subscription.Status.ACTIVE, end_date__lte=now
        ).values_list("pk", flat=True)
    )
    for pk in due_ids:
        sub = Subscription.objects.select_related("plan", "user").get(pk=pk)
        if sub.status != Subscription.Status.ACTIVE or sub.end_date > now:
            continue 

        if sub.auto_renew and sub.plan.is_active:
            payment = _charge(sub.user, sub.plan, Payment.Kind.RENEWAL)
            if payment.status == Payment.Status.SUCCESS:
                with transaction.atomic():
                    locked = Subscription.objects.select_for_update().get(pk=pk)
                    new_end = locked.end_date + timedelta(days=locked.plan.duration_days)
                    if new_end <= now:  # was lapsed for a long time: restart from now
                        new_end = now + timedelta(days=locked.plan.duration_days)
                    locked.end_date = new_end
                    locked.save(update_fields=["end_date"])
                    payment.subscription = locked
                    payment.save(update_fields=["subscription"])
                stats["renewed"] += 1
                continue
            stats["failed_payments"] += 1

        sub.status = Subscription.Status.EXPIRED
        sub.save(update_fields=["status"])
        stats["expired"] += 1
    return stats
