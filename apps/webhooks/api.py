"""
API views for Webhook management.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.webhooks.serializers import WebhookSerializer, WebhookCreateUpdateSerializer
from apps.webhooks.selectors import list_webhooks, get_webhook_by_id
from apps.webhooks.services import (
    create_webhook,
    update_webhook,
    delete_webhook,
    test_webhook
)


class WebhookListCreateAPIView(APIView):
    """List webhooks or create a new webhook."""
    
    def get(self, request):
        """List webhooks with optional filtering."""
        filters = {
            'event_type': request.query_params.get('event_type'),
            'enabled': request.query_params.get('enabled'),
        }
        
        # Remove None values and convert enabled to boolean
        filters = {k: v for k, v in filters.items() if v is not None}
        if 'enabled' in filters:
            filters['enabled'] = filters['enabled'].lower() in ('true', '1', 'yes')
        
        queryset = list_webhooks(filters=filters)
        serializer = WebhookSerializer(queryset, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Create a new webhook."""
        serializer = WebhookCreateUpdateSerializer(data=request.data)
        if serializer.is_valid():
            webhook = create_webhook(
                url=serializer.validated_data['url'],
                event_type=serializer.validated_data['event_type'],
                enabled=serializer.validated_data.get('enabled', True),
                headers=serializer.validated_data.get('headers', {})
            )
            response_serializer = WebhookSerializer(webhook)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WebhookDetailAPIView(APIView):
    """Retrieve, update or delete a webhook."""
    
    def get(self, request, webhook_id):
        """Retrieve a webhook by ID."""
        webhook = get_webhook_by_id(webhook_id)
        if not webhook:
            return Response({'error': 'Webhook not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = WebhookSerializer(webhook)
        return Response(serializer.data)
    
    def put(self, request, webhook_id):
        """Update a webhook."""
        serializer = WebhookCreateUpdateSerializer(data=request.data)
        if serializer.is_valid():
            webhook = update_webhook(webhook_id, **serializer.validated_data)
            if not webhook:
                return Response({'error': 'Webhook not found'}, status=status.HTTP_404_NOT_FOUND)
            response_serializer = WebhookSerializer(webhook)
            return Response(response_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, webhook_id):
        """Partially update a webhook."""
        serializer = WebhookCreateUpdateSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            webhook = update_webhook(webhook_id, **serializer.validated_data)
            if not webhook:
                return Response({'error': 'Webhook not found'}, status=status.HTTP_404_NOT_FOUND)
            response_serializer = WebhookSerializer(webhook)
            return Response(response_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, webhook_id):
        """Delete a webhook."""
        success = delete_webhook(webhook_id)
        if not success:
            return Response({'error': 'Webhook not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class WebhookTestAPIView(APIView):
    """Test a webhook."""
    
    def post(self, request, webhook_id):
        """Test a webhook by sending a test request."""
        payload = request.data.get('payload')
        result = test_webhook(webhook_id, payload)
        
        if result is None:
            return Response({'error': 'Webhook not found'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(result)

