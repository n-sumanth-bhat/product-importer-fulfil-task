"""
Services for ImportJob write operations and CSV processing.
"""
import csv
import io
from apps.uploads.models import ImportJob
from apps.uploads.selectors import get_import_job_by_id
from apps.products.services import create_product


def create_import_job(file_name):
    """Create a new import job."""
    return ImportJob.objects.create(file_name=file_name)


def update_import_job_status(job_id, status=None, progress=None, processed_records=None, total_records=None, errors=None, celery_task_id=None, update_fields=None):
    """
    Update import job status and progress.
    Uses update_fields to minimize DB overhead for frequent updates.
    """
    job = get_import_job_by_id(job_id)
    if not job:
        return None
    
    # Check if job is cancelled
    if job.status == 'cancelled':
        return job
    
    fields_to_update = []
    
    if status is not None:
        job.status = status
        fields_to_update.append('status')
        if status in ('completed', 'failed', 'cancelled'):
            from django.utils import timezone
            job.completed_at = timezone.now()
            fields_to_update.append('completed_at')
    
    if progress is not None:
        job.progress = progress
        fields_to_update.append('progress')
    
    if processed_records is not None:
        job.processed_records = processed_records
        fields_to_update.append('processed_records')
    
    if total_records is not None:
        job.total_records = total_records
        fields_to_update.append('total_records')
    
    if errors is not None:
        job.errors = errors
        fields_to_update.append('errors')
    
    if celery_task_id is not None:
        job.celery_task_id = celery_task_id
        fields_to_update.append('celery_task_id')
    
    # Always update last_updated_at for staleness detection
    fields_to_update.append('last_updated_at')
    
    # Use update_fields if specified, otherwise use all changed fields
    if update_fields:
        fields_to_update = update_fields
    
    job.save(update_fields=fields_to_update)
    return job


def normalize_csv_record(record):
    """
    Normalize CSV record keys to be case-insensitive.
    Converts all keys to a standard format (title case) for consistent access.
    
    Args:
        record: dict with CSV row data (original case-sensitive keys)
    
    Returns:
        dict: Record with normalized keys
    """
    normalized = {}
    # Map of normalized key -> original key
    key_mapping = {}
    
    for key, value in record.items():
        # Normalize key to title case (e.g., 'sku' -> 'Sku', 'SKU' -> 'Sku', 'Name' -> 'Name')
        normalized_key = key.strip().title()
        normalized[normalized_key] = value
        key_mapping[normalized_key] = key
    
    return normalized


def parse_csv_file(file_content):
    """
    Parse CSV file content and return records with normalized (case-insensitive) headers.
    
    Args:
        file_content: File content (bytes or string)
    
    Returns:
        list: List of dictionaries with CSV data (normalized keys)
    """
    if isinstance(file_content, bytes):
        file_content = file_content.decode('utf-8')
    
    csv_file = io.StringIO(file_content)
    reader = csv.DictReader(csv_file)
    
    # Normalize all records to handle case-insensitive headers
    records = [normalize_csv_record(record) for record in reader]
    
    return records


def validate_csv_record(record):
    """
    Validate a single CSV record.
    Assumes record keys are already normalized to title case (case-insensitive).
    
    Args:
        record: dict with CSV row data (normalized keys like 'Sku', 'Name', 'Description')
    
    Returns:
        tuple: (is_valid, error_message)
    """
    # Keys are normalized to title case, so 'Sku' and 'Name' are the standard keys
    sku = (record.get('Sku') or '').strip()
    name = (record.get('Name') or '').strip()
    
    if not sku:
        return False, "SKU is required"
    if not name:
        return False, "Name is required"
    return True, None


