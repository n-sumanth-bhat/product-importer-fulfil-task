#!/bin/bash
# Start Celery worker for Linux/Mac

celery -A config.celery_app worker --loglevel=info

