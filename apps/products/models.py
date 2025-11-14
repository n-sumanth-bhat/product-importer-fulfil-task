from django.db import models


class Product(models.Model):
    """Product model with case-insensitive SKU uniqueness."""
    sku = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products'
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['active']),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"
