"""
Business logic layer for computing rider and merchant performance metrics.
Separates aggregation from views so the same logic can be used in Celery tasks.
"""
from django.db.models import Sum, Avg, Count, Q, F, Value, DecimalField, FloatField
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import date

from .models import Rider, Merchant, RiderSnapshot, MerchantSnapshot, Order


# ── Constants ─────────────────────────────────────────────────────────────────
MONTHLY_ORDERS_TARGET  = 400
MONTHLY_REVENUE_TARGET = 600_000
WORKING_DAYS_MONTH     = 26
TARGET_ACCEPT_RATE     = 92
TARGET_CSAT            = 4.5
TARGET_DELIVERY_MINS   = 28
TARGET_FAILED_RATE     = 3.0
TARGET_PEAK_UTIL       = 75
TARGET_REV_PER_KM      = 3_333
GHOST_THRESHOLD        = 12  # % ghost-ride ratio triggers flag


def scale_target(base: int, start: date, end: date) -> int:
    """Scale monthly target for the given date range."""
    days = (end - start).days + 1
    return max(1, round(base * days / WORKING_DAYS_MONTH))


def _build_flags(data: dict) -> list:
    """Build anomaly flag list from computed metrics."""
    flags = []
    if data.get("ghost_ratio", 0) > GHOST_THRESHOLD:
        flags.append({"type": "warning", "msg": "High ghost-ride ratio — offline but GPS active"})
    if data.get("acceptance_rate", 100) < 80:
        flags.append({"type": "critical", "msg": "Low acceptance rate — may be cherry-picking orders"})
    if data.get("failed_rate", 0) > 7:
        flags.append({"type": "warning", "msg": "High failed delivery rate — last-mile issues"})
    if data.get("online_days", WORKING_DAYS_MONTH) < 18:
        flags.append({"type": "critical", "msg": "Low active days — attendance needs attention"})
    if data.get("avg_delivery_mins") and data["avg_delivery_mins"] > 42:
        flags.append({"type": "warning", "msg": "Slow delivery times — route optimisation needed"})
    return flags


def compute_rider_metrics(rider: Rider, start: date, end: date, detailed: bool = False) -> dict:
    """
    Aggregate RiderSnapshot records for a rider over [start, end].
    Returns a dict compatible with RiderPerformanceSerializer.
    """
    snaps = RiderSnapshot.objects.filter(rider=rider, date__range=[start, end])

    agg = snaps.aggregate(
        orders_completed  = Coalesce(Sum("orders_completed"),  0),
        orders_rejected   = Coalesce(Sum("orders_rejected"),   0),
        orders_failed     = Coalesce(Sum("orders_failed"),     0),
        revenue           = Coalesce(Sum("revenue_generated"), 0),
        km_covered        = Coalesce(
            Sum("km_covered"),
            Value(0, output_field=DecimalField(max_digits=8, decimal_places=2)),
        ),
        ghost_minutes     = Coalesce(Sum("ghost_minutes"),     0),
        peak_orders       = Coalesce(Sum("peak_orders"),       0),
        csat_sum          = Coalesce(
            Sum("csat_sum"),
            Value(0, output_field=DecimalField(max_digits=8, decimal_places=2)),
        ),
        csat_count        = Coalesce(Sum("csat_count"),        0),
        online_minutes    = Coalesce(Sum("online_minutes"),    0),
        working_days      = Count("id"),
    )

    target_orders   = scale_target(MONTHLY_ORDERS_TARGET, start, end)
    target_revenue  = scale_target(MONTHLY_REVENUE_TARGET, start, end)
    orders          = agg["orders_completed"]
    pct             = round((orders / target_orders) * 100) if target_orders else 0

    # Derived ratios
    total_attempted = orders + agg["orders_rejected"]
    acceptance_rate = round((orders / total_attempted) * 100) if total_attempted else 100
    failed_rate     = round((agg["orders_failed"] / max(orders, 1)) * 100, 1)
    km              = float(agg["km_covered"])
    rev_per_km      = round(agg["revenue"] / km) if km > 0 else 0
    csat_avg        = round(agg["csat_sum"] / agg["csat_count"], 2) if agg["csat_count"] else None
    ghost_ratio     = round((agg["ghost_minutes"] / max(agg["online_minutes"], 1)) * 100, 1)
    peak_util       = round((agg["peak_orders"] / max(orders, 1)) * 100)
    online_days     = agg["working_days"]

    # Avg delivery time from orders table
    avg_mins = None
    if detailed:
        avg_mins_qs = Order.objects.filter(
            rider=rider,
            created_at__date__range=[start, end],
            status="delivered",
            picked_up_at__isnull=False,
            delivered_at__isnull=False,
        ).values_list("picked_up_at", "delivered_at")
        if avg_mins_qs.exists():
            total_secs = sum((d - p).total_seconds() for p, d in avg_mins_qs)
            avg_mins = round(total_secs / len(avg_mins_qs) / 60, 1)

    data = {
        "acceptance_rate":  acceptance_rate,
        "failed_rate":      failed_rate,
        "ghost_ratio":      ghost_ratio,
        "avg_delivery_mins": avg_mins,
        "online_days":      online_days,
    }
    flags = _build_flags(data) if online_days else []

    result = {
        "id":               rider.id,
        "full_name":        rider.full_name,
        "hub_name":         rider.hub.name,
        "status":           rider.status,
        "orders_completed": orders,
        "orders_rejected":  agg["orders_rejected"],
        "orders_failed":    agg["orders_failed"],
        "revenue":          agg["revenue"],
        "km_covered":       km,
        "online_days":      online_days,
        "avg_delivery_mins": avg_mins,
        "csat_avg":         csat_avg,
        "ghost_minutes":    agg["ghost_minutes"],
        "ghost_ratio":      ghost_ratio,
        "peak_orders":      agg["peak_orders"],
        "peak_util":        peak_util,
        "rev_per_km":       rev_per_km,
        "acceptance_rate":  acceptance_rate,
        "failed_rate":      failed_rate,
        "target_orders":    target_orders,
        "target_revenue":   target_revenue,
        "pct":              pct,
        "flags":            flags,
    }

    if detailed:
        # Monthly history (last 5 months)
        result["order_history"]   = _monthly_order_history(rider)
        result["revenue_history"] = _monthly_revenue_history(rider)

    return result


