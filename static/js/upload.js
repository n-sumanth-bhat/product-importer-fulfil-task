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
        const uploadBtn = document.getElementById('upload-btn');
        
        if (file) {
            // Validate file type
            if (!file.name.toLowerCase().endsWith('.csv')) {
                showDialog('Invalid File Type', 'Please select a CSV file.', 'error');
                fileInput.value = '';
                uploadBtn.style.display = 'none';
                return;
            }
            
            droppedFile = null; // Clear dropped file when user selects new one
            fileNameSpan.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
            fileNameSpan.style.display = 'block';
            uploadText.textContent = 'Click to change file';
            uploadBtn.style.display = 'inline-block';
        } else {
            droppedFile = null;
            fileNameSpan.style.display = 'none';
            uploadText.textContent = 'Choose CSV file or drag it here';
            uploadBtn.style.display = 'none';
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
                
                // Validate file type
                if (!file.name.toLowerCase().endsWith('.csv')) {
                    showDialog('Invalid File Type', 'Please select a CSV file.', 'error');
                    return;
                }
                
                fileNameSpan.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
                fileNameSpan.style.display = 'block';
                uploadText.textContent = 'Click to change file';
                document.getElementById('upload-btn').style.display = 'inline-block';
            } else {
                showDialog('Invalid File Type', 'Please select a CSV file.', 'error');
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
        showDialog('No File Selected', 'Please select a CSV file to upload.', 'warning');
        return;
    }
    
    // Validate file type
    if (!file.name.toLowerCase().endsWith('.csv')) {
        showDialog('Invalid File Type', 'Please select a CSV file.', 'error');
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
        
        // Start SSE connection for real-time progress updates
        startSSEConnection(job.id);
        
    } catch (error) {
        showDialog('Upload Error', 'Error uploading file: ' + error.message, 'error');
        document.getElementById('upload-btn').disabled = false;
        document.getElementById('upload-progress').style.display = 'none';
    }
});

// Start SSE connection for real-time progress updates
function startSSEConnection(jobId) {
    // Close any existing SSE connection
    if (progressInterval) {
        if (progressInterval.close) {
            progressInterval.close();
        }
        progressInterval = null;
    }
    
    let lastJobData = null;
    let lastUpdateTime = Date.now();
    
    // Create EventSource for SSE
    const eventSource = new EventSource(`/api/uploads/stream/${jobId}/`);
    progressInterval = eventSource; // Store for cleanup
    
    // Handle incoming messages
    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            
            // Update progress UI
            updateProgress({
                progress: data.progress || 0,
                processed_records: data.processed || 0,
                total_records: data.total || 0,
                status: data.status || 'processing',
                phase: data.phase || 'processing'
            });
            
            // Update status text with phase information
            const statusText = document.getElementById('status-text');
            const phaseMap = {
                'uploading': 'Uploading to S3...',
                'parsing': 'Parsing CSV file...',
                'processing': 'Processing records...',
                'completed': 'Completed'
            };
            
            if (data.phase && phaseMap[data.phase]) {
                statusText.textContent = phaseMap[data.phase];
            }
            
            // Handle terminal states
            if (data.status === 'completed') {
                eventSource.close();
                document.getElementById('upload-btn').disabled = false;
                document.getElementById('cancel-btn').style.display = 'none';
                showSuccess({
                    processed_records: data.processed,
                    total_records: data.total,
                    errors: []
                });
            } else if (data.status === 'failed') {
                eventSource.close();
                document.getElementById('upload-btn').disabled = false;
                document.getElementById('cancel-btn').style.display = 'none';
                document.getElementById('upload-progress').style.display = 'none';
                showErrors([{'error': 'Upload failed. Please check the file format.'}]);
                resetFileInput();
            } else if (data.status === 'cancelled') {
                eventSource.close();
                document.getElementById('upload-btn').disabled = false;
                document.getElementById('cancel-btn').style.display = 'none';
                statusText.textContent = 'Cancelled';
                showDialog('Upload Cancelled', 'The upload has been cancelled.', 'warning');
            }
            
            lastJobData = data;
            lastUpdateTime = Date.now();
            
        } catch (error) {
            console.error('Error parsing SSE message:', error);
        }
    };
    
    // Handle connection errors
    eventSource.onerror = (error) => {
        console.error('SSE connection error:', error);
        
        // If connection closed and job might still be processing, try to reconnect
        if (eventSource.readyState === EventSource.CLOSED) {
            // Check if job is still processing by making a regular API call
            setTimeout(async () => {
                try {
                    const job = await apiRequest(`/api/uploads/progress/${jobId}/`);
                    if (job.status === 'processing' || job.status === 'pending') {
                        // Job still processing, reconnect
                        console.log('Reconnecting SSE...');
                        startSSEConnection(jobId);
                    } else {
                        // Job finished, update UI
                        updateProgress(job);
                        if (job.status === 'completed') {
                            showSuccess(job);
                        } else if (job.status === 'failed') {
                            showErrors(job.errors || [{'error': 'Upload failed.'}]);
                        }
                        document.getElementById('upload-btn').disabled = false;
                        document.getElementById('cancel-btn').style.display = 'none';
                    }
                } catch (err) {
                    console.error('Error checking job status:', err);
                }
            }, 2000);
        }
    };
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
    
    // Update status with phase information if available
    const statusText = document.getElementById('status-text');
    if (job.phase) {
        const phaseMap = {
            'uploading': 'Uploading to S3...',
            'parsing': 'Parsing CSV file...',
            'processing': 'Processing records...',
            'completed': 'Completed'
        };
        if (phaseMap[job.phase]) {
            statusText.textContent = phaseMap[job.phase];
        }
    } else if (!statusText.textContent.includes('Est.') && !statusText.textContent.includes('...')) {
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
    
    // Reset file input and hide upload button
    resetFileInput();
}

// Reset file input
function resetFileInput() {
    const fileInput = document.getElementById('csv-file');
    const fileNameSpan = document.getElementById('file-name');
    const uploadText = document.getElementById('upload-text');
    const uploadBtn = document.getElementById('upload-btn');
    
    fileInput.value = '';
    droppedFile = null;
    fileNameSpan.style.display = 'none';
    uploadText.textContent = 'Choose CSV file or drag it here';
    uploadBtn.style.display = 'none';
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
    
    const confirmed = await showConfirmDialog(
        'Cancel Upload',
        'Are you sure you want to cancel this upload? The operation will be stopped immediately.'
    );
    
    if (!confirmed) {
        return;
    }
    
    try {
        const response = await apiRequest(`/api/uploads/cancel/${currentJobId}/`, {
            method: 'POST',
        });
        
        // Close SSE connection if open
        if (progressInterval) {
            if (progressInterval.close) {
                progressInterval.close();
            }
            progressInterval = null;
        }
        
        document.getElementById('upload-btn').disabled = false;
        document.getElementById('cancel-btn').style.display = 'none';
        document.getElementById('status-text').textContent = 'Cancelled';
        
        showDialog('Upload Cancelled', 'The upload has been cancelled successfully.', 'success');
    } catch (error) {
        showDialog('Error', 'Error cancelling upload: ' + error.message, 'error');
    }
}

