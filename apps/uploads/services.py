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


def update_import_job_status(job_id, status=None, phase=None, progress=None, processed_records=None, total_records=None, errors=None, celery_task_id=None, s3_key=None, file_size=None, update_fields=None):
    """
    Update import job status and progress.
    Uses update_fields to minimize DB overhead for frequent updates.
    
    Progress calculation based on phase:
    - uploading: 0-10%
    - parsing: 10-20%
    - processing: 20-100% (based on processed_records/total_records)
    - completed: 100%
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
    
    if phase is not None:
        job.phase = phase
        fields_to_update.append('phase')
    
    # Calculate progress based on phase if not explicitly provided
    if progress is None and phase is not None:
        if phase == 'uploading':
            progress = 5  # Mid-point of uploading phase
        elif phase == 'parsing':
            progress = 15  # Mid-point of parsing phase
        elif phase == 'processing' and processed_records is not None and total_records:
            # Calculate progress within processing phase (20-100%)
            processing_progress = (processed_records / total_records) * 80  # 80% of total (20-100%)
            progress = int(20 + processing_progress)
            progress = min(progress, 99)  # Cap at 99% until completed
        elif phase == 'completed':
            progress = 100
    
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
    
    if s3_key is not None:
        job.s3_key = s3_key
        fields_to_update.append('s3_key')
    
    if file_size is not None:
        job.file_size = file_size
        fields_to_update.append('file_size')
    
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


def preload_existing_skus():
    """
    Preload all existing SKUs into a dictionary for O(1) case-insensitive lookup.
    This eliminates N+1 queries during CSV processing.
    
    Returns:
        dict: Dictionary mapping lowercase SKU to product data
        Format: {sku_lower: {'id': id, 'sku': sku, 'name': name, 'description': description, 'active': active}}
    """
    from apps.products.models import Product
    import logging
    
    logger = logging.getLogger(__name__)
    
    logger.info("Preloading existing SKUs into memory...")
    products = Product.objects.all().values('id', 'sku', 'name', 'description', 'active')
    
    sku_dict = {}
    for product in products:
        sku_lower = product['sku'].lower()
        # If duplicate SKUs exist (shouldn't happen due to constraint, but handle gracefully)
        if sku_lower not in sku_dict:
            sku_dict[sku_lower] = product
    
    logger.info(f"Preloaded {len(sku_dict)} existing SKUs")
    return sku_dict


def validate_csv_headers(reader):
    """
    Validate that CSV has required headers (SKU, Name, Description).
    Headers are case-insensitive.
    
    Args:
        reader: csv.DictReader instance
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not reader.fieldnames:
        return False, "CSV file is empty or has no headers"
    
    # Normalize headers to title case for comparison
    normalized_headers = set()
    for header in reader.fieldnames:
        # Normalize each header to title case
        normalized_header = header.strip().title()
        normalized_headers.add(normalized_header)
    
    # Check for required fields (case-insensitive)
    required_fields = {'Sku', 'Name', 'Description'}
    missing_fields = required_fields - normalized_headers
    
    if missing_fields:
        return False, f"CSV file is missing required columns: {', '.join(missing_fields)}. Found columns: {', '.join(reader.fieldnames)}"
    
    return True, None


def count_csv_records(s3_key):
    """
    Count total records in CSV file from S3 (quick pass, no processing).
    Also validates CSV headers.
    
    Args:
        s3_key: S3 object key
    
    Returns:
        int: Total number of records (excluding header)
    
    Raises:
        ValueError: If CSV headers are invalid
    """
    from apps.uploads.s3_service import get_s3_file_stream
    import csv
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get streaming file object from S3
        s3_file = get_s3_file_stream(s3_key)
        
        # Use csv.DictReader for efficient row-by-row parsing
        reader = csv.DictReader(s3_file)
        
        # Validate headers
        is_valid, error_msg = validate_csv_headers(reader)
        if not is_valid:
            logger.error(f"Invalid CSV headers: {error_msg}")
            raise ValueError(error_msg)
        
        count = 0
        for _ in reader:
            count += 1
        
        logger.info(f"Counted {count} records in CSV file")
        return count
            
    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        logger.error(f"Error counting CSV records from S3: {str(e)}", exc_info=True)
        raise


