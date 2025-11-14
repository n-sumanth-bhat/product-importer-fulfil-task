from django.db import models


class Webhook(models.Model):
    """Webhook configuration model."""
    
    EVENT_TYPE_CHOICES = [
        ('product.created', 'Product Created'),
        ('product.updated', 'Product Updated'),
        ('product.deleted', 'Product Deleted'),
    ]
    
    url = models.URLField(max_length=500)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES, db_index=True)
    enabled = models.BooleanField(default=True, db_index=True)
    headers = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'webhooks'
        indexes = [
            models.Index(fields=['event_type', 'enabled']),
            models.Index(fields=['enabled']),
        ]

    def __str__(self):
        return f"{self.event_type} -> {self.url}"
