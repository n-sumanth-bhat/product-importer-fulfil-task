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


@shared_task(name='apps.uploads.tasks.process_csv_import_task', bind=True)
def process_csv_import_task(self, job_id, file_content):
    """
    Process CSV import asynchronously.
    
    Args:
        self: Task instance (for cancellation support)
        job_id: Import job ID
        file_content: CSV file content as string
    """
    import logging
    from django.utils import timezone
    from datetime import timedelta
    
    logger = logging.getLogger(__name__)
    
    try:
        # Update status to processing
        update_import_job_status(
            job_id, 
            status='processing', 
            progress=0, 
            processed_records=0,
            celery_task_id=self.request.id,
            update_fields=['status', 'progress', 'processed_records', 'celery_task_id', 'last_updated_at']
        )
        
        # Parse CSV
        records = parse_csv_file(file_content)
        
        if not records:
            update_import_job_status(
                job_id,
                status='failed',
                progress=0,
                processed_records=0,
                errors=[{'error': 'CSV file is empty or invalid'}],
                update_fields=['status', 'progress', 'processed_records', 'errors', 'completed_at', 'last_updated_at']
            )
            return
        
        # Check for cancellation before processing
        from apps.uploads.selectors import get_import_job_by_id
        job = get_import_job_by_id(job_id)
        if job and job.status == 'cancelled':
            logger.info(f"Import job {job_id} was cancelled before processing")
            return
        
        # Process records in chunks (adaptive chunk size)
        processed_count, error_count, errors = process_csv_chunk(
            job_id=job_id,
            records=records,
            chunk_size=None  # Let function determine optimal chunk size
        )
        
        # Final check for cancellation
        job = get_import_job_by_id(job_id)
        if job and job.status == 'cancelled':
            logger.info(f"Import job {job_id} was cancelled during processing")
            return
        
        # Mark as completed with final counts
        update_import_job_status(
            job_id,
            status='completed',
            progress=100,
            processed_records=processed_count,
            errors=errors[-100:] if len(errors) > 100 else errors,
            update_fields=['status', 'progress', 'processed_records', 'errors', 'completed_at', 'last_updated_at']
        )
        
        logger.info(f"Import job {job_id} completed: {processed_count} records processed, {error_count} errors")
        
    except Exception as e:
        # Mark as failed
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Import job {job_id} failed: {str(e)}\n{error_trace}")
        
        update_import_job_status(
            job_id,
            status='failed',
            progress=0,
            errors=[{'error': str(e), 'traceback': error_trace}],
            update_fields=['status', 'progress', 'errors', 'completed_at', 'last_updated_at']
        )
        raise

