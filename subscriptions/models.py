from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Plan(models.Model):
    name = models.CharField(max_length=100, unique=True)
    tier = models.PositiveSmallIntegerField(
        help_text="Access level: 1=basic, 2=standard, 3=premium. A plan can watch videos with min_tier <= tier."
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["tier", "price"]

    def __str__(self):
        return f"{self.name} (tier {self.tier})"


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    auto_renew = models.BooleanField(default=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            # a user can have at most one active subscription at a time
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status="active"),
                name="one_active_subscription_per_user",
            )
        ]

    @property
    def is_canceled(self):
        return self.canceled_at is not None

    def __str__(self):
        return f"{self.user} - {self.plan.name} ({self.status})"


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    class Kind(models.TextChoices):
        PURCHASE = "purchase", "Purchase"
        RENEWAL = "renewal", "Renewal"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="payments")
    subscription = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PURCHASE)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    gateway_ref = models.CharField(max_length=100, blank=True)
    # Zarinpal (and other redirect gateways) issue an "authority" at request time,
    # used to look the payment back up when the bank redirects the user back to us.
    authority = models.CharField(max_length=100, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.user} {self.amount} {self.status}"
