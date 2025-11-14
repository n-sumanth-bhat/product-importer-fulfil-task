"""
Serializers for ImportJob model.
"""
from rest_framework import serializers
from apps.uploads.models import ImportJob


class ImportJobSerializer(serializers.ModelSerializer):
    """Serializer for ImportJob model."""
    
    class Meta:
        model = ImportJob
        fields = [
            'id', 'file_name', 'status', 'progress', 'total_records',
            'processed_records', 'errors', 'celery_task_id', 'last_updated_at',
            'created_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'status', 'progress', 'total_records', 'processed_records',
            'errors', 'celery_task_id', 'last_updated_at', 'created_at', 'completed_at'
        ]

