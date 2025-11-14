from django.contrib import admin
from apps.products.models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'active', 'created_at', 'updated_at')
    list_filter = ('active', 'created_at')
    search_fields = ('sku', 'name', 'description')
    readonly_fields = ('created_at', 'updated_at')
