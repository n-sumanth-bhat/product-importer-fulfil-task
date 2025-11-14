"""
Selectors for ImportJob read operations.
"""
from apps.uploads.models import ImportJob


def get_import_job_by_id(job_id):
    """Get an import job by ID."""
    try:
        return ImportJob.objects.get(id=job_id)
    except ImportJob.DoesNotExist:
        return None


def list_import_jobs(limit=None):
    """List import jobs, optionally limited."""
    queryset = ImportJob.objects.all()
    if limit:
        queryset = queryset[:limit]
    return queryset

