from django.contrib import admin
from apps.uploads.models import ImportJob


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'status', 'progress', 'total_records', 'processed_records', 'last_updated_at', 'created_at')
    list_filter = ('status', 'created_at')
    readonly_fields = ('created_at', 'completed_at', 'last_updated_at', 'progress', 'total_records', 'processed_records', 'errors', 'celery_task_id')
    search_fields = ('file_name', 'celery_task_id')
