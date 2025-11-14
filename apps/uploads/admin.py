from django.contrib import admin
from apps.uploads.models import ImportJob


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'status', 'progress', 'total_records', 'processed_records', 'created_at')
    list_filter = ('status', 'created_at')
    readonly_fields = ('created_at', 'completed_at', 'progress', 'total_records', 'processed_records', 'errors')
