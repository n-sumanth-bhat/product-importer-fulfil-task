"""
Services for Webhook write operations and triggering.
"""
import requests
from django.utils import timezone
from apps.webhooks.models import Webhook
from apps.webhooks.selectors import get_webhook_by_id, get_enabled_webhooks_for_event
from apps.webhooks.tasks import trigger_webhook_task


def create_webhook(url, event_type, enabled=True, headers=None):
    """Create a new webhook."""
    return Webhook.objects.create(
        url=url,
        event_type=event_type,
        enabled=enabled,
        headers=headers or {}
    )


def update_webhook(webhook_id, **kwargs):
    """Update an existing webhook."""
    webhook = get_webhook_by_id(webhook_id)
    if not webhook:
        return None
    
    if 'url' in kwargs:
        webhook.url = kwargs['url']
    if 'event_type' in kwargs:
        webhook.event_type = kwargs['event_type']
    if 'enabled' in kwargs:
        webhook.enabled = kwargs['enabled']
    if 'headers' in kwargs:
        webhook.headers = kwargs['headers']
    
    webhook.save()
    return webhook


def delete_webhook(webhook_id):
    """Delete a webhook."""
    webhook = get_webhook_by_id(webhook_id)
    if not webhook:
        return False
    
    webhook.delete()
    return True


def trigger_webhooks_for_event(event_type, payload):
    """
    Trigger all enabled webhooks for an event type.
    
    Args:
        event_type: Event type (e.g., 'product.created')
        payload: Data to send to webhooks
    """
    webhooks = get_enabled_webhooks_for_event(event_type)
    
    for webhook in webhooks:
        # Trigger async webhook delivery
        trigger_webhook_task.delay(webhook.id, payload)


def test_webhook(webhook_id, payload=None):
    """
    Test a webhook by sending a test request.
    
    Args:
        webhook_id: Webhook ID to test
        payload: Optional test payload
    
    Returns:
        dict: Response information (status_code, response_time, success, error)
    """
    webhook = get_webhook_by_id(webhook_id)
    if not webhook:
        return None
    
    test_payload = payload or {
        'event': 'test',
        'timestamp': timezone.now().isoformat(),
        'message': 'This is a test webhook'
    }
    
    try:
        start_time = timezone.now()
        response = requests.post(
            webhook.url,
            json=test_payload,
            headers=webhook.headers or {},
            timeout=10
        )
        end_time = timezone.now()
        
        response_time = (end_time - start_time).total_seconds()
        
        return {
            'status_code': response.status_code,
            'response_time': response_time,
            'success': 200 <= response.status_code < 300,
            'response_body': response.text[:500]  # Limit response body
        }
    except Exception as e:
        return {
            'status_code': None,
            'response_time': None,
            'success': False,
            'error': str(e)
        }

