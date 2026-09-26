from celery import shared_task

from .services import process_due_subscriptions


@shared_task(name="subscriptions.process_due_subscriptions")
def process_due_subscriptions_task() -> dict:
    """Periodic job (Celery beat): renew or expire subscriptions whose period ended."""
    return process_due_subscriptions()
