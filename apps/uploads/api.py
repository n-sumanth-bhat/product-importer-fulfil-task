"""
API views for CSV upload and import job tracking.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import StreamingHttpResponse, JsonResponse
from django.views import View
from apps.uploads.serializers import ImportJobSerializer
from apps.uploads.selectors import get_import_job_by_id
from apps.uploads.services import create_import_job, update_import_job_status
from apps.uploads.tasks import process_csv_import_task
from apps.uploads.s3_service import upload_file_to_s3
import json
import time
import logging

logger = logging.getLogger(__name__)


class CSVUploadAPIView(APIView):
    """Handle CSV file upload to S3 and trigger import task."""
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        """Upload CSV file to S3 and start import process."""
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_file = request.FILES['file']
        
        # Validate file type
        if not uploaded_file.name.endswith('.csv'):
            return Response(
                {'error': 'File must be a CSV file'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create import job first (before upload to get job_id)
        import_job = create_import_job(file_name=uploaded_file.name)
        
        try:
            # Upload file to S3 (no parsing, just upload)
            s3_key, file_size = upload_file_to_s3(uploaded_file, uploaded_file.name, import_job.id)
            
            # Update job with S3 metadata
            update_import_job_status(
                job_id=import_job.id,
                status='pending',
                phase='uploading',
                s3_key=s3_key,
                file_size=file_size,
                processed_records=0,
                update_fields=['status', 'phase', 's3_key', 'file_size', 'processed_records', 'last_updated_at']
            )
            
            # Trigger async task with S3 key (not file content)
            task = process_csv_import_task.delay(import_job.id, s3_key)
            
            # Store task ID for cancellation
            update_import_job_status(
                job_id=import_job.id,
                celery_task_id=task.id,
                update_fields=['celery_task_id', 'last_updated_at']
            )
            
        except Exception as e:
            # If upload or task queuing fails, mark job as failed
            logger.error(f"Error uploading file or queuing task: {str(e)}", exc_info=True)
            update_import_job_status(
                job_id=import_job.id,
                status='failed',
                errors=[{'error': f'Failed to upload file or start import: {str(e)}'}],
                update_fields=['status', 'errors', 'completed_at', 'last_updated_at']
            )
            return Response(
                {'error': f'Failed to upload file or start import: {str(e)}. Make sure S3 is configured and Celery worker is running.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Refresh job to get latest data
        import_job.refresh_from_db()
        serializer = ImportJobSerializer(import_job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ImportJobProgressAPIView(APIView):
    """Get import job progress (kept for backward compatibility)."""
    
    def get(self, request, job_id):
        """Get current progress of an import job."""
        job = get_import_job_by_id(job_id)
        if not job:
            return Response(
                {'error': 'Import job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Refresh from database to get latest data
        job.refresh_from_db()
        serializer = ImportJobSerializer(job)
        return Response(serializer.data)


class ImportJobStreamAPIView(View):
    """Server-Sent Events endpoint for real-time progress updates."""
    
    def get(self, request, job_id):
        """Stream progress updates via SSE."""
        job = get_import_job_by_id(job_id)
        if not job:
            return JsonResponse(
                {'error': 'Import job not found'},
                status=404
            )
        
        def event_stream():
            """Generator function that yields SSE events."""
            last_progress = -1
            last_processed = -1
            
            while True:
                # Get fresh job instance from database
                current_job = get_import_job_by_id(job_id)
                if not current_job:
                    break
                
                # Check if job is in terminal state
                if current_job.status in ('completed', 'failed', 'cancelled'):
                    # Send final update
                    data = {
                        'progress': current_job.progress,
                        'processed': current_job.processed_records,
                        'total': current_job.total_records,
                        'status': current_job.status,
                        'phase': current_job.phase,
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                    break
                
                # Only send update if progress or processed count changed
                if current_job.progress != last_progress or current_job.processed_records != last_processed:
                    data = {
                        'progress': current_job.progress,
                        'processed': current_job.processed_records,
                        'total': current_job.total_records,
                        'status': current_job.status,
                        'phase': current_job.phase,
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                    last_progress = current_job.progress
                    last_processed = current_job.processed_records
                
                # Sleep for 0.5 second before next check (lightweight polling)
                time.sleep(0.5)
        
        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
        return response


class ImportJobCancelAPIView(APIView):
    """Cancel an import job."""
    
    def post(self, request, job_id):
        """Cancel a running import job."""
        from apps.uploads.selectors import get_import_job_by_id
        from apps.uploads.services import update_import_job_status
        from celery.result import AsyncResult
        
        job = get_import_job_by_id(job_id)
        if not job:
            return Response(
                {'error': 'Import job not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if job can be cancelled
        if job.status in ('completed', 'failed', 'cancelled'):
            return Response(
                {'error': f'Cannot cancel job with status: {job.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Revoke Celery task if it exists
        if job.celery_task_id:
            try:
                from config.celery_app import app
                app.control.revoke(job.celery_task_id, terminate=True)
            except Exception as e:
                # Log error but continue with cancellation
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error revoking Celery task {job.celery_task_id}: {str(e)}")
        
        # Update job status to cancelled
        update_import_job_status(
            job_id=job_id,
            status='cancelled',
            update_fields=['status', 'completed_at', 'last_updated_at']
        )
        
        job.refresh_from_db()
        serializer = ImportJobSerializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)

