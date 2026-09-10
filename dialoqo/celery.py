import os
from celery import Celery

# Define your celery config here.

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dialoqo.settings")
app = Celery("dialoqo")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()