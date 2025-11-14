from django.db import models


class ImportJob(models.Model):
    """Model to track CSV import job status and progress."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PHASE_CHOICES = [
        ('uploading', 'Uploading'),
        ('parsing', 'Parsing'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
    ]
    
    file_name = models.CharField(max_length=255)
    s3_key = models.CharField(max_length=500, null=True, blank=True)  # S3 object key
    file_size = models.BigIntegerField(default=0)  # File size in bytes
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES, default='uploading', db_index=True)
    progress = models.IntegerField(default=0)  # 0-100
    total_records = models.IntegerField(default=0)
    processed_records = models.IntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    celery_task_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    last_updated_at = models.DateTimeField(auto_now=True)  # Track last update for staleness detection
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'import_jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.file_name} - {self.status}"