def process_csv_chunk(job_id, records, chunk_size=None):
    """
    Process a chunk of CSV records using optimized bulk operations.
    
    Args:
        job_id: Import job ID
        records: List of CSV record dictionaries
        chunk_size: Number of records to process in each batch (adaptive based on file size)
    
    Returns:
        tuple: (processed_count, error_count, errors)
    """
    from apps.products.models import Product
    from django.db import transaction
    from django.utils import timezone
    import logging
    
    logger = logging.getLogger(__name__)
    
    total_processed = 0
    total_errors = 0
    all_errors = []
    
    job = get_import_job_by_id(job_id)
    if not job:
        return 0, 0, []
    
    # Check if cancelled
    job.refresh_from_db()
    if job.status == 'cancelled':
        logger.info(f"Import job {job_id} was cancelled, stopping processing")
        return total_processed, total_errors, all_errors
    
    # Adaptive chunk sizing based on total records
    if chunk_size is None:
        if job.total_records < 1000:
            chunk_size = 500
        elif job.total_records < 10000:
            chunk_size = 1000
        elif job.total_records < 100000:
            chunk_size = 2000
        else:
            chunk_size = 3000  # Smaller chunks for very large files to ensure progress visibility
    
    # Process records in chunks
    total_chunks = (len(records) + chunk_size - 1) // chunk_size
    
    for chunk_idx, chunk_start in enumerate(range(0, len(records), chunk_size)):
        # Check if cancelled before processing each chunk
        job.refresh_from_db()
        if job.status == 'cancelled':
            logger.info(f"Import job {job_id} was cancelled during processing")
            break
        
        chunk = records[chunk_start:chunk_start + chunk_size]
        
        # Separate valid and invalid records
        valid_products = []
        invalid_records = []
        
        for idx, record in enumerate(chunk):
            row_number = chunk_start + idx + 2  # +2 because CSV has header row (row 1) and 0-indexed
            
            # Validate record
            is_valid, error_msg = validate_csv_record(record)
            if not is_valid:
                total_errors += 1
                sku_value = (record.get('Sku') or '').strip()
                invalid_records.append({
                    'row': row_number,
                    'sku': sku_value,
                    'error': error_msg
                })
                continue
            
            # Get values (keys are normalized to title case)
            sku = (record.get('Sku') or '').strip()
            name = (record.get('Name') or '').strip()
            description = (record.get('Description') or '').strip() or ''
            
            valid_products.append({
                'sku': sku,
                'name': name,
                'description': description,
                'active': True,
                'row_number': row_number
            })
        
        # Process valid products using bulk operations
        if valid_products:
            try:
                with transaction.atomic():
                    # Get all SKUs from this chunk
                    skus = [p['sku'] for p in valid_products]
                    
                    # Efficient lookup: Get all products with matching SKUs (case-insensitive)
                    # Use Q objects with OR for case-insensitive matching
                    # For small chunks, this is efficient. For very large chunks, we batch the query.
                    from django.db.models import Q
                    from functools import reduce
                    import operator
                    
                    # Get unique SKUs (case-insensitive) to minimize query size
                    skus_lower_set = {sku.lower() for sku in skus}
                    
                    # Efficient lookup: Use smaller batches to avoid query complexity
                    # For very large chunks, use smaller batch sizes to prevent Q object overload
                    batch_size = min(200, len(skus))  # Smaller batches for better performance
                    existing_products = {}
                    
                    # Process in batches to avoid creating huge Q objects
                    for i in range(0, len(skus), batch_size):
                        # Check if cancelled before each batch query
                        job.refresh_from_db()
                        if job.status == 'cancelled':
                            break
                        
                        sku_batch = skus[i:i + batch_size]
                        q_objects = [Q(sku__iexact=sku) for sku in sku_batch]
                        
                        if q_objects:
                            try:
                                existing_products_raw = Product.objects.filter(
                                    reduce(operator.or_, q_objects)
                                ).values('id', 'sku', 'name', 'description', 'active')
                                
                                # Build dictionary for fast lookup (case-insensitive)
                                for product in existing_products_raw:
                                    sku_lower = product['sku'].lower()
                                    if sku_lower in skus_lower_set and sku_lower not in existing_products:
                                        existing_products[sku_lower] = product
                            except Exception as query_error:
                                logger.warning(f"Query error for SKU batch, trying individual lookups: {str(query_error)}")
                                # Fallback to individual lookups for this batch
                                for sku in sku_batch:
                                    try:
                                        product = Product.objects.get(sku__iexact=sku)
                                        sku_lower = sku.lower()
                                        if sku_lower not in existing_products:
                                            existing_products[sku_lower] = {
                                                'id': product.id,
                                                'sku': product.sku,
                                                'name': product.name,
                                                'description': product.description,
                                                'active': product.active
                                            }
                                    except Product.DoesNotExist:
                                        pass
                                    except Product.MultipleObjectsReturned:
                                        product = Product.objects.filter(sku__iexact=sku).first()
                                        if product:
                                            sku_lower = sku.lower()
                                            if sku_lower not in existing_products:
                                                existing_products[sku_lower] = {
                                                    'id': product.id,
                                                    'sku': product.sku,
                                                    'name': product.name,
                                                    'description': product.description,
                                                    'active': product.active
                                                }
                    
                    # Separate into updates and creates
                    products_to_update = []
                    products_to_create = []
                    update_ids = []
                    
                    for product_data in valid_products:
                        sku_lower = product_data['sku'].lower()
                        if sku_lower in existing_products:
                            # Update existing
                            existing = existing_products[sku_lower]
                            # Only update if values changed
                            if (existing['name'] != product_data['name'] or 
                                existing['description'] != product_data['description'] or
                                existing['active'] != product_data['active']):
                                update_ids.append(existing['id'])
                                products_to_update.append(Product(
                                    id=existing['id'],
                                    sku=existing['sku'],  # Keep original SKU case
                                    name=product_data['name'],
                                    description=product_data['description'],
                                    active=product_data['active']
                                ))
                        else:
                            # Create new
                            products_to_create.append(Product(
                                sku=product_data['sku'],
                                name=product_data['name'],
                                description=product_data['description'],
                                active=product_data['active']
                            ))
                    
                    # Bulk update (only if there are changes)
                    if products_to_update:
                        Product.objects.bulk_update(
                            products_to_update,
                            ['name', 'description', 'active'],
                            batch_size=1000
                        )
                    
                    # Bulk create
                    if products_to_create:
                        Product.objects.bulk_create(
                            products_to_create,
                            batch_size=1000,
                            ignore_conflicts=False
                        )
                    
                    total_processed += len(valid_products)
                    
            except Exception as e:
                logger.error(f"Error in bulk operation for chunk {chunk_idx}: {str(e)}", exc_info=True)
                # If bulk operation fails, fall back to individual processing for this chunk
                # Process in smaller batches to avoid further issues
                fallback_batch_size = 100
                for i in range(0, len(valid_products), fallback_batch_size):
                    # Check if cancelled before each fallback batch
                    job.refresh_from_db()
                    if job.status == 'cancelled':
                        break
                    
                    fallback_batch = valid_products[i:i + fallback_batch_size]
                    for product_data in fallback_batch:
                        try:
                            from apps.products.services import create_product
                            create_product(
                                sku=product_data['sku'],
                                name=product_data['name'],
                                description=product_data['description'] or None,
                                active=product_data['active']
                            )
                            total_processed += 1
                        except Exception as e2:
                            total_errors += 1
                            invalid_records.append({
                                'row': product_data['row_number'],
                                'sku': product_data['sku'],
                                'error': str(e2)
                            })
        
        # Add invalid records to errors
        all_errors.extend(invalid_records)
        
        # Update progress after EVERY chunk for smooth progress tracking
        # Use update_fields to minimize DB overhead
        # Always update progress, even if there were errors in the chunk
        try:
            progress = int((total_processed / job.total_records) * 100) if job.total_records > 0 else 0
            
            update_import_job_status(
                job_id=job_id,
                status='processing',
                progress=min(progress, 99),
                processed_records=total_processed,
                errors=all_errors[-100:] if len(all_errors) > 100 else all_errors,
                update_fields=['status', 'progress', 'processed_records', 'errors', 'last_updated_at']
            )
            
            # Log progress for debugging
            if chunk_idx % 10 == 0 or chunk_idx == total_chunks - 1:
                logger.info(f"Import job {job_id}: Processed {total_processed}/{job.total_records} records ({progress}%)")
                
        except Exception as e:
            logger.error(f"Error updating progress for job {job_id}: {str(e)}", exc_info=True)
            # Continue processing even if progress update fails
    
    return total_processed, total_errors, all_errors

