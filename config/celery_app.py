"""
Celery configuration for product importer.
This file is imported in config/__init__.py to ensure Celery is loaded.
"""
import os
import django
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('product_importer')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Initialize Django if not already initialized
# This is needed when Celery worker imports this module
# Must be called AFTER creating the Celery app but BEFORE autodiscover
try:
    django.setup()
except RuntimeError:
    # Django is already set up (e.g., when running as Django server), ignore
    pass

# Load task modules from all registered Django apps.
# autodiscover_tasks will discover tasks after Django is fully initialized
# Specify the packages explicitly to avoid scanning all installed apps
app.autodiscover_tasks(['apps.uploads', 'apps.webhooks'])

@app.task(bind=True, name='celery.debug_task')
def debug_task(self):
    print(f'Request: {self.request!r}')

