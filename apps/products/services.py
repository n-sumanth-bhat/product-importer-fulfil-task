"""
Services for Product write operations.
All database write operations should be placed here.
Services can call selectors for read operations.
"""
from apps.products.models import Product
from apps.products.selectors import get_product_by_sku, get_product_by_id


def create_product(sku, name, description=None, active=True):
    """
    Create a new product.
    
    Args:
        sku: Product SKU (case-insensitive unique)
        name: Product name
        description: Optional description
        active: Active status (default: True)
    
    Returns:
        tuple: (product, created) - created is True if new, False if updated
    """
    # Check if product exists (case-insensitive)
    existing = get_product_by_sku(sku)
    
    if existing:
        # Update existing product
        existing.name = name
        if description is not None:
            existing.description = description
        existing.active = active
        existing.save()
        
        # Trigger webhook for update
        from apps.webhooks.services import trigger_webhooks_for_event
        from apps.products.serializers import ProductSerializer
        trigger_webhooks_for_event('product.updated', ProductSerializer(existing).data)
        
        return existing, False
    
    # Create new product
    product = Product.objects.create(
        sku=sku,
        name=name,
        description=description or '',
        active=active
    )
    
    # Trigger webhook for create
    from apps.webhooks.services import trigger_webhooks_for_event
    from apps.products.serializers import ProductSerializer
    trigger_webhooks_for_event('product.created', ProductSerializer(product).data)
    
    return product, True


def update_product(product_id, **kwargs):
    """
    Update an existing product.
    
    Args:
        product_id: ID of product to update
        **kwargs: Fields to update (sku, name, description, active)
    
    Returns:
        Product instance or None if not found
    """
    product = get_product_by_id(product_id)
    if not product:
        return None
    
    # Handle SKU update (check for conflicts)
    if 'sku' in kwargs:
        new_sku = kwargs['sku']
        existing = get_product_by_sku(new_sku)
        if existing and existing.id != product_id:
            raise ValueError(f"Product with SKU '{new_sku}' already exists")
        product.sku = new_sku
    
    if 'name' in kwargs:
        product.name = kwargs['name']
    if 'description' in kwargs:
        product.description = kwargs['description']
    if 'active' in kwargs:
        product.active = kwargs['active']
    
    product.save()
    
    # Trigger webhook for update
    from apps.webhooks.services import trigger_webhooks_for_event
    from apps.products.serializers import ProductSerializer
    trigger_webhooks_for_event('product.updated', ProductSerializer(product).data)
    
    return product


def delete_product(product_id):
    """
    Delete a product by ID.
    
    Returns:
        bool: True if deleted, False if not found
    """
    product = get_product_by_id(product_id)
    if not product:
        return False
    
    # Store product data for webhook before deletion
    from apps.products.serializers import ProductSerializer
    product_data = ProductSerializer(product).data
    
    product.delete()
    
    # Trigger webhook for delete
    from apps.webhooks.services import trigger_webhooks_for_event
    trigger_webhooks_for_event('product.deleted', product_data)
    
    return True


def bulk_delete_products():
    """
    Delete all products.
    
    Returns:
        int: Number of products deleted
    """
    from apps.products.selectors import get_all_products
    from apps.products.serializers import ProductSerializer
    from apps.webhooks.services import trigger_webhooks_for_event
    
    products = get_all_products()
    
    # Trigger webhooks for each product deletion
    for product in products:
        product_data = ProductSerializer(product).data
        trigger_webhooks_for_event('product.deleted', product_data)
    
    count = products.count()
    products.delete()
    return count

