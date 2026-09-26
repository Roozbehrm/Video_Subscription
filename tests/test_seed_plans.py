import pytest
from django.core.management import call_command

from subscriptions.models import Plan


@pytest.mark.django_db
def test_seed_plans_creates_twelve_plans():
    call_command("seed_plans")
    assert Plan.objects.count() == 12
    assert set(Plan.objects.values_list("tier", flat=True)) == {1, 2, 3}
    assert Plan.objects.filter(name="Premium - 1 Year").exists()


@pytest.mark.django_db
def test_seed_plans_is_idempotent():
    call_command("seed_plans")
    call_command("seed_plans")
    assert Plan.objects.count() == 12  # no duplicates on a second run
