"""
Serializers for Product model.
"""
from rest_framework import serializers
from apps.products.models import Product


class ProductSerializer(serializers.ModelSerializer):
    """Serializer for Product model."""
    
    class Meta:
        model = Product
        fields = ['id', 'sku', 'name', 'description', 'active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating products."""
    
    class Meta:
        model = Product
        fields = ['sku', 'name', 'description', 'active']

