"""
Selectors for Product read operations.
All database read queries should be placed here.
"""
from django.db.models import Q
from apps.products.models import Product


def get_product_by_id(product_id):
    """Get a single product by ID."""
    try:
        return Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return None


def get_product_by_sku(sku):
    """Get a product by SKU (case-insensitive)."""
    try:
        return Product.objects.get(sku__iexact=sku)
    except Product.DoesNotExist:
        return None


def list_products(filters=None, page=None, page_size=None):
    """
    List products with optional filtering and pagination.
    
    Args:
        filters: dict with keys: sku, name, active, description
        page: page number (1-indexed)
        page_size: number of items per page
    
    Returns:
        tuple: (queryset, total_count)
    """
    queryset = Product.objects.all()
    
    if filters:
        if filters.get('sku'):
            queryset = queryset.filter(sku__icontains=filters['sku'])
        if filters.get('name'):
            queryset = queryset.filter(name__icontains=filters['name'])
        if filters.get('description'):
            queryset = queryset.filter(description__icontains=filters['description'])
        if filters.get('active') is not None:
            queryset = queryset.filter(active=filters['active'])
    
    total_count = queryset.count()
    
    if page and page_size:
        start = (page - 1) * page_size
        end = start + page_size
        queryset = queryset[start:end]
    
    return queryset, total_count


def get_all_products():
    """Get all products (for bulk operations)."""
    return Product.objects.all()

