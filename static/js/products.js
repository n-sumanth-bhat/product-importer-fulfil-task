// Products page JavaScript

let currentPage = 1;
let pageSize = 20;
let filters = {};

// Load products on page load
document.addEventListener('DOMContentLoaded', () => {
    loadProducts();
});

// Load products from API
async function loadProducts() {
    try {
        const params = new URLSearchParams({
            page: currentPage,
            page_size: pageSize,
            ...filters,
        });
        
        const data = await apiRequest(`/api/products/?${params}`);
        
        renderProducts(data.results);
        renderPagination(data.count, data.page, data.page_size);
    } catch (error) {
        console.error('Error loading products:', error);
        document.getElementById('products-tbody').innerHTML = 
            '<tr><td colspan="6">Error loading products. Please try again.</td></tr>';
    }
}

// Render products table
function renderProducts(products) {
    const tbody = document.getElementById('products-tbody');
    
    if (products.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6">No products found.</td></tr>';
        return;
    }
    
    tbody.innerHTML = products.map(product => `
        <tr>
            <td>${escapeHtml(product.sku)}</td>
            <td>${escapeHtml(product.name)}</td>
            <td>${escapeHtml(product.description || '')}</td>
            <td>${product.active ? 'Yes' : 'No'}</td>
            <td>${new Date(product.created_at).toLocaleDateString()}</td>
            <td class="action-buttons">
                <button class="btn btn-primary" onclick="editProduct(${product.id})">Edit</button>
                <button class="btn btn-danger" onclick="deleteProduct(${product.id})">Delete</button>
            </td>
        </tr>
    `).join('');
}

// Render pagination
function renderPagination(total, page, pageSize) {
    const totalPages = Math.ceil(total / pageSize);
    const pagination = document.getElementById('pagination');
    
    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }
    
    let html = '';
    
    if (page > 1) {
        html += `<button onclick="goToPage(${page - 1})">Previous</button>`;
    }
    
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= page - 2 && i <= page + 2)) {
            html += `<button class="${i === page ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
        } else if (i === page - 3 || i === page + 3) {
            html += `<span>...</span>`;
        }
    }
    
    if (page < totalPages) {
        html += `<button onclick="goToPage(${page + 1})">Next</button>`;
    }
    
    pagination.innerHTML = html;
}

// Pagination
function goToPage(page) {
    currentPage = page;
    loadProducts();
}

// Apply filters
function applyFilters() {
    filters = {};
    
    const sku = document.getElementById('filter-sku').value.trim();
    const name = document.getElementById('filter-name').value.trim();
    const description = document.getElementById('filter-description').value.trim();
    const active = document.getElementById('filter-active').value;
    
    if (sku) filters.sku = sku;
    if (name) filters.name = name;
    if (description) filters.description = description;
    if (active) filters.active = active;
    
    currentPage = 1;
    loadProducts();
}

// Clear filters
function clearFilters() {
    document.getElementById('filter-sku').value = '';
    document.getElementById('filter-name').value = '';
    document.getElementById('filter-description').value = '';
    document.getElementById('filter-active').value = '';
    filters = {};
    currentPage = 1;
    loadProducts();
}

// Open create modal
function openCreateModal() {
    document.getElementById('product-id').value = '';
    document.getElementById('product-sku').value = '';
    document.getElementById('product-name').value = '';
    document.getElementById('product-description').value = '';
    document.getElementById('product-active').checked = true;
    document.getElementById('modal-title').textContent = 'Create Product';
    document.getElementById('product-modal').style.display = 'block';
}

// Edit product
async function editProduct(productId) {
    try {
        const product = await apiRequest(`/api/products/${productId}/`);
        
        document.getElementById('product-id').value = product.id;
        document.getElementById('product-sku').value = product.sku;
        document.getElementById('product-name').value = product.name;
        document.getElementById('product-description').value = product.description || '';
        document.getElementById('product-active').checked = product.active;
        document.getElementById('modal-title').textContent = 'Edit Product';
        document.getElementById('product-modal').style.display = 'block';
    } catch (error) {
        showDialog('Error', 'Error loading product: ' + error.message, 'error');
    }
}

// Close modal
function closeModal() {
    document.getElementById('product-modal').style.display = 'none';
}

// Handle form submission
document.getElementById('product-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const productId = document.getElementById('product-id').value;
    const data = {
        sku: document.getElementById('product-sku').value,
        name: document.getElementById('product-name').value,
        description: document.getElementById('product-description').value,
        active: document.getElementById('product-active').checked,
    };
    
    try {
        if (productId) {
            await apiRequest(`/api/products/${productId}/`, {
                method: 'PUT',
                body: JSON.stringify(data),
            });
        } else {
            await apiRequest('/api/products/', {
                method: 'POST',
                body: JSON.stringify(data),
            });
        }
        
        closeModal();
        loadProducts();
        showDialog('Success', 'Product saved successfully!', 'success');
    } catch (error) {
        showDialog('Error', 'Error saving product: ' + error.message, 'error');
    }
});

// Delete product
async function deleteProduct(productId) {
    const confirmed = await showConfirmDialog(
        'Delete Product',
        'Are you sure you want to delete this product?'
    );
    
    if (!confirmed) {
        return;
    }
    
    try {
        await apiRequest(`/api/products/${productId}/`, {
            method: 'DELETE',
        });
        loadProducts();
        showDialog('Success', 'Product deleted successfully!', 'success');
    } catch (error) {
        showDialog('Error', 'Error deleting product: ' + error.message, 'error');
    }
}

// Bulk delete
async function confirmBulkDelete() {
    const confirmed = await showConfirmDialog(
        'Delete All Products',
        'Are you sure you want to delete ALL products? This action cannot be undone.'
    );
    
    if (!confirmed) {
        return;
    }
    
    try {
        const result = await apiRequest('/api/products/bulk-delete/', {
            method: 'DELETE',
        });
        showDialog('Success', result.message || 'All products deleted successfully!', 'success');
        loadProducts();
    } catch (error) {
        showDialog('Error', 'Error deleting products: ' + error.message, 'error');
    }
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

