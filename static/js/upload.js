// Upload page JavaScript

let progressInterval = null;
let currentJobId = null;
let pollAttempts = 0;
const MAX_POLL_ATTEMPTS = 3600; // 1 hour max for very large files (3600 * 10 seconds)
let droppedFile = null; // Store dropped file

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    setupFileInput();
    setupDragAndDrop();
});

// Setup file input change handler
function setupFileInput() {
    const fileInput = document.getElementById('csv-file');
    const fileNameSpan = document.getElementById('file-name');
    const uploadText = document.getElementById('upload-text');
    
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            droppedFile = null; // Clear dropped file when user selects new one
            fileNameSpan.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(2)} KB)`;
            fileNameSpan.style.display = 'block';
            uploadText.textContent = 'Click to change file';
        } else {
            droppedFile = null;
            fileNameSpan.style.display = 'none';
            uploadText.textContent = 'Choose CSV file or drag it here';
        }
    });
}

// Setup drag and drop
function setupDragAndDrop() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('csv-file');
    const fileNameSpan = document.getElementById('file-name');
    const uploadText = document.getElementById('upload-text');
    
    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });
    
    // Highlight drop area when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.style.backgroundColor = '#e3f2fd';
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.style.backgroundColor = '#f8f9fa';
        }, false);
    });
    
    // Handle dropped files
    uploadArea.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length > 0) {
            const file = files[0];
            if (file.name.endsWith('.csv')) {
                // Store the dropped file
                droppedFile = file;
                
                // Try to assign to input (modern browsers)
                try {
                    if (typeof DataTransfer !== 'undefined') {
                        const dataTransfer = new DataTransfer();
                        dataTransfer.items.add(file);
                        fileInput.files = dataTransfer.files;
                    }
                } catch (err) {
                    // Fallback: file will be used from droppedFile variable
                    console.log('Using fallback file assignment');
                }
                
                fileNameSpan.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(2)} KB)`;
                fileNameSpan.style.display = 'block';
                uploadText.textContent = 'Click to change file';
            } else {
                alert('Please select a CSV file');
            }
        }
    }, false);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

// Handle file upload
document.getElementById('upload-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const fileInput = document.getElementById('csv-file');
    // Use dropped file if available, otherwise use input file
    const file = droppedFile || (fileInput.files && fileInput.files[0]);
    
    if (!file) {
        alert('Please select a CSV file');
        return;
    }
    
    // Reset dropped file after use
    droppedFile = null;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        // Show progress section
        document.getElementById('upload-progress').style.display = 'block';
        document.getElementById('upload-success').style.display = 'none';
        document.getElementById('upload-errors').style.display = 'none';
        document.getElementById('upload-btn').disabled = true;
        document.getElementById('cancel-btn').style.display = 'block';
        
        // Reset progress
        updateProgress({
            status: 'pending',
            progress: 0,
            processed_records: 0,
            total_records: 0
        });
        
        // Upload file
        const response = await fetch('/api/uploads/upload/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
            },
            body: formData,
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Upload failed');
        }
        
        const job = await response.json();
        currentJobId = job.id;
        pollAttempts = 0;
        
        // Start polling for progress
        startProgressPolling(job.id);
        
    } catch (error) {
        alert('Error uploading file: ' + error.message);
        document.getElementById('upload-btn').disabled = false;
        document.getElementById('upload-progress').style.display = 'none';
    }
});

// Calculate dynamic polling interval based on file size
function getPollingInterval(totalRecords) {
    if (totalRecords < 100) {
        return 500; // 0.5 seconds for very small files
    } else if (totalRecords < 1000) {
        return 1000; // 1 second for small files
    } else if (totalRecords < 10000) {
        return 2000; // 2 seconds for medium files
    } else if (totalRecords < 100000) {
        return 5000; // 5 seconds for large files
    } else {
        return 10000; // 10 seconds for very large files
    }
}

