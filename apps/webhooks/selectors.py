"""
Selectors for Webhook read operations.
"""
from apps.webhooks.models import Webhook


def get_webhook_by_id(webhook_id):
    """Get a webhook by ID."""
    try:
        return Webhook.objects.get(id=webhook_id)
    except Webhook.DoesNotExist:
        return None


def list_webhooks(filters=None):
    """
    List webhooks with optional filtering.
    
    Args:
        filters: dict with keys: event_type, enabled
    
    Returns:
        queryset
    """
    queryset = Webhook.objects.all()
    
    if filters:
        if filters.get('event_type'):
            queryset = queryset.filter(event_type=filters['event_type'])
        if filters.get('enabled') is not None:
            queryset = queryset.filter(enabled=filters['enabled'])
    
    return queryset


def get_enabled_webhooks_for_event(event_type):
    """Get all enabled webhooks for a specific event type."""
    return Webhook.objects.filter(event_type=event_type, enabled=True)

