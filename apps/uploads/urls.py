"""
URL routing for upload endpoints.
"""
from django.urls import path
from apps.uploads.api import CSVUploadAPIView, ImportJobProgressAPIView

app_name = 'uploads'

urlpatterns = [
    path('upload/', CSVUploadAPIView.as_view(), name='upload'),
    path('progress/<int:job_id>/', ImportJobProgressAPIView.as_view(), name='progress'),
]

