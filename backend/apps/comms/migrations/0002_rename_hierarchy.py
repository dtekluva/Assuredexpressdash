"""
Rename broadcast FK fields for new business terminology.
- vertical FK → zone FK (keeps db column 'vertical_id')
- zone FK → hub FK (keeps db column 'zone_id')

All operations are state-only because comms_broadcasts already has both
vertical_id and zone_id columns which don't need renaming.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("comms", "0001_initial"),
        ("core", "0002_rename_hierarchy"),
    ]

    operations = [
        # Rename fields in Django state only.
        # Rename 'zone' → 'hub' FIRST to free the name.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    model_name="Broadcast",
                    old_name="zone",
                    new_name="hub",
                ),
            ],
            database_operations=[],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    model_name="Broadcast",
                    old_name="vertical",
                    new_name="zone",
                ),
            ],
            database_operations=[],
        ),

        # Set db_column and update FK targets — state-only.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="Broadcast",
                    name="zone",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="broadcasts",
                        to="core.zone",
                        help_text="Scope to entire zone",
                        db_column="vertical_id",
                    ),
                ),
                migrations.AlterField(
                    model_name="Broadcast",
                    name="hub",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="broadcasts",
                        to="core.hub",
                        help_text="Scope to single hub",
                        db_column="zone_id",
                    ),
                ),
            ],
            database_operations=[],
        ),

        # Update template body help_text (no column change)
        migrations.AlterField(
            model_name="MessageTemplate",
            name="body",
            field=models.TextField(help_text="Supports {name}, {orders}, {hub}, {captain} tokens"),
        ),
    ]
