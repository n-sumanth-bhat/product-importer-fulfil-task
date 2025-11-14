"""
Celery tasks for async CSV import processing.
"""
from celery import shared_task
from apps.uploads.services import (
    stream_csv_from_s3,
    process_csv_stream,
    preload_existing_skus,
    update_import_job_status,
    count_csv_records
)

# Import celery app to ensure tasks are registered
try:
    from config.celery_app import app as celery_app
except ImportError:
    # Fallback if import fails
    celery_app = None


@shared_task(name='apps.uploads.tasks.process_csv_import_task', bind=True)
def process_csv_import_task(self, job_id, s3_key):
    """
    Process CSV import asynchronously from S3.
    
    Args:
        self: Task instance (for cancellation support)
        job_id: Import job ID
        s3_key: S3 object key for the CSV file
    """
    import logging
    import traceback
    
    logger = logging.getLogger(__name__)
    
    try:
        # Update status to processing, phase to parsing (10-20%)
        update_import_job_status(
            job_id, 
            status='processing',
            phase='parsing',
            progress=15,  # Mid-point of parsing phase
            processed_records=0,
            celery_task_id=self.request.id,
            update_fields=['status', 'phase', 'progress', 'processed_records', 'celery_task_id', 'last_updated_at']
        )
        
        # Check for cancellation before processing
        from apps.uploads.selectors import get_import_job_by_id
        job = get_import_job_by_id(job_id)
        if job and job.status == 'cancelled':
            logger.info(f"Import job {job_id} was cancelled before processing")
            return
        
        # Preload existing SKUs once at the start (eliminates N+1 queries)
        logger.info(f"Preloading existing SKUs for job {job_id}...")
        existing_skus_dict = preload_existing_skus()
        
        # Check for cancellation after preloading
        job = get_import_job_by_id(job_id)
        if job and job.status == 'cancelled':
            logger.info(f"Import job {job_id} was cancelled after preloading SKUs")
            return
        
        # Count total records first (quick pass to get accurate total)
        logger.info(f"Counting total records in CSV file for job {job_id}...")
        total_records = count_csv_records(s3_key)
        
        # Update job with total records (set once, don't change during processing)
        update_import_job_status(
            job_id=job_id,
            total_records=total_records,
            update_fields=['total_records', 'last_updated_at']
        )
        
        # Check for cancellation after counting
        job = get_import_job_by_id(job_id)
        if job and job.status == 'cancelled':
            logger.info(f"Import job {job_id} was cancelled after counting records")
            return
        
        # Stream CSV from S3 and process in micro-batches
        logger.info(f"Starting CSV stream processing for job {job_id} from S3: {s3_key}")
        csv_generator = stream_csv_from_s3(s3_key)
        
        # Process stream in micro-batches (500 records per batch)
        processed_count, error_count, errors = process_csv_stream(
            job_id=job_id,
            csv_generator=csv_generator,
            existing_skus_dict=existing_skus_dict,
            total_records=total_records,
            micro_batch_size=500
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
            phase='completed',
            progress=100,
            processed_records=processed_count,
            total_records=total_records,
            errors=errors[-100:] if len(errors) > 100 else errors,
            update_fields=['status', 'phase', 'progress', 'processed_records', 'total_records', 'errors', 'completed_at', 'last_updated_at']
        )
        
        logger.info(f"Import job {job_id} completed: {processed_count}/{total_records} records processed, {error_count} errors")
        
    except Exception as e:
        # Mark as failed
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

