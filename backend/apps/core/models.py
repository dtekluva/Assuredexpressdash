"""
Core operational models for Assured Express Logistics.
All financial figures are in Nigerian Naira (₦).

REDUNDANCY NOTE (OCC ↔ AXpress Integration)
============================================
The following models are NOW REDUNDANT for read operations because the main
AXpress backend owns this data and the OCC consumes it via API calls
(see axpress_client.py):

  - Zone (AXpress: Vertical)  → main backend: dispatcher.Vertical
  - Hub  (AXpress: Zone)      → main backend: dispatcher.Zone
  - Rider                     → main backend: dispatcher.Rider + riders app
  - Merchant                  → main backend: dispatcher.Merchant
  - RiderSnapshot             → main backend: RiderDailySnapshot (Celery-aggregated)
  - MerchantSnapshot          → main backend: MerchantDailySnapshot (Celery-aggregated)
  - Order                     → main backend: orders.Order

NAMING NOTE: The business uses "Zone" (was Vertical) and "Relay Hub" (was Zone).
The AXpress API still uses the old names (verticals, zones). This OCC backend
uses the NEW business terminology in code while translating to old API names
in axpress_client.py.

These models are kept temporarily so that:
  1. Existing migrations don't break.
  2. The seed_data management command still works for local dev/demo.
  3. The comms app can still FK to Rider/Merchant for broadcast recipients.

MIGRATION PATH: Once the comms app is updated to reference riders/merchants
by their main-backend IDs (stored as CharField/UUIDField) instead of local
FKs, these models can be dropped entirely.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


# ── Reference / Config ────────────────────────────────────────────────────────

class Zone(models.Model):
    """One of the regional zones (was 'Vertical'), managed by a Zone Lead."""
    name      = models.CharField(max_length=100)
    full_name = models.CharField(max_length=200)
    color_hex = models.CharField(max_length=7, default="#3B82F6")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Compensation
    base_pay      = models.PositiveIntegerField(default=250_000, help_text="Monthly base ₦")
    transport_pay = models.PositiveIntegerField(default=80_000,  help_text="Monthly transport ₦")
    commission_rate = models.DecimalField(max_digits=5, decimal_places=4, default="0.0110")

    class Meta:
        ordering = ["name"]
        db_table = "core_verticals"

    def __str__(self):
        return self.full_name


class Hub(models.Model):
    """A relay hub (was 'Zone') within a zone, managed by a Hub Captain."""
    zone       = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="hubs")
    name       = models.CharField(max_length=100)
    slug       = models.SlugField(unique=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Compensation
    base_pay        = models.PositiveIntegerField(default=50_000)
    transport_pay   = models.PositiveIntegerField(default=40_000)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=4, default="0.0400")

    # Targets (monthly)
    order_target   = models.PositiveIntegerField(default=2000)
    revenue_target = models.PositiveBigIntegerField(default=3_000_000)

    class Meta:
        ordering = ["zone", "name"]
        db_table = "core_zones"

    def __str__(self):
        return f"{self.zone.name} — {self.name}"


# ── Operational Entities ──────────────────────────────────────────────────────

class Rider(models.Model):
    """A delivery rider assigned to a hub."""
    class Status(models.TextChoices):
        ACTIVE   = "active",   "Active"
        INACTIVE = "inactive", "Inactive"
        SUSPENDED = "suspended", "Suspended"

    hub        = models.ForeignKey(Hub, on_delete=models.PROTECT, related_name="riders")
    first_name = models.CharField(max_length=100)
    last_name  = models.CharField(max_length=100)
    phone      = models.CharField(max_length=20, unique=True)
    email      = models.EmailField(blank=True)
    status     = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    joined_at  = models.DateField()
    bike_plate = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering  = ["hub", "last_name", "first_name"]
        db_table  = "core_riders"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.hub.name})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Merchant(models.Model):
    """A business onboarded onto the Assured Express delivery platform."""
    class Status(models.TextChoices):
        ACTIVE   = "active",   "Active"
        WATCH    = "watch",    "Watch"
        INACTIVE = "inactive", "Inactive"
        CHURNED  = "churned",  "Churned"

    hub          = models.ForeignKey(Hub, on_delete=models.PROTECT, related_name="merchants")
    business_name = models.CharField(max_length=200)
    business_type = models.CharField(max_length=100)
    owner_name   = models.CharField(max_length=200)
    phone        = models.CharField(max_length=20)
    whatsapp     = models.CharField(max_length=20, blank=True)
    email        = models.EmailField(blank=True)
    address      = models.TextField(blank=True)
    status       = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    onboarded_at = models.DateField()
    last_order_at = models.DateTimeField(null=True, blank=True)
    cac_number   = models.CharField(max_length=50, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering  = ["hub", "business_name"]
        db_table  = "core_merchants"

    def __str__(self):
        return f"{self.business_name} ({self.hub.name})"


# ── Performance Data ──────────────────────────────────────────────────────────

class RiderSnapshot(models.Model):
    """
    Daily performance record for a rider.
    Aggregated from order data for dashboard metrics.
    """
    rider        = models.ForeignKey(Rider, on_delete=models.CASCADE, related_name="snapshots")
    date         = models.DateField()

    orders_completed = models.PositiveIntegerField(default=0)
    orders_rejected  = models.PositiveIntegerField(default=0)
    orders_failed    = models.PositiveIntegerField(default=0)
    km_covered       = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    revenue_generated = models.PositiveBigIntegerField(default=0)

    # Quality metrics
    online_minutes   = models.PositiveIntegerField(default=0)
    peak_orders      = models.PositiveIntegerField(default=0, help_text="Orders during peak hours")
    avg_delivery_mins = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    csat_sum         = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    csat_count       = models.PositiveIntegerField(default=0)

    # Anomaly flags (computed nightly)
    ghost_minutes    = models.PositiveIntegerField(default=0,
        help_text="Minutes GPS active while rider status is offline")
    has_ghost_flag   = models.BooleanField(default=False)

    class Meta:
        unique_together = [("rider", "date")]
        ordering = ["-date"]
        db_table = "core_rider_snapshots"
        indexes  = [
            models.Index(fields=["rider", "date"]),
            models.Index(fields=["date"]),
        ]

    @property
    def acceptance_rate(self):
        total = self.orders_completed + self.orders_rejected
        return round((self.orders_completed / total) * 100, 1) if total else 0

    @property
    def csat_avg(self):
        return round(self.csat_sum / self.csat_count, 2) if self.csat_count else None

    @property
    def revenue_per_km(self):
        return round(self.revenue_generated / float(self.km_covered)) if self.km_covered else 0


class MerchantSnapshot(models.Model):
    """Daily performance record for a merchant."""
    merchant     = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="snapshots")
    date         = models.DateField()

    orders_placed     = models.PositiveIntegerField(default=0)
    orders_fulfilled  = models.PositiveIntegerField(default=0)
    orders_returned   = models.PositiveIntegerField(default=0)
    gross_revenue     = models.PositiveBigIntegerField(default=0)
    avg_order_value   = models.PositiveBigIntegerField(default=0)

    class Meta:
        unique_together = [("merchant", "date")]
        ordering = ["-date"]
        db_table = "core_merchant_snapshots"
        indexes  = [
            models.Index(fields=["merchant", "date"]),
            models.Index(fields=["date"]),
        ]

    @property
    def fulfillment_rate(self):
        return round((self.orders_fulfilled / self.orders_placed) * 100, 1) if self.orders_placed else 0


class Order(models.Model):
    """Individual delivery order (source of truth for all snapshots)."""
    class Status(models.TextChoices):
        PENDING    = "pending",    "Pending"
        ASSIGNED   = "assigned",   "Assigned to Rider"
        PICKED_UP  = "picked_up",  "Picked Up"
        DELIVERED  = "delivered",  "Delivered"
        FAILED     = "failed",     "Failed"
        RETURNED   = "returned",   "Returned"
        CANCELLED  = "cancelled",  "Cancelled"

    reference    = models.CharField(max_length=50, unique=True)
    merchant     = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="orders")
    rider        = models.ForeignKey(Rider, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    hub          = models.ForeignKey(Hub, on_delete=models.PROTECT, related_name="orders")
    status       = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    pickup_address   = models.TextField()
    delivery_address = models.TextField()
    delivery_fee     = models.PositiveIntegerField(default=0)
    order_value      = models.PositiveIntegerField(default=0, help_text="Value of goods")
    km_distance      = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    created_at   = models.DateTimeField(auto_now_add=True)
    assigned_at  = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    csat_score   = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    rejection_reason = models.CharField(max_length=200, blank=True)
    failure_reason   = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "core_orders"
        indexes  = [
            models.Index(fields=["rider", "status"]),
            models.Index(fields=["merchant", "status"]),
            models.Index(fields=["hub", "created_at"]),
        ]

    def __str__(self):
        return f"Order {self.reference} — {self.status}"

    @property
    def delivery_minutes(self):
        if self.delivered_at and self.picked_up_at:
            return round((self.delivered_at - self.picked_up_at).seconds / 60, 1)
        return None
