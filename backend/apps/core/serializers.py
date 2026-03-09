from rest_framework import serializers
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import Vertical, Zone, Rider, Merchant, RiderSnapshot, MerchantSnapshot, Order


# ── Helpers ─────────────────────────────────────────────────────────────────

def get_date_range(period: str, custom_month: int | None = None):
    """Translate period string into (start_date, end_date) for QuerySet filtering."""
    today = timezone.localdate()
    if period == "today":
        return today, today
    if period == "yesterday":
        d = today - timedelta(days=1)
        return d, d
    if period == "this_week":
        start = today - timedelta(days=today.weekday())
        return start, today
    if period == "past_7":
        return today - timedelta(days=6), today
    if period == "this_month":
        return today.replace(day=1), today
    if period == "last_month":
        first_this = today.replace(day=1)
        last_prev  = first_this - timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    if period == "this_year":
        return today.replace(month=1, day=1), today
    if period == "custom_month" and custom_month is not None:
        m = int(custom_month)
        start = today.replace(month=m+1, day=1)
        if m+1 == 12:
            end = today.replace(month=12, day=31)
        else:
            end = today.replace(month=m+2, day=1) - timedelta(days=1)
        return start, end
    # default: this month
    return today.replace(day=1), today


# ── Rider ────────────────────────────────────────────────────────────────────

class RiderListSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source="zone.name", read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model  = Rider
        fields = ["id", "full_name", "first_name", "last_name", "phone", "zone", "zone_name", "status", "joined_at"]

    def get_full_name(self, obj):
        return obj.full_name


class RiderPerformanceSerializer(serializers.ModelSerializer):
    """Rider with aggregated metrics for a given date range."""
    full_name        = serializers.CharField()
    zone_name        = serializers.CharField()
    orders_completed = serializers.IntegerField()
    orders_rejected  = serializers.IntegerField()
    orders_failed    = serializers.IntegerField()
    revenue          = serializers.IntegerField()
    km_covered       = serializers.FloatField()
    online_days      = serializers.IntegerField()
    avg_delivery_mins = serializers.FloatField(allow_null=True)
    csat_avg         = serializers.FloatField(allow_null=True)
    ghost_minutes    = serializers.IntegerField()
    peak_orders      = serializers.IntegerField()
    pct              = serializers.IntegerField()
    flags            = serializers.ListField(child=serializers.DictField())

    class Meta:
        model  = Rider
        fields = [
            "id", "full_name", "zone_name", "status",
            "orders_completed", "orders_rejected", "orders_failed",
            "revenue", "km_covered", "online_days",
            "avg_delivery_mins", "csat_avg", "ghost_minutes", "peak_orders",
            "pct", "flags",
        ]


class RiderDetailSerializer(serializers.ModelSerializer):
    zone_name    = serializers.CharField(source="zone.name",    read_only=True)
    vertical_name = serializers.CharField(source="zone.vertical.name", read_only=True)
    full_name    = serializers.SerializerMethodField()

    class Meta:
        model  = Rider
        fields = ["id", "full_name", "first_name", "last_name", "phone", "email",
                  "zone", "zone_name", "vertical_name", "status", "joined_at", "bike_plate",
                  "created_at", "updated_at"]

    def get_full_name(self, obj):
        return obj.full_name


# ── Merchant ─────────────────────────────────────────────────────────────────

class MerchantListSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source="zone.name", read_only=True)

    class Meta:
        model  = Merchant
        fields = ["id", "business_name", "business_type", "owner_name",
                  "phone", "zone", "zone_name", "status", "onboarded_at", "last_order_at"]


class MerchantDetailSerializer(serializers.ModelSerializer):
    zone_name     = serializers.CharField(source="zone.name",            read_only=True)
    vertical_name = serializers.CharField(source="zone.vertical.name",   read_only=True)

    class Meta:
        model  = Merchant
        fields = "__all__"


class MerchantPerformanceSerializer(serializers.ModelSerializer):
    zone_name         = serializers.CharField()
    orders_placed     = serializers.IntegerField()
    orders_fulfilled  = serializers.IntegerField()
    orders_returned   = serializers.IntegerField()
    gross_revenue     = serializers.IntegerField()
    avg_order_value   = serializers.IntegerField()
    fulfillment_rate  = serializers.FloatField()
    days_since_order  = serializers.IntegerField(allow_null=True)

    class Meta:
        model  = Merchant
        fields = [
            "id", "business_name", "business_type", "zone_name", "status",
            "orders_placed", "orders_fulfilled", "orders_returned", "gross_revenue",
            "avg_order_value", "fulfillment_rate", "days_since_order",
        ]


# ── Zone ─────────────────────────────────────────────────────────────────────

class ZoneSerializer(serializers.ModelSerializer):
    vertical_name = serializers.CharField(source="vertical.name", read_only=True)
    rider_count   = serializers.SerializerMethodField()
    merchant_count = serializers.SerializerMethodField()

    class Meta:
        model  = Zone
        fields = ["id", "name", "slug", "vertical", "vertical_name",
                  "is_active", "order_target", "revenue_target",
                  "rider_count", "merchant_count",
                  "base_pay", "transport_pay", "commission_rate"]

    def get_rider_count(self, obj):
        return obj.riders.filter(status="active").count()

    def get_merchant_count(self, obj):
        return obj.merchants.filter(status__in=["active","watch"]).count()


# ── Vertical ─────────────────────────────────────────────────────────────────

class VerticalSerializer(serializers.ModelSerializer):
    zone_count = serializers.IntegerField(source="zones.count", read_only=True)

    class Meta:
        model  = Vertical
        fields = ["id", "name", "full_name", "color_hex", "is_active", "zone_count",
                  "base_pay", "transport_pay", "commission_rate"]


# ── Orders ────────────────────────────────────────────────────────────────────

class OrderSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.business_name", read_only=True)
    rider_name    = serializers.SerializerMethodField()
    zone_name     = serializers.CharField(source="zone.name", read_only=True)

    class Meta:
        model  = Order
        fields = ["id", "reference", "status", "merchant", "merchant_name",
                  "rider", "rider_name", "zone", "zone_name",
                  "pickup_address", "delivery_address", "delivery_fee", "order_value",
                  "km_distance", "csat_score", "rejection_reason", "failure_reason",
                  "created_at", "assigned_at", "picked_up_at", "delivered_at"]

    def get_rider_name(self, obj):
        return obj.rider.full_name if obj.rider else None


class OrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Order
        fields = ["reference", "merchant", "zone", "pickup_address", "delivery_address",
                  "delivery_fee", "order_value"]


class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Order
        fields = ["status", "rider", "rejection_reason", "failure_reason", "csat_score",
                  "picked_up_at", "delivered_at"]
