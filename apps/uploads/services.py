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


def update_import_job_status(job_id, status, progress=None, processed_records=None, total_records=None, errors=None):
    """Update import job status and progress."""
    job = get_import_job_by_id(job_id)
    if not job:
        return None
    
    job.status = status
    if progress is not None:
        job.progress = progress
    if processed_records is not None:
        job.processed_records = processed_records
    if total_records is not None:
        job.total_records = total_records
    if errors is not None:
        job.errors = errors
    if status in ('completed', 'failed'):
        from django.utils import timezone
        job.completed_at = timezone.now()
    
    job.save()
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


def process_csv_chunk(job_id, records, chunk_size=1000):
    """
    Process a chunk of CSV records.
    
    Args:
        job_id: Import job ID
        records: List of CSV record dictionaries
        chunk_size: Number of records to process in each batch
    
    Returns:
        tuple: (processed_count, error_count, errors)
    """
    total_processed = 0
    total_errors = 0
    all_errors = []
    
    job = get_import_job_by_id(job_id)
    if not job:
        return 0, 0, []
    
    # Process records in chunks
    for chunk_start in range(0, len(records), chunk_size):
        chunk = records[chunk_start:chunk_start + chunk_size]
        chunk_processed = 0
        chunk_errors = 0
        
        for idx, record in enumerate(chunk):
            row_number = chunk_start + idx + 2  # +2 because CSV has header row (row 1) and 0-indexed
            
            # Validate record
            is_valid, error_msg = validate_csv_record(record)
            if not is_valid:
                total_errors += 1
                chunk_errors += 1
                # Get SKU for error reporting (keys are normalized to title case)
                sku_value = (record.get('Sku') or '').strip()
                all_errors.append({
                    'row': row_number,
                    'sku': sku_value,
                    'error': error_msg
                })
                continue
            
            try:
                # Get values (keys are normalized to title case: 'Sku', 'Name', 'Description')
                sku = (record.get('Sku') or '').strip()
                name = (record.get('Name') or '').strip()
                description = (record.get('Description') or '').strip() or None
                
                # Create or update product (case-insensitive SKU handling)
                create_product(
                    sku=sku,
                    name=name,
                    description=description,
                    active=True  # Default to active
                )
                total_processed += 1
                chunk_processed += 1
            except Exception as e:
                total_errors += 1
                chunk_errors += 1
                # Get SKU for error reporting (keys are normalized to title case)
                sku_value = (record.get('Sku') or '').strip()
                all_errors.append({
                    'row': row_number,
                    'sku': sku_value,
                    'error': str(e)
                })
        
        # Update progress after each chunk
        # Refresh job to ensure we have latest data
        job.refresh_from_db()
        
        # Calculate progress based on total records processed so far
        progress = int((total_processed / job.total_records) * 100) if job.total_records > 0 else 0
        
        # Update progress (keep at 99% max until fully complete)
        update_import_job_status(
            job_id=job_id,
            status='processing',
            progress=min(progress, 99),
            processed_records=total_processed,
            errors=all_errors[-100:] if len(all_errors) > 100 else all_errors  # Keep last 100 errors
        )
    
    return total_processed, total_errors, all_errors

