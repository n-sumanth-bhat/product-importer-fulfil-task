from django.contrib import admin
from apps.webhooks.models import Webhook


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ('url', 'event_type', 'enabled', 'created_at', 'updated_at')
    list_filter = ('event_type', 'enabled', 'created_at')
    search_fields = ('url',)
    readonly_fields = ('created_at', 'updated_at')
