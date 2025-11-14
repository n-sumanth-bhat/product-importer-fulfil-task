"""
Celery tasks for async webhook delivery.
"""
import requests
from celery import shared_task
from apps.webhooks.selectors import get_webhook_by_id


@shared_task
def trigger_webhook_task(webhook_id, payload):
    """
    Trigger a webhook asynchronously.
    
    Args:
        webhook_id: Webhook ID
        payload: Data to send to webhook
    """
    webhook = get_webhook_by_id(webhook_id)
    if not webhook or not webhook.enabled:
        return
    
    try:
        response = requests.post(
            webhook.url,
            json=payload,
            headers=webhook.headers or {},
            timeout=30
        )
        # Log response if needed (can be extended)
        return {
            'status_code': response.status_code,
            'success': 200 <= response.status_code < 300
        }
    except Exception as e:
        # Log error if needed (can be extended)
        return {
            'error': str(e),
            'success': False
        }

