// Main JavaScript utilities

// CSRF Token helper
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function getCsrfToken() {
    return getCookie('csrftoken');
}

// API helper
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
    };
    
    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...(options.headers || {}),
        },
    };
    
    try {
        const response = await fetch(url, mergedOptions);
        
        // Handle empty responses (204 No Content, etc.)
        if (response.status === 204) {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return null; // Return null for empty responses
        }
        
        // Read response as text first to check if it's empty
        const text = await response.text();
        let data = null;
        
        // Only parse JSON if there's actual content
        if (text && text.trim()) {
            try {
                data = JSON.parse(text);
            } catch (parseError) {
                // If JSON parsing fails and it's an error response, use text as error message
                if (!response.ok) {
                    throw new Error(text || `HTTP error! status: ${response.status}`);
                }
                // If it's a successful response but not JSON, return the text
                data = text;
            }
        }
        
        if (!response.ok) {
            throw new Error(data?.error || data?.message || data || `HTTP error! status: ${response.status}`);
        }
        
        return data;
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    }
}

// Dialog helper functions
let dialogResolve = null;

function showDialog(title, message, type = 'info') {
    return new Promise((resolve) => {
        const overlay = document.getElementById('dialog-overlay');
        if (!overlay) {
            console.error('Dialog overlay not found');
            alert(message); // Fallback to alert if dialog doesn't exist
            resolve();
            return;
        }
        
        const titleEl = document.getElementById('dialog-title');
        const messageEl = document.getElementById('dialog-message');
        const okBtn = document.getElementById('dialog-ok-btn');
        const confirmBtn = document.getElementById('dialog-confirm-btn');
        const cancelBtn = document.getElementById('dialog-cancel-btn');
        
        if (!titleEl || !messageEl || !okBtn) {
            console.error('Dialog elements not found');
            alert(message); // Fallback to alert
            resolve();
            return;
        }
        
        titleEl.textContent = title;
        messageEl.textContent = message;
        
        // Hide all buttons first
        okBtn.style.display = 'none';
        confirmBtn.style.display = 'none';
        cancelBtn.style.display = 'none';
        
        // Show appropriate button
        okBtn.style.display = 'inline-block';
        
        // Reset title color first
        titleEl.style.color = '#333';
        
        // Set dialog type styling
        if (type === 'error') {
            titleEl.style.color = '#e74c3c';
        } else if (type === 'success') {
            titleEl.style.color = '#27ae60';
        } else if (type === 'warning') {
            titleEl.style.color = '#f39c12';
        }
        
        // Force display - remove inline style and add class
        overlay.removeAttribute('style');
        overlay.classList.add('show');
        overlay.style.setProperty('display', 'flex', 'important');
        dialogResolve = resolve;
    });
}

function showConfirmDialog(title, message) {
    return new Promise((resolve) => {
        const overlay = document.getElementById('dialog-overlay');
        if (!overlay) {
            console.error('Dialog overlay not found');
            const result = confirm(message); // Fallback to confirm
            resolve(result);
            return;
        }
        
        const titleEl = document.getElementById('dialog-title');
        const messageEl = document.getElementById('dialog-message');
        const okBtn = document.getElementById('dialog-ok-btn');
        const confirmBtn = document.getElementById('dialog-confirm-btn');
        const cancelBtn = document.getElementById('dialog-cancel-btn');
        
        if (!titleEl || !messageEl || !confirmBtn || !cancelBtn) {
            console.error('Dialog elements not found');
            const result = confirm(message); // Fallback to confirm
            resolve(result);
            return;
        }
        
        titleEl.textContent = title;
        messageEl.textContent = message;
        titleEl.style.color = '#333';
        
        // Hide all buttons first
        okBtn.style.display = 'none';
        confirmBtn.style.display = 'none';
        cancelBtn.style.display = 'none';
        
        // Show confirm and cancel buttons
        confirmBtn.style.display = 'inline-block';
        cancelBtn.style.display = 'inline-block';
        
        // Force display - remove inline style and add class
        overlay.removeAttribute('style');
        overlay.classList.add('show');
        overlay.style.setProperty('display', 'flex', 'important');
        dialogResolve = resolve;
    });
}

function confirmDialog() {
    if (dialogResolve) {
        dialogResolve(true);
        dialogResolve = null;
    }
    closeDialog();
}

function closeDialog() {
    const overlay = document.getElementById('dialog-overlay');
    if (overlay) {
        overlay.classList.remove('show');
        overlay.style.setProperty('display', 'none', 'important');
    }
    if (dialogResolve) {
        dialogResolve(false);
        dialogResolve = null;
    }
}

// Close dialog on overlay click
document.addEventListener('DOMContentLoaded', () => {
    const overlay = document.getElementById('dialog-overlay');
    if (overlay) {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                closeDialog();
            }
        });
    }
    
    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && overlay && overlay.style.display === 'flex') {
            closeDialog();
        }
    });
});

// Notification helper (kept for backward compatibility)
function showNotification(message, type = 'info') {
    return showDialog(type === 'error' ? 'Error' : type === 'success' ? 'Success' : 'Info', message, type);
}

