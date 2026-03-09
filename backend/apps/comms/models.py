"""
Communication models — merchant multi-channel outreach and rider in-app notifications.
"""
from django.db import models
from django.contrib.postgres.fields import ArrayField


class MessageTemplate(models.Model):
    """Reusable message templates, grouped by type and audience."""
    class Audience(models.TextChoices):
        MERCHANT = "merchant", "Merchant"
        RIDER    = "rider",    "Rider"

    class MsgType(models.TextChoices):
        PROMOTION = "promotion", "Promotion"
        REMINDER  = "reminder",  "Reminder"
        DRIP      = "drip",      "Drip"
        SEASONAL  = "seasonal",  "Seasonal"
        PERFORMANCE = "performance", "Performance"
        INCENTIVE   = "incentive",   "Incentive"
        OPERATIONAL = "operational", "Operational"
        GENERAL     = "general",     "General"

    audience    = models.CharField(max_length=20, choices=Audience.choices)
    msg_type    = models.CharField(max_length=30, choices=MsgType.choices)
    label       = models.CharField(max_length=100)
    subject     = models.CharField(max_length=200, blank=True, help_text="Email subject only")
    body        = models.TextField(help_text="Supports {name}, {orders}, {zone}, {captain} tokens")
    is_active   = models.BooleanField(default=True)
    created_by  = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["audience", "msg_type", "label"]
        db_table = "comms_templates"

    def __str__(self):
        return f"[{self.audience}/{self.msg_type}] {self.label}"


class Broadcast(models.Model):
    """
    A single send event — one message to N recipients across one or more channels.
    Tracks send status, opens/reads, and delivery failures.
    """
    class Status(models.TextChoices):
        DRAFT     = "draft",     "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        SENDING   = "sending",   "Sending"
        SENT      = "sent",      "Sent"
        FAILED    = "failed",    "Failed"

    class Audience(models.TextChoices):
        MERCHANT = "merchant", "Merchant"
        RIDER    = "rider",    "Rider"

    class Channel(models.TextChoices):
        SMS      = "sms",      "SMS"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL    = "email",    "Email"
        INAPP    = "inapp",    "In-App (Rider)"

    class Priority(models.TextChoices):
        NORMAL = "normal", "Normal"
        HIGH   = "high",   "High"
        URGENT = "urgent", "Urgent"

    created_by  = models.ForeignKey(
        "authentication.User", on_delete=models.SET_NULL, null=True, related_name="broadcasts"
    )
    # Scope — one of these must be set
    vertical    = models.ForeignKey(
        "core.Vertical", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="broadcasts", help_text="Scope to entire vertical"
    )
    zone        = models.ForeignKey(
        "core.Zone", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="broadcasts", help_text="Scope to single zone"
    )
    audience    = models.CharField(max_length=20, choices=Audience.choices)
    recipient_filter = models.CharField(
        max_length=30, default="all",
        help_text="all | active | watch | inactive | critical | atrisk | flagged"
    )
    channels    = ArrayField(
        models.CharField(max_length=20, choices=Channel.choices),
        default=list, help_text="Merchant: sms/whatsapp/email. Rider: inapp"
    )
    priority    = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    template    = models.ForeignKey(
        MessageTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    subject     = models.CharField(max_length=200, blank=True)
    body        = models.TextField()
    status      = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    scheduled_at  = models.DateTimeField(null=True, blank=True)
    sent_at       = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "comms_broadcasts"

    def __str__(self):
        scope = self.zone or self.vertical
        return f"Broadcast to {self.audience} · {scope} · {self.created_at:%Y-%m-%d}"

    @property
    def total_recipients(self):
        return self.deliveries.count()

    @property
    def open_rate(self):
        total = self.total_recipients
        if not total:
            return 0
        opened = self.deliveries.filter(is_read=True).count()
        return round((opened / total) * 100)


class BroadcastDelivery(models.Model):
    """
    One row per recipient per channel for a Broadcast.
    Tracks per-recipient delivery and read status.
    """
    class DeliveryStatus(models.TextChoices):
        PENDING   = "pending",   "Pending"
        SENT      = "sent",      "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED    = "failed",    "Failed"
        BOUNCED   = "bounced",   "Bounced"

    broadcast   = models.ForeignKey(Broadcast, on_delete=models.CASCADE, related_name="deliveries")
    channel     = models.CharField(max_length=20, choices=Broadcast.Channel.choices)
    status      = models.CharField(max_length=20, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING)
    is_read     = models.BooleanField(default=False)
    read_at     = models.DateTimeField(null=True, blank=True)
    sent_at     = models.DateTimeField(null=True, blank=True)
    error_msg   = models.TextField(blank=True)

    # Recipient — one of these is set
    merchant    = models.ForeignKey(
        "core.Merchant", on_delete=models.CASCADE, null=True, blank=True, related_name="deliveries"
    )
    rider       = models.ForeignKey(
        "core.Rider", on_delete=models.CASCADE, null=True, blank=True, related_name="deliveries"
    )

    class Meta:
        db_table = "comms_deliveries"
        indexes = [
            models.Index(fields=["broadcast", "status"]),
            models.Index(fields=["rider", "is_read"]),
        ]

    def __str__(self):
        recipient = self.merchant or self.rider
        return f"{self.broadcast_id} → {recipient} via {self.channel} [{self.status}]"


class RiderInAppNotification(models.Model):
    """
    A notification that appears in the rider's mobile app.
    Created from a Broadcast delivery or directly.
    """
    class Priority(models.TextChoices):
        NORMAL = "normal", "Normal"
        HIGH   = "high",   "High"
        URGENT = "urgent", "Urgent"

    rider       = models.ForeignKey("core.Rider", on_delete=models.CASCADE, related_name="notifications")
    broadcast   = models.ForeignKey(
        Broadcast, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications"
    )
    title       = models.CharField(max_length=100, blank=True)
    body        = models.TextField()
    priority    = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    is_read     = models.BooleanField(default=False)
    read_at     = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "comms_rider_notifications"
        indexes  = [
            models.Index(fields=["rider", "is_read"]),
        ]

    def __str__(self):
        return f"Notif → Rider {self.rider_id} [{self.priority}] {'READ' if self.is_read else 'UNREAD'}"
