from django.core.management.base import BaseCommand

from subscriptions.models import Plan

# (name, tier, duration_days, price)
DEFAULT_PLANS = [
    ("Basic - 1 Month", 1, 30, "50000"),
    ("Basic - 3 Months", 1, 90, "135000"),
    ("Basic - 6 Months", 1, 180, "250000"),
    ("Basic - 1 Year", 1, 365, "450000"),
    ("Standard - 1 Month", 2, 30, "90000"),
    ("Standard - 3 Months", 2, 90, "240000"),
    ("Standard - 6 Months", 2, 180, "450000"),
    ("Standard - 1 Year", 2, 365, "800000"),
    ("Premium - 1 Month", 3, 30, "150000"),
    ("Premium - 3 Months", 3, 90, "400000"),
    ("Premium - 6 Months", 3, 180, "750000"),
    ("Premium - 1 Year", 3, 365, "1400000"),
]


class Command(BaseCommand):
    help = "Create (or update) a starter set of plans: Basic/Standard/Premium x 1/3/6/12 months."

    def handle(self, *args, **options):
        created, updated = 0, 0
        for name, tier, duration_days, price in DEFAULT_PLANS:
            plan, was_created = Plan.objects.update_or_create(
                name=name,
                defaults={
                    "tier": tier,
                    "duration_days": duration_days,
                    "price": price,
                    "is_active": True,
                },
            )
            created += was_created
            updated += not was_created
        self.stdout.write(self.style.SUCCESS(f"Plans seeded: {created} created, {updated} updated."))