// Start polling for progress
function startProgressPolling(jobId) {
    // Clear any existing interval
    if (progressInterval) {
        clearInterval(progressInterval);
    }
    
    let currentPollingInterval = 2000; // Default interval in milliseconds
    let lastJobData = null;
    let lastPollTime = Date.now();
    
    const pollProgress = async () => {
        try {
            pollAttempts++;
            
            // Stop polling if max attempts reached
            if (pollAttempts > MAX_POLL_ATTEMPTS) {
                clearInterval(progressInterval);
                document.getElementById('upload-btn').disabled = false;
                alert('Upload is taking too long. Please check the server logs.');
                return;
            }
            
            const job = await apiRequest(`/api/uploads/progress/${jobId}/`);
            
            // Update polling interval dynamically based on total records
            if (job.total_records) {
                const newInterval = getPollingInterval(job.total_records);
                if (newInterval !== currentPollingInterval) {
                    currentPollingInterval = newInterval;
                    // Restart with new interval
                    clearInterval(progressInterval);
                    progressInterval = setInterval(pollProgress, currentPollingInterval);
                }
            }
            
            // Update progress
            updateProgress(job);
            
            // Staleness detection: Check if job hasn't updated in a while
            if (job.last_updated_at) {
                const lastUpdate = new Date(job.last_updated_at);
                const now = new Date();
                const minutesSinceUpdate = (now - lastUpdate) / (1000 * 60);
                
                // If no update for 5 minutes and still processing, show warning
                if (job.status === 'processing' && minutesSinceUpdate > 5) {
                    document.getElementById('status-text').textContent = 
                        `Processing... (No update for ${Math.floor(minutesSinceUpdate)} minutes - may be stalled)`;
                }
            }
            
            // Calculate estimated time remaining for large files
            if (job.status === 'processing' && job.total_records > 1000 && job.processed_records > 0) {
                const now = Date.now();
                const timeElapsed = (now - lastPollTime) / 1000; // seconds
                
                if (lastJobData && lastJobData.processed_records < job.processed_records && timeElapsed > 0) {
                    const recordsProcessed = job.processed_records - lastJobData.processed_records;
                    const recordsPerSecond = recordsProcessed / timeElapsed;
                    const remainingRecords = job.total_records - job.processed_records;
                    const estimatedSeconds = remainingRecords / recordsPerSecond;
                    
                    if (estimatedSeconds > 0 && estimatedSeconds < 3600 && recordsPerSecond > 0) {
                        const minutes = Math.floor(estimatedSeconds / 60);
                        const seconds = Math.floor(estimatedSeconds % 60);
                        document.getElementById('status-text').textContent = 
                            `Processing... (Est. ${minutes}m ${seconds}s remaining)`;
                    }
                }
                lastJobData = job;
                lastPollTime = now;
            }
            
            // Handle different statuses
            if (job.status === 'completed') {
                clearInterval(progressInterval);
                document.getElementById('upload-btn').disabled = false;
                document.getElementById('cancel-btn').style.display = 'none';
                showSuccess(job);
            } else if (job.status === 'failed') {
                clearInterval(progressInterval);
                document.getElementById('upload-btn').disabled = false;
                document.getElementById('cancel-btn').style.display = 'none';
                showErrors(job.errors || [{'error': 'Upload failed. Please check the file format.'}]);
            } else if (job.status === 'cancelled') {
                clearInterval(progressInterval);
                document.getElementById('upload-btn').disabled = false;
                document.getElementById('cancel-btn').style.display = 'none';
                document.getElementById('status-text').textContent = 'Cancelled';
                alert('Upload has been cancelled.');
            } else if (job.status === 'processing' || job.status === 'pending') {
                // Continue polling
                // If stuck in pending for too long, show warning
                if (job.status === 'pending' && pollAttempts > 10) {
                    document.getElementById('status-text').textContent = 
                        'Pending - Waiting for Celery worker to start processing...';
                }
            }
        } catch (error) {
            console.error('Error polling progress:', error);
            // If job not found, stop polling
            if (error.message && error.message.includes('not found')) {
                clearInterval(progressInterval);
                document.getElementById('upload-btn').disabled = false;
                alert('Import job not found. The upload may have failed.');
            }
        }
    };
    
    // Start polling with initial interval
    progressInterval = setInterval(pollProgress, currentPollingInterval);
}

// Update progress UI
function updateProgress(job) {
    const progress = job.progress || 0;
    const processed = job.processed_records || 0;
    const total = job.total_records || 0;
    
    // Update progress bar with smooth animation
    document.getElementById('progress-bar').style.width = `${progress}%`;
    document.getElementById('progress-text').textContent = `${progress}%`;
    
    // Update counts
    document.getElementById('processed-count').textContent = processed.toLocaleString();
    document.getElementById('total-count').textContent = total.toLocaleString();
    
    // Update status (don't override if it has estimated time)
    const statusText = document.getElementById('status-text');
    if (!statusText.textContent.includes('Est.')) {
        statusText.textContent = job.status.charAt(0).toUpperCase() + job.status.slice(1);
    }
}

// Show success message
function showSuccess(job) {
    document.getElementById('upload-progress').style.display = 'none';
    document.getElementById('upload-success').style.display = 'block';
    document.getElementById('success-message').textContent = 
        `Successfully processed ${job.processed_records} out of ${job.total_records} records.`;
    
    if (job.errors && job.errors.length > 0) {
        showErrors(job.errors);
    }
}

// Show errors
function showErrors(errors) {
    if (!errors || errors.length === 0) {
        return;
    }
    
    const errorsDiv = document.getElementById('upload-errors');
    errorsDiv.style.display = 'block';
    errorsDiv.innerHTML = '<h4>Errors:</h4>' + 
        errors.slice(0, 10).map(error => 
            `<p>Row ${error.row || 'N/A'}: ${error.error || error}</p>`
        ).join('');
}

// Cancel upload
async function cancelUpload() {
    if (!currentJobId) {
        return;
    }
    
    if (!confirm('Are you sure you want to cancel this upload? The operation will be stopped immediately.')) {
        return;
    }
    
    try {
        const response = await apiRequest(`/api/uploads/cancel/${currentJobId}/`, {
            method: 'POST',
        });
        
        // Stop polling
        if (progressInterval) {
            clearInterval(progressInterval);
        }
        
        document.getElementById('upload-btn').disabled = false;
        document.getElementById('cancel-btn').style.display = 'none';
        document.getElementById('status-text').textContent = 'Cancelled';
        
        alert('Upload has been cancelled successfully.');
    } catch (error) {
        alert('Error cancelling upload: ' + error.message);
    }
}