def stream_csv_from_s3(s3_key):
    """
    Stream CSV file from S3 using smart_open generator.
    Yields normalized CSV records one at a time.
    Headers are validated before streaming.
    
    Args:
        s3_key: S3 object key
    
    Yields:
        tuple: (normalized_record, row_number)
    
    Raises:
        ValueError: If CSV headers are invalid
    """
    from apps.uploads.s3_service import get_s3_file_stream
    import csv
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get streaming file object from S3
        s3_file = get_s3_file_stream(s3_key)
        
        # Use csv.DictReader for efficient row-by-row parsing
        reader = csv.DictReader(s3_file)
        
        # Validate headers (headers are already validated in count_csv_records, but validate again for safety)
        is_valid, error_msg = validate_csv_headers(reader)
        if not is_valid:
            logger.error(f"Invalid CSV headers: {error_msg}")
            raise ValueError(error_msg)
        
        row_number = 1  # Start at 1 (header is row 0)
        for record in reader:
            row_number += 1
            # Normalize record keys to title case for case-insensitive handling
            normalized_record = normalize_csv_record(record)
            yield normalized_record, row_number
            
    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        logger.error(f"Error streaming CSV from S3: {str(e)}", exc_info=True)
        raise


def process_csv_stream(job_id, csv_generator, existing_skus_dict, total_records, micro_batch_size=500):
    """
    Process CSV stream in micro-batches using optimized bulk operations.
    Uses preloaded SKU dictionary for O(1) lookups.
    
    Args:
        job_id: Import job ID
        csv_generator: Generator yielding (normalized_record, row_number) tuples
        existing_skus_dict: Preloaded dictionary of existing SKUs (lowercase keys)
        total_records: Total number of records to process (already counted)
        micro_batch_size: Number of records to process in each micro-batch (default: 500)
    
    Returns:
        tuple: (processed_count, error_count, errors)
    """
    from apps.products.models import Product
    from django.db import transaction
    import logging
    
    logger = logging.getLogger(__name__)
    
    total_processed = 0
    total_errors = 0
    all_errors = []
    
    job = get_import_job_by_id(job_id)
    if not job:
        return 0, 0, []
    
    # Micro-batch accumulator
    micro_batch = []
    batch_count = 0
    
    try:
        records_seen = 0
        for record, row_number in csv_generator:
            records_seen += 1
            
            # Check for cancellation periodically
            if records_seen % 1000 == 0:
                job.refresh_from_db()
                if job.status == 'cancelled':
                    logger.info(f"Import job {job_id} was cancelled during processing")
                    break
            
            # Validate record
            is_valid, error_msg = validate_csv_record(record)
            if not is_valid:
                total_errors += 1
                sku_value = (record.get('Sku') or '').strip()
                all_errors.append({
                    'row': row_number,
                    'sku': sku_value,
                    'error': error_msg
                })
                continue
            
            # Get values (keys are normalized to title case)
            sku = (record.get('Sku') or '').strip()
            name = (record.get('Name') or '').strip()
            description = (record.get('Description') or '').strip() or ''
            
            micro_batch.append({
                'sku': sku,
                'name': name,
                'description': description,
                'active': True,
                'row_number': row_number
            })
            
            # Process micro-batch when it reaches the size limit
            if len(micro_batch) >= micro_batch_size:
                processed, errors = _process_micro_batch(job_id, micro_batch, existing_skus_dict)
                total_processed += processed
                total_errors += len(errors)
                all_errors.extend(errors)
                micro_batch = []
                batch_count += 1
                
                # Update progress after each micro-batch
                try:
                    # Calculate progress: processing phase is 20-100%
                    # So progress = 20 + (processed/total * 80)
                    progress = int((total_processed / total_records) * 80) + 20 if total_records > 0 else 20
                    progress = min(progress, 99)  # Cap at 99% until completed
                    update_import_job_status(
                        job_id=job_id,
                        phase='processing',
                        status='processing',
                        progress=progress,
                        processed_records=total_processed,
                        # Don't update total_records - it's already set and should remain fixed
                        errors=all_errors[-100:] if len(all_errors) > 100 else all_errors,
                        update_fields=['phase', 'status', 'progress', 'processed_records', 'errors', 'last_updated_at']
                    )
                except Exception as e:
                    logger.error(f"Error updating progress for job {job_id}: {str(e)}", exc_info=True)
                
                # Log progress periodically
                if batch_count % 10 == 0:
                    logger.info(f"Import job {job_id}: Processed {total_processed}/{total_records} records ({progress}%)")
        
        # Process remaining records in micro_batch
        if micro_batch:
            processed, errors = _process_micro_batch(job_id, micro_batch, existing_skus_dict)
            total_processed += processed
            total_errors += len(errors)
            all_errors.extend(errors)
            
    except Exception as e:
        logger.error(f"Error processing CSV stream for job {job_id}: {str(e)}", exc_info=True)
        raise
    
    return total_processed, total_errors, all_errors


