from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Extended user model for Assured Express staff.
    Roles determine what data they can see and what actions they can take.
    """
    class Role(models.TextChoices):
        SUPER_ADMIN    = "super_admin",    "Super Admin"
        ZONE_LEAD      = "zone_lead",      "Zone Lead"
        HUB_CAPTAIN    = "hub_captain",    "Hub Captain"
        OPS_ANALYST    = "ops_analyst",    "Ops Analyst"
        RIDER          = "rider",          "Rider"

    role        = models.CharField(max_length=30, choices=Role.choices, default=Role.OPS_ANALYST)
    phone       = models.CharField(max_length=20, blank=True)
    avatar      = models.ImageField(upload_to="avatars/", blank=True, null=True)
    # Link to operational entity
    zone        = models.ForeignKey(
        "core.Zone", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="lead_users", help_text="Set for zone_lead role",
        db_column="vertical_id",
    )
    hub         = models.ForeignKey(
        "core.Hub", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="captain_users", help_text="Set for hub_captain role",
        db_column="zone_id",
    )
    rider_profile = models.OneToOneField(
        "core.Rider", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="user_account", help_text="Set for rider role"
    )
    firebase_token = models.TextField(blank=True, help_text="FCM push token for riders")
    last_seen   = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "auth_users"
        verbose_name = "User"

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"
