import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
# read every CELERY_* setting from Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")
# find tasks.py in every installed app
app.autodiscover_tasks()