def _process_micro_batch(job_id, micro_batch, existing_skus_dict):
    """
    Process a micro-batch of products using bulk operations.
    Helper function for process_csv_stream.
    
    Args:
        job_id: Import job ID
        micro_batch: List of product data dictionaries
        existing_skus_dict: Preloaded dictionary of existing SKUs
    
    Returns:
        tuple: (processed_count, errors)
    """
    from apps.products.models import Product
    from django.db import transaction
    import logging
    
    logger = logging.getLogger(__name__)
    
    processed = 0
    errors = []
    
    try:
        with transaction.atomic():
            products_to_update = []
            products_to_create = []
            skus_in_create_batch = set()  # Track SKUs already added to create list in this batch
            
            for product_data in micro_batch:
                sku_lower = product_data['sku'].lower()
                
                if sku_lower in existing_skus_dict:
                    # Update existing product (only if it has an ID - was created in DB before)
                    existing = existing_skus_dict[sku_lower]
                    # Only update if product has an ID (exists in DB) and values changed
                    if existing.get('id') is not None:
                        if (existing['name'] != product_data['name'] or 
                            existing['description'] != product_data['description'] or
                            existing['active'] != product_data['active']):
                            products_to_update.append(Product(
                                id=existing['id'],
                                sku=existing['sku'],  # Keep original SKU case
                                name=product_data['name'],
                                description=product_data['description'],
                                active=product_data['active']
                            ))
                            # Update the dict to reflect changes
                            existing_skus_dict[sku_lower] = {
                                'id': existing['id'],
                                'sku': existing['sku'],
                                'name': product_data['name'],
                                'description': product_data['description'],
                                'active': product_data['active']
                            }
                    # If id is None, it means it was added to dict but not yet created
                    # (or created but ID wasn't set in dict)
                    else:
                        # This SKU was added to dict but not yet created - create it now
                        # But only if we haven't already added it to create list in this batch
                        if sku_lower not in skus_in_create_batch:
                            products_to_create.append(Product(
                                sku=product_data['sku'],
                                name=product_data['name'],
                                description=product_data['description'],
                                active=product_data['active']
                            ))
                            skus_in_create_batch.add(sku_lower)
                else:
                    # Create new product (only if not already in create list)
                    if sku_lower not in skus_in_create_batch:
                        products_to_create.append(Product(
                            sku=product_data['sku'],
                            name=product_data['name'],
                            description=product_data['description'],
                            active=product_data['active']
                        ))
                        skus_in_create_batch.add(sku_lower)
                        # Add to dict for future lookups in same job (will be updated with ID after bulk_create)
                        existing_skus_dict[sku_lower] = {
                            'id': None,  # Will be set after bulk_create
                            'sku': product_data['sku'],
                            'name': product_data['name'],
                            'description': product_data['description'],
                            'active': product_data['active']
                        }
            
            # Bulk update
            if products_to_update:
                Product.objects.bulk_update(
                    products_to_update,
                    ['name', 'description', 'active'],
                    batch_size=500
                )
            
            # Bulk create
            if products_to_create:
                created_products = Product.objects.bulk_create(
                    products_to_create,
                    batch_size=500,
                    ignore_conflicts=False
                )
                # Update dict with created IDs
                # Note: bulk_create may or may not return objects with IDs depending on DB backend
                # For PostgreSQL, IDs are typically returned
                for created in created_products:
                    if hasattr(created, 'id') and created.id:
                        sku_lower = created.sku.lower()
                        if sku_lower in existing_skus_dict:
                            existing_skus_dict[sku_lower]['id'] = created.id
                
                # If IDs weren't returned, fetch them from DB
                if products_to_create and (not created_products or not hasattr(created_products[0], 'id') or not created_products[0].id):
                    # Fetch the created products by SKU to get their IDs
                    created_skus = [p.sku for p in products_to_create]
                    created_skus_lower = {sku.lower() for sku in created_skus}
                    
                    # Query for the products we just created
                    from django.db.models import Q
                    from functools import reduce
                    import operator
                    
                    q_objects = [Q(sku__iexact=sku) for sku in created_skus[:200]]  # Batch queries
                    if q_objects:
                        fetched_products = Product.objects.filter(
                            reduce(operator.or_, q_objects)
                        ).values('id', 'sku')
                        
                        for product in fetched_products:
                            sku_lower = product['sku'].lower()
                            if sku_lower in created_skus_lower and sku_lower in existing_skus_dict:
                                existing_skus_dict[sku_lower]['id'] = product['id']
            
            processed = len(micro_batch)
            
    except Exception as e:
        logger.error(f"Error in micro-batch processing: {str(e)}", exc_info=True)
        # Fallback: try individual creates
        for product_data in micro_batch:
            try:
                from apps.products.services import create_product
                create_product(
                    sku=product_data['sku'],
                    name=product_data['name'],
                    description=product_data['description'] or None,
                    active=product_data['active']
                )
                processed += 1
            except Exception as e2:
                errors.append({
                    'row': product_data['row_number'],
                    'sku': product_data['sku'],
                    'error': str(e2)
                })
    
    return processed, errors


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

