"""
Rename user fields and roles for new business terminology.
- vertical FK → zone FK (keeps db column 'vertical_id')
- zone FK → hub FK (keeps db column 'zone_id')
- Role values: vertical_lead → zone_lead, zone_captain → hub_captain

All field renames and AlterFields are state-only because auth_users already
has both vertical_id and zone_id columns which don't need renaming.
"""
from django.db import migrations, models
import django.db.models.deletion


def rename_roles_forward(apps, schema_editor):
    User = apps.get_model("authentication", "User")
    User.objects.filter(role="vertical_lead").update(role="zone_lead")
    User.objects.filter(role="zone_captain").update(role="hub_captain")


def rename_roles_backward(apps, schema_editor):
    User = apps.get_model("authentication", "User")
    User.objects.filter(role="zone_lead").update(role="vertical_lead")
    User.objects.filter(role="hub_captain").update(role="zone_captain")


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
        ("core", "0002_rename_hierarchy"),
    ]

    operations = [
        # Rename fields in Django state only — DB columns stay the same.
        # Rename 'zone' → 'hub' FIRST to free the name 'zone'.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    model_name="User",
                    old_name="zone",
                    new_name="hub",
                ),
            ],
            database_operations=[],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    model_name="User",
                    old_name="vertical",
                    new_name="zone",
                ),
            ],
            database_operations=[],
        ),

        # Update role choices (no column change, just validation)
        migrations.AlterField(
            model_name="User",
            name="role",
            field=models.CharField(
                choices=[
                    ("super_admin", "Super Admin"),
                    ("zone_lead", "Zone Lead"),
                    ("hub_captain", "Hub Captain"),
                    ("ops_analyst", "Ops Analyst"),
                    ("rider", "Rider"),
                ],
                default="ops_analyst",
                max_length=30,
            ),
        ),

        # Data migration for existing role values
        migrations.RunPython(rename_roles_forward, rename_roles_backward),

        # Set db_column and update FK targets — state-only since columns
        # are already named correctly in the DB.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="User",
                    name="zone",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lead_users",
                        to="core.zone",
                        help_text="Set for zone_lead role",
                        db_column="vertical_id",
                    ),
                ),
                migrations.AlterField(
                    model_name="User",
                    name="hub",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="captain_users",
                        to="core.hub",
                        help_text="Set for hub_captain role",
                        db_column="zone_id",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
