"""
S3 service for file upload and streaming operations.
"""
import boto3
from django.conf import settings
from smart_open import open as smart_open
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_s3_client():
    """
    Get configured S3 client.
    
    Returns:
        boto3.client: Configured S3 client
    """
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )


def upload_file_to_s3(file_obj, file_name, job_id):
    """
    Upload file to S3 and return the S3 key.
    
    Args:
        file_obj: File-like object to upload
        file_name: Original file name
        job_id: Import job ID for organizing files
    
    Returns:
        tuple: (s3_key, file_size)
    """
    s3_client = get_s3_client()
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    # Generate S3 key: uploads/job_{job_id}/{timestamp}_{filename}
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    s3_key = f"uploads/job_{job_id}/{timestamp}_{file_name}"
    
    try:
        # Read file size
        file_obj.seek(0, 2)  # Seek to end
        file_size = file_obj.tell()
        file_obj.seek(0)  # Reset to beginning
        
        # Upload to S3
        s3_client.upload_fileobj(
            file_obj,
            bucket_name,
            s3_key,
            ExtraArgs={'ContentType': 'text/csv'}
        )
        
        logger.info(f"Uploaded file {file_name} to S3: {s3_key} ({file_size} bytes)")
        return s3_key, file_size
        
    except Exception as e:
        logger.error(f"Error uploading file to S3: {str(e)}", exc_info=True)
        raise


def get_s3_file_stream(s3_key):
    """
    Get streaming file object from S3 using smart_open.
    
    Args:
        s3_key: S3 object key
    
    Returns:
        file-like object: Streaming file object
    """
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    # Construct S3 URI
    s3_uri = f"s3://{bucket_name}/{s3_key}"
    
    # Use smart_open for efficient streaming
    # smart_open handles buffering and connection management
    return smart_open(
        s3_uri,
        'r',
        transport_params={
            'client': get_s3_client()
        }
    )

