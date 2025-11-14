# Product Importer - Django Application

A Django-based web application for importing and managing products from CSV files. Built with Django, Django REST Framework, Celery, and PostgreSQL.

## Features

- **CSV Upload**: Upload large CSV files (up to 500,000 records) with real-time progress tracking
- **Product Management**: Full CRUD operations for products with filtering and pagination
- **Bulk Delete**: Delete all products with confirmation
- **Webhook Management**: Configure and manage webhooks for product events
- **Async Processing**: Celery-based async processing for large file imports

## Tech Stack

- **Backend**: Django 4.2.7, Django REST Framework
- **Database**: PostgreSQL
- **Task Queue**: Celery with Redis
- **Frontend**: Django Templates with vanilla JavaScript

## Project Structure

```
product-importer/
├── apps/
│   ├── products/      # Product management app
│   ├── uploads/        # CSV upload and import tracking
│   └── webhooks/       # Webhook configuration
├── config/             # Django project settings
├── static/             # Static files (CSS, JS)
├── templates/          # HTML templates
└── celery_app.py       # Celery configuration
```

## Architecture

The project follows the Hacksoft style guide pattern:
- **api.py**: API views (request/response handling only)
- **selectors.py**: All read operations (database queries)
- **services.py**: All write operations (business logic)
- **models.py**: Database models
- **serializers.py**: DRF serializers

## Setup Instructions

### Prerequisites

- Python 3.10+
- PostgreSQL
- Redis

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd product-importer-fulfil-task
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the project root:
```
SECRET_KEY=your-secret-key-here
DEBUG=True
DB_NAME=product_importer
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

5. Create PostgreSQL database:
```sql
CREATE DATABASE product_importer;
```

6. Run migrations:
```bash
python manage.py migrate
```

7. Create a superuser (optional):
```bash
python manage.py createsuperuser
```

### Running the Application

1. Start Redis (required for Celery):
```bash
redis-server
```

2. Start Celery worker (in a separate terminal):
```bash
celery -A celery_app worker --loglevel=info
```

3. Start Django development server:
```bash
python manage.py runserver
```

4. Access the application:
- Web UI: http://localhost:8000
- Admin Panel: http://localhost:8000/admin
- API: http://localhost:8000/api/

## API Endpoints

### Products
- `GET /api/products/` - List products (with filtering and pagination)
- `POST /api/products/` - Create product
- `GET /api/products/{id}/` - Get product details
- `PUT /api/products/{id}/` - Update product
- `DELETE /api/products/{id}/` - Delete product
- `DELETE /api/products/bulk-delete/` - Delete all products

### Uploads
- `POST /api/uploads/upload/` - Upload CSV file
- `GET /api/uploads/progress/{job_id}/` - Get upload progress

### Webhooks
- `GET /api/webhooks/` - List webhooks
- `POST /api/webhooks/` - Create webhook
- `GET /api/webhooks/{id}/` - Get webhook details
- `PUT /api/webhooks/{id}/` - Update webhook
- `DELETE /api/webhooks/{id}/` - Delete webhook
- `POST /api/webhooks/{id}/test/` - Test webhook

## CSV Format

The CSV file should have the following columns:
- `SKU` (required): Product SKU (case-insensitive, unique)
- `Name` (required): Product name
- `Description` (optional): Product description

## Features Implementation

### Case-Insensitive SKU
Products are identified by SKU in a case-insensitive manner. If a product with the same SKU (case-insensitive) is uploaded, it will be updated instead of creating a duplicate.

### Real-time Progress
The upload progress is tracked using polling. The UI polls the progress endpoint every 2 seconds to update the progress bar.

### Webhook Events
Webhooks are triggered on the following events:
- `product.created`: When a new product is created
- `product.updated`: When a product is updated
- `product.deleted`: When a product is deleted

## Development

### Running Tests
```bash
python manage.py test
```

### Code Style
The project follows Django and PEP 8 conventions. Business logic is separated from views using the services/selectors pattern.

## Deployment

For production deployment:
1. Set `DEBUG=False` in production settings
2. Configure proper `ALLOWED_HOSTS`
3. Set up proper database credentials
4. Configure static file serving
5. Set up Celery workers and Redis in production environment

## License

This project is part of a technical assessment.
