import os
from celery import Celery

# Define your celery config here.

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "centralchat.settings")
app = Celery("centralchat")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()