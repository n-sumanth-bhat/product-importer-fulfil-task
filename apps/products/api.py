"""
API views for Product endpoints.
These views handle request/response only and delegate to services/selectors.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.products.serializers import ProductSerializer, ProductCreateUpdateSerializer
from apps.products.selectors import list_products, get_product_by_id
from apps.products.services import create_product, update_product, delete_product, bulk_delete_products


class ProductListCreateAPIView(APIView):
    """List products or create a new product."""
    
    def get(self, request):
        """List products with filtering and pagination."""
        # Extract filters from query params
        filters = {
            'sku': request.query_params.get('sku'),
            'name': request.query_params.get('name'),
            'description': request.query_params.get('description'),
            'active': request.query_params.get('active'),
        }
        
        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}
        
        # Convert active to boolean if provided
        if 'active' in filters:
            filters['active'] = filters['active'].lower() in ('true', '1', 'yes')
        
        # Pagination
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 20)
        
        try:
            page = int(page)
            page_size = int(page_size)
        except (ValueError, TypeError):
            page = 1
            page_size = 20
        
        queryset, total_count = list_products(filters=filters, page=page, page_size=page_size)
        serializer = ProductSerializer(queryset, many=True)
        
        return Response({
            'results': serializer.data,
            'count': total_count,
            'page': page,
            'page_size': page_size
        })
    
    def post(self, request):
        """Create a new product."""
        serializer = ProductCreateUpdateSerializer(data=request.data)
        if serializer.is_valid():
            product, created = create_product(
                sku=serializer.validated_data['sku'],
                name=serializer.validated_data['name'],
                description=serializer.validated_data.get('description'),
                active=serializer.validated_data.get('active', True)
            )
            response_serializer = ProductSerializer(product)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductDetailAPIView(APIView):
    """Retrieve, update or delete a product."""
    
    def get(self, request, product_id):
        """Retrieve a product by ID."""
        product = get_product_by_id(product_id)
        if not product:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ProductSerializer(product)
        return Response(serializer.data)
    
    def put(self, request, product_id):
        """Update a product."""
        serializer = ProductCreateUpdateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                product = update_product(product_id, **serializer.validated_data)
                if not product:
                    return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
                response_serializer = ProductSerializer(product)
                return Response(response_serializer.data)
            except ValueError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, product_id):
        """Partially update a product."""
        serializer = ProductCreateUpdateSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            try:
                product = update_product(product_id, **serializer.validated_data)
                if not product:
                    return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
                response_serializer = ProductSerializer(product)
                return Response(response_serializer.data)
            except ValueError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, product_id):
        """Delete a product."""
        success = delete_product(product_id)
        if not success:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductBulkDeleteAPIView(APIView):
    """Delete all products."""
    
    def delete(self, request):
        """Delete all products."""
        count = bulk_delete_products()
        return Response({'message': f'Deleted {count} products'}, status=status.HTTP_200_OK)

