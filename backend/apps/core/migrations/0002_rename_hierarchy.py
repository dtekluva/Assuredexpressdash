"""
Rename Vertical → Zone and Zone → Hub to match new business terminology.

Model renames are state-only (db_table stays the same).
Field renames DO touch the DB (column renames) because downstream code
uses the new column names via db_column.

Order: rename Zone → Hub first, then Vertical → Zone, to avoid name conflict.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        # 1. Rename Zone model → Hub FIRST (avoids name conflict)
        #    State-only: db_table stays "core_zones"
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameModel(
                    old_name="Zone",
                    new_name="Hub",
                ),
            ],
            database_operations=[],
        ),

        # 2. Rename Vertical model → Zone
        #    State-only: db_table stays "core_verticals"
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameModel(
                    old_name="Vertical",
                    new_name="Zone",
                ),
            ],
            database_operations=[],
        ),

        # 3-6. Rename FK fields — these DO rename DB columns
        migrations.RenameField(
            model_name="Hub",
            old_name="vertical",
            new_name="zone",
        ),
        migrations.RenameField(
            model_name="Rider",
            old_name="zone",
            new_name="hub",
        ),
        migrations.RenameField(
            model_name="Merchant",
            old_name="zone",
            new_name="hub",
        ),
        migrations.RenameField(
            model_name="Order",
            old_name="zone",
            new_name="hub",
        ),

        # 7. Update Meta options
        migrations.AlterModelOptions(
            name="Hub",
            options={"ordering": ["zone", "name"]},
        ),
        migrations.AlterModelOptions(
            name="Rider",
            options={"ordering": ["hub", "last_name", "first_name"]},
        ),
        migrations.AlterModelOptions(
            name="Merchant",
            options={"ordering": ["hub", "business_name"]},
        ),
    ]
