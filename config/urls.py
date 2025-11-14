"""
URL configuration for product importer project.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    # API endpoints
    path('api/products/', include('apps.products.urls')),
    path('api/uploads/', include('apps.uploads.urls')),
    path('api/webhooks/', include('apps.webhooks.urls')),
    # UI views
    path('', TemplateView.as_view(template_name='products/list.html'), name='home'),
    path('products/', TemplateView.as_view(template_name='products/list.html'), name='products'),
    path('upload/', TemplateView.as_view(template_name='uploads/upload.html'), name='upload'),
    path('webhooks/', TemplateView.as_view(template_name='webhooks/manage.html'), name='webhooks'),
]
