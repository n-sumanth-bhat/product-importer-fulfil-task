// Webhooks page JavaScript

let filters = {};

// Load webhooks on page load
document.addEventListener('DOMContentLoaded', () => {
    loadWebhooks();
});

// Load webhooks from API
async function loadWebhooks() {
    try {
        const params = new URLSearchParams();
        
        const eventType = document.getElementById('filter-event-type').value;
        const enabled = document.getElementById('filter-enabled').value;
        
        if (eventType) params.append('event_type', eventType);
        if (enabled) params.append('enabled', enabled);
        
        const webhooks = await apiRequest(`/api/webhooks/?${params}`);
        renderWebhooks(webhooks);
    } catch (error) {
        console.error('Error loading webhooks:', error);
        document.getElementById('webhooks-tbody').innerHTML = 
            '<tr><td colspan="5">Error loading webhooks. Please try again.</td></tr>';
    }
}

// Render webhooks table
function renderWebhooks(webhooks) {
    const tbody = document.getElementById('webhooks-tbody');
    
    if (webhooks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5">No webhooks found.</td></tr>';
        return;
    }
    
    tbody.innerHTML = webhooks.map(webhook => `
        <tr>
            <td>${escapeHtml(webhook.url)}</td>
            <td>${escapeHtml(webhook.event_type)}</td>
            <td>${webhook.enabled ? 'Yes' : 'No'}</td>
            <td>${new Date(webhook.created_at).toLocaleDateString()}</td>
            <td class="action-buttons">
                <button class="btn btn-primary" onclick="editWebhook(${webhook.id})">Edit</button>
                <button class="btn btn-secondary" onclick="testWebhook(${webhook.id})">Test</button>
                <button class="btn btn-danger" onclick="deleteWebhook(${webhook.id})">Delete</button>
            </td>
        </tr>
    `).join('');
}

// Open create modal
function openCreateModal() {
    document.getElementById('webhook-id').value = '';
    document.getElementById('webhook-url').value = '';
    document.getElementById('webhook-event-type').value = '';
    document.getElementById('webhook-enabled').checked = true;
    document.getElementById('webhook-headers').value = '';
    document.getElementById('modal-title').textContent = 'Add Webhook';
    document.getElementById('webhook-modal').style.display = 'block';
}

// Edit webhook
async function editWebhook(webhookId) {
    try {
        const webhook = await apiRequest(`/api/webhooks/${webhookId}/`);
        
        document.getElementById('webhook-id').value = webhook.id;
        document.getElementById('webhook-url').value = webhook.url;
        document.getElementById('webhook-event-type').value = webhook.event_type;
        document.getElementById('webhook-enabled').checked = webhook.enabled;
        document.getElementById('webhook-headers').value = JSON.stringify(webhook.headers || {}, null, 2);
        document.getElementById('modal-title').textContent = 'Edit Webhook';
        document.getElementById('webhook-modal').style.display = 'block';
    } catch (error) {
        alert('Error loading webhook: ' + error.message);
    }
}

// Close modal
function closeModal() {
    document.getElementById('webhook-modal').style.display = 'none';
}

// Handle form submission
document.getElementById('webhook-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const webhookId = document.getElementById('webhook-id').value;
    let headers = {};
    
    try {
        const headersText = document.getElementById('webhook-headers').value.trim();
        if (headersText) {
            headers = JSON.parse(headersText);
        }
    } catch (error) {
        alert('Invalid JSON in headers field');
        return;
    }
    
    const data = {
        url: document.getElementById('webhook-url').value,
        event_type: document.getElementById('webhook-event-type').value,
        enabled: document.getElementById('webhook-enabled').checked,
        headers: headers,
    };
    
    try {
        if (webhookId) {
            await apiRequest(`/api/webhooks/${webhookId}/`, {
                method: 'PUT',
                body: JSON.stringify(data),
            });
        } else {
            await apiRequest('/api/webhooks/', {
                method: 'POST',
                body: JSON.stringify(data),
            });
        }
        
        closeModal();
        loadWebhooks();
        alert('Webhook saved successfully!');
    } catch (error) {
        alert('Error saving webhook: ' + error.message);
    }
});

// Delete webhook
async function deleteWebhook(webhookId) {
    if (!confirm('Are you sure you want to delete this webhook?')) {
        return;
    }
    
    try {
        await apiRequest(`/api/webhooks/${webhookId}/`, {
            method: 'DELETE',
        });
        loadWebhooks();
        alert('Webhook deleted successfully!');
    } catch (error) {
        alert('Error deleting webhook: ' + error.message);
    }
}

// Test webhook
async function testWebhook(webhookId) {
    try {
        const result = await apiRequest(`/api/webhooks/${webhookId}/test/`, {
            method: 'POST',
        });
        
        showTestResult(result);
    } catch (error) {
        alert('Error testing webhook: ' + error.message);
    }
}

// Show test result
function showTestResult(result) {
    const content = document.getElementById('test-result-content');
    
    let html = '<div class="test-result">';
    html += `<p><strong>Status Code:</strong> ${result.status_code || 'N/A'}</p>`;
    html += `<p><strong>Response Time:</strong> ${result.response_time ? result.response_time.toFixed(3) + 's' : 'N/A'}</p>`;
    html += `<p><strong>Success:</strong> ${result.success ? 'Yes' : 'No'}</p>`;
    
    if (result.error) {
        html += `<p><strong>Error:</strong> ${escapeHtml(result.error)}</p>`;
    }
    
    if (result.response_body) {
        html += `<p><strong>Response Body:</strong></p><pre>${escapeHtml(result.response_body)}</pre>`;
    }
    
    html += '</div>';
    
    content.innerHTML = html;
    document.getElementById('test-result-modal').style.display = 'block';
}

// Close test modal
function closeTestModal() {
    document.getElementById('test-result-modal').style.display = 'none';
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

