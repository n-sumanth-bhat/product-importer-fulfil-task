# Webhook Testing Guide

This guide will help you test the webhook functionality in the Product Importer application.

## Overview

Webhooks are triggered automatically when products are:
- **Created** (`product.created`)
- **Updated** (`product.updated`)
- **Deleted** (`product.deleted`)

## Testing Methods

### Method 1: Using Webhook.site (Recommended for Quick Testing)

1. **Get a test URL:**
   - Visit https://webhook.site
   - Copy the unique URL provided (e.g., `https://webhook.site/unique-id-12345`)

2. **Create a webhook in the application:**
   - Go to the Webhooks page
   - Click "Add Webhook"
   - Enter the webhook.site URL
   - Select an event type (e.g., "Product Created")
   - Click "Save"

3. **Test the webhook:**
   - Click the "Test" button next to the webhook
   - Or perform the action (create/update/delete a product)
   - Check webhook.site to see the received payload

4. **Verify the payload:**
   - The payload will be in JSON format
   - It should contain product data (id, sku, name, description, active, created_at, etc.)

### Method 2: Using httpbin.org

1. **Create a webhook with httpbin URL:**
   - URL: `https://httpbin.org/post`
   - This will echo back the request details

2. **Test and check response:**
   - Use the "Test" button or trigger an event
   - The response will show headers, JSON payload, etc.

### Method 3: Using Local Test Server (Python)

Run the provided test server script:

```bash
python test_webhook_receiver.py
```

This will start a local server at `http://localhost:8001` that receives and displays webhook payloads.

**Note:** For local testing, you'll need to:
- Use a service like ngrok to expose your local server: `ngrok http 8001`
- Use the ngrok URL as your webhook URL

### Method 4: Using the Built-in Test Button

1. **Create a webhook** with any valid URL
2. **Click the "Test" button** next to the webhook
3. **View the test result** in the modal that appears
   - Status code
   - Response time
   - Success status
   - Response body (if any)
   - Error message (if failed)

## Testing Scenarios

### Scenario 1: Test Product Creation Webhook

1. Create a webhook for `product.created` event
2. Create a new product via the UI
3. Verify the webhook receives the product data

**Expected Payload:**
```json
{
  "id": 1,
  "sku": "TEST-SKU-001",
  "name": "Test Product",
  "description": "Test Description",
  "active": true,
  "created_at": "2025-01-15T10:30:00Z"
}
```

### Scenario 2: Test Product Update Webhook

1. Create a webhook for `product.updated` event
2. Edit an existing product
3. Verify the webhook receives the updated product data

### Scenario 3: Test Product Deletion Webhook

1. Create a webhook for `product.deleted` event
2. Delete a product
3. Verify the webhook receives the deleted product data (before deletion)

### Scenario 4: Test CSV Import Webhooks

1. Create webhooks for all three event types
2. Upload a CSV file with products
3. Verify webhooks are triggered for:
   - New products (product.created)
   - Updated products (product.updated)

**Note:** CSV imports process products in batches, so webhooks are triggered asynchronously via Celery.

## Webhook Configuration

### Headers

You can add custom headers to webhooks (e.g., for authentication):

```json
{
  "Authorization": "Bearer your-token-here",
  "X-Custom-Header": "custom-value"
}
```

### Enable/Disable

- **Enabled:** Webhook will be triggered for events
- **Disabled:** Webhook will be ignored (useful for temporarily disabling without deleting)

## Troubleshooting

### Webhook Not Triggering

1. **Check if webhook is enabled:**
   - Ensure the "Enabled" checkbox is checked

2. **Check Celery worker:**
   - Webhooks are processed asynchronously
   - Ensure Celery worker is running: `celery -A config.celery_app worker --loglevel=info`

3. **Check event type:**
   - Ensure the webhook event type matches the action performed

4. **Check logs:**
   - Check Celery worker logs for errors
   - Check Django server logs

### Webhook Failing

1. **Check URL validity:**
   - Ensure the URL is accessible
   - For local testing, use ngrok or similar service

2. **Check timeout:**
   - Webhooks have a 30-second timeout
   - Ensure the receiving endpoint responds quickly

3. **Check authentication:**
   - If using custom headers for authentication, verify they're correct

4. **Test manually:**
   - Use the "Test" button to verify the webhook URL is reachable

## Example Test Payloads

### Product Created
```json
{
  "id": 1,
  "sku": "PROD-001",
  "name": "Sample Product",
  "description": "This is a sample product",
  "active": true,
  "created_at": "2025-01-15T10:30:00Z"
}
```

### Product Updated
```json
{
  "id": 1,
  "sku": "PROD-001",
  "name": "Updated Product Name",
  "description": "Updated description",
  "active": false,
  "created_at": "2025-01-15T10:30:00Z"
}
```

### Product Deleted
```json
{
  "id": 1,
  "sku": "PROD-001",
  "name": "Deleted Product",
  "description": "This product was deleted",
  "active": true,
  "created_at": "2025-01-15T10:30:00Z"
}
```

## Best Practices

1. **Test webhooks before production use**
2. **Use webhook.site for initial testing**
3. **Monitor webhook delivery** (check Celery logs)
4. **Handle webhook failures gracefully** (implement retry logic if needed)
5. **Use authentication headers** for production webhooks
6. **Test with different event types** to ensure correct routing

