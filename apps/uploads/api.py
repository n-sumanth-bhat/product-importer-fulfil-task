"""
API views for CSV upload and import job tracking.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from apps.uploads.serializers import ImportJobSerializer
from apps.uploads.selectors import get_import_job_by_id
from apps.uploads.services import create_import_job, update_import_job_status, parse_csv_file
from apps.uploads.tasks import process_csv_import_task


class CSVUploadAPIView(APIView):
    """Handle CSV file upload and trigger import task."""
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        """Upload CSV file and start import process."""
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
        
        # Read file content
        try:
            file_content = uploaded_file.read()
        except Exception as e:
            return Response(
                {'error': f'Error reading file: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse CSV to get record count
        try:
            records = parse_csv_file(file_content)
            total_records = len(records)
        except Exception as e:
            return Response(
                {'error': f'Error parsing CSV: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create import job
        import_job = create_import_job(file_name=uploaded_file.name)
        update_import_job_status(
            job_id=import_job.id,
            status='pending',
            total_records=total_records,
            processed_records=0
        )
        
        # Trigger async task
        try:
            task = process_csv_import_task.delay(import_job.id, file_content.decode('utf-8'))
            # Store task ID for cancellation
            update_import_job_status(
                job_id=import_job.id,
                celery_task_id=task.id,
                update_fields=['celery_task_id', 'last_updated_at']
            )
        except Exception as e:
            # If Celery task fails to queue, mark job as failed
            update_import_job_status(
                job_id=import_job.id,
                status='failed',
                errors=[{'error': f'Failed to queue import task: {str(e)}'}]
            )
            return Response(
                {'error': f'Failed to start import: {str(e)}. Make sure Celery worker is running.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Refresh job to get latest data
        import_job.refresh_from_db()
        serializer = ImportJobSerializer(import_job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ImportJobProgressAPIView(APIView):
    """Get import job progress."""
    
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

