"""
URL routing for Product endpoints.
"""
from django.urls import path
from apps.products.api import (
    ProductListCreateAPIView,
    ProductDetailAPIView,
    ProductBulkDeleteAPIView
)

app_name = 'products'

urlpatterns = [
    path('', ProductListCreateAPIView.as_view(), name='list-create'),
    path('<int:product_id>/', ProductDetailAPIView.as_view(), name='detail'),
    path('bulk-delete/', ProductBulkDeleteAPIView.as_view(), name='bulk-delete'),
]

