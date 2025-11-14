"""
Celery tasks for async CSV import processing.
"""
from celery import shared_task
from apps.uploads.services import (
    parse_csv_file,
    process_csv_chunk,
    update_import_job_status
)

# Import celery app to ensure tasks are registered
try:
    from config.celery_app import app as celery_app
except ImportError:
    # Fallback if import fails
    celery_app = None


@shared_task(name='apps.uploads.tasks.process_csv_import_task')
def process_csv_import_task(job_id, file_content):
    """
    Process CSV import asynchronously.
    
    Args:
        job_id: Import job ID
        file_content: CSV file content as string
    """
    try:
        # Update status to processing
        update_import_job_status(job_id, status='processing', progress=0, processed_records=0)
        
        # Parse CSV
        records = parse_csv_file(file_content)
        
        if not records:
            update_import_job_status(
                job_id,
                status='failed',
                progress=0,
                processed_records=0,
                errors=[{'error': 'CSV file is empty or invalid'}]
            )
            return
        
        # Process records in chunks
        processed_count, error_count, errors = process_csv_chunk(
            job_id=job_id,
            records=records,
            chunk_size=1000
        )
        
        # Mark as completed with final counts
        update_import_job_status(
            job_id,
            status='completed',
            progress=100,
            processed_records=processed_count,
            errors=errors[-100:] if len(errors) > 100 else errors  # Limit to last 100 errors
        )
        
    except Exception as e:
        # Mark as failed
        import traceback
        error_trace = traceback.format_exc()
        update_import_job_status(
            job_id,
            status='failed',
            progress=0,
            errors=[{'error': str(e), 'traceback': error_trace}]
        )
        raise

