from django.core.management.base import BaseCommand

from subscriptions.services import process_due_subscriptions


class Command(BaseCommand):
    help = "Run the renew/expire job once, synchronously (manual trigger; Celery beat runs it hourly)."

    def handle(self, *args, **options):
        stats = process_due_subscriptions()
        self.stdout.write(self.style.SUCCESS(f"Done: {stats}"))
