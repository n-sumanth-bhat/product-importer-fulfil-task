"""
Migration to add case-insensitive unique constraint on SKU field.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            # Create unique index with LOWER() for case-insensitive uniqueness
            sql="CREATE UNIQUE INDEX IF NOT EXISTS products_sku_lower_unique ON products (LOWER(sku));",
            reverse_sql="DROP INDEX IF EXISTS products_sku_lower_unique;"
        ),
    ]

