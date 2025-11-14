"""
URL routing for upload endpoints.
"""
from django.urls import path
from apps.uploads.api import (
    CSVUploadAPIView, 
    ImportJobProgressAPIView, 
    ImportJobCancelAPIView,
    ImportJobStreamAPIView
)

app_name = 'uploads'

urlpatterns = [
    path('upload/', CSVUploadAPIView.as_view(), name='upload'),
    path('progress/<int:job_id>/', ImportJobProgressAPIView.as_view(), name='progress'),
    path('stream/<int:job_id>/', ImportJobStreamAPIView.as_view(), name='stream'),
    path('cancel/<int:job_id>/', ImportJobCancelAPIView.as_view(), name='cancel'),
]