def compute_merchant_metrics(merchant: Merchant, start: date, end: date, detailed: bool = False) -> dict:
    snaps = MerchantSnapshot.objects.filter(merchant=merchant, date__range=[start, end])

    agg = snaps.aggregate(
        orders_placed    = Coalesce(Sum("orders_placed"),    0),
        orders_fulfilled = Coalesce(Sum("orders_fulfilled"), 0),
        orders_returned  = Coalesce(Sum("orders_returned"),  0),
        gross_revenue    = Coalesce(Sum("gross_revenue"),    0),
        avg_order_value  = Coalesce(
            Avg("avg_order_value"),
            Value(0.0, output_field=FloatField()),
        ),
    )

    fulfillment_rate = round((agg["orders_fulfilled"] / max(agg["orders_placed"], 1)) * 100, 1)
    last_order = merchant.last_order_at
    days_since_order = (timezone.now().date() - last_order.date()).days if last_order else None

    result = {
        "id":               merchant.id,
        "business_name":    merchant.business_name,
        "business_type":    merchant.business_type,
        "hub_name":         merchant.hub.name,
        "status":           merchant.status,
        "orders_placed":    agg["orders_placed"],
        "orders_fulfilled": agg["orders_fulfilled"],
        "orders_returned":  agg["orders_returned"],
        "gross_revenue":    agg["gross_revenue"],
        "avg_order_value":  int(agg["avg_order_value"] or 0),
        "fulfillment_rate": fulfillment_rate,
        "days_since_order": days_since_order,
    }

    if detailed:
        result["order_history"] = _monthly_merchant_history(merchant)

    return result


def _monthly_order_history(rider: Rider, months: int = 5) -> list:
    from django.db.models.functions import TruncMonth
    today = timezone.localdate()
    results = (
        RiderSnapshot.objects
        .filter(rider=rider)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(orders=Sum("orders_completed"))
        .order_by("month")
    )
    rows = list(results)
    return [{"month": r["month"].strftime("%b"), "orders": r["orders"]} for r in rows[-months:]]


def _monthly_revenue_history(rider: Rider, months: int = 5) -> list:
    from django.db.models.functions import TruncMonth
    results = (
        RiderSnapshot.objects
        .filter(rider=rider)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(revenue=Sum("revenue_generated"))
        .order_by("month")
    )
    rows = list(results)
    return [{"month": r["month"].strftime("%b"), "revenue": r["revenue"]} for r in rows[-months:]]


def _monthly_merchant_history(merchant: Merchant, months: int = 5) -> list:
    from django.db.models.functions import TruncMonth
    results = (
        MerchantSnapshot.objects
        .filter(merchant=merchant)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(orders=Sum("orders_placed"), revenue=Sum("gross_revenue"))
        .order_by("month")
    )
    rows = list(results)
    return [{"month": r["month"].strftime("%b"), "orders": r["orders"], "revenue": r["revenue"]} for r in rows[-months:]]


def aggregate_hub_summary(hub_id: int, start: date, end: date) -> dict:
    """Used by WebSocket consumers to push live hub updates."""
    from .models import Hub
    hub = Hub.objects.get(id=hub_id)
    snaps = RiderSnapshot.objects.filter(rider__hub=hub, date__range=[start, end])
    agg = snaps.aggregate(
        orders  = Coalesce(Sum("orders_completed"), 0),
        revenue = Coalesce(Sum("revenue_generated"), 0),
    )
    pct = round((agg["orders"] / (hub.order_target or 1)) * 100)
    return {"hub_id": hub_id, "orders": agg["orders"], "revenue": agg["revenue"], "pct": pct}
