@echo off
REM Start Celery worker for Windows
REM Use --pool=solo to avoid billiard pool issues on Windows

celery -A config.celery_app worker --pool=solo --loglevel=info

