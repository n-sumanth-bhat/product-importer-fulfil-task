"""
Serializers for Webhook model.
"""
from rest_framework import serializers
from apps.webhooks.models import Webhook


class WebhookSerializer(serializers.ModelSerializer):
    """Serializer for Webhook model."""
    
    class Meta:
        model = Webhook
        fields = [
            'id', 'url', 'event_type', 'enabled', 'headers',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class WebhookCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating webhooks."""
    
    class Meta:
        model = Webhook
        fields = ['url', 'event_type', 'enabled', 'headers']

