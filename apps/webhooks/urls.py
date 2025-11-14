"""
URL routing for webhook endpoints.
"""
from django.urls import path
from apps.webhooks.api import (
    WebhookListCreateAPIView,
    WebhookDetailAPIView,
    WebhookTestAPIView
)

app_name = 'webhooks'

urlpatterns = [
    path('', WebhookListCreateAPIView.as_view(), name='list-create'),
    path('<int:webhook_id>/', WebhookDetailAPIView.as_view(), name='detail'),
    path('<int:webhook_id>/test/', WebhookTestAPIView.as_view(), name='test'),
]

