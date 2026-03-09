"""
Celery tasks for the core app.

Nightly aggregation: runs after midnight Africa/Lagos to compute RiderSnapshot
and MerchantSnapshot records from raw Order data.

Schedule these via Celery Beat (django_celery_beat) in the admin:
  - aggregate_daily_rider_snapshots  → every day at 01:00
  - aggregate_daily_merchant_snapshots → every day at 01:15
  - flag_ghost_riders                → every day at 01:30
  - push_zone_leaderboard_update     → every 15 minutes (daytime)
"""
import logging
from datetime import date, timedelta
from celery import shared_task
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

logger = logging.getLogger("apps.core")


# ── Nightly Rider Snapshot Aggregation ───────────────────────────────────────

@shared_task
def aggregate_daily_rider_snapshots(target_date: str = None):
    """
    Aggregate all completed orders for each rider on target_date
    and upsert a RiderSnapshot record.

    target_date: ISO date string (e.g. "2025-06-15"). Defaults to yesterday.
    """
    from .models import Rider, Order, RiderSnapshot

    snap_date = date.fromisoformat(target_date) if target_date else date.today() - timedelta(days=1)
    logger.info("Aggregating rider snapshots for %s", snap_date)

    riders = Rider.objects.filter(status="active").select_related("zone")
    created_count = updated_count = 0

    for rider in riders:
        day_orders = Order.objects.filter(
            rider=rider,
            created_at__date=snap_date,
        )

        completed = day_orders.filter(status=Order.Status.DELIVERED)
        rejected  = day_orders.filter(status__in=[Order.Status.CANCELLED]).count()
        failed    = day_orders.filter(status=Order.Status.FAILED).count()

        agg = completed.aggregate(
            revenue      = Coalesce(Sum("delivery_fee"), 0),
            km           = Coalesce(Sum("km_distance"), 0),
            csat_sum     = Coalesce(Sum("csat_score"), 0),
            csat_count   = Count("id", filter=Q(csat_score__isnull=False)),
        )

        # Peak hours: 08:00–11:00 and 17:00–20:00
        peak_orders = completed.filter(
            Q(created_at__hour__gte=8, created_at__hour__lt=11) |
            Q(created_at__hour__gte=17, created_at__hour__lt=20)
        ).count()

        # Avg delivery time (seconds → minutes)
        delivered_pairs = completed.exclude(
            picked_up_at=None
        ).exclude(
            delivered_at=None
        ).values_list("picked_up_at", "delivered_at")

        avg_mins = None
        if delivered_pairs.exists():
            total_secs = sum((d - p).total_seconds() for p, d in delivered_pairs)
            avg_mins = round(total_secs / len(delivered_pairs) / 60, 2)

        snap, created = RiderSnapshot.objects.update_or_create(
            rider=rider,
            date=snap_date,
            defaults={
                "orders_completed":  completed.count(),
                "orders_rejected":   rejected,
                "orders_failed":     failed,
                "km_covered":        agg["km"],
                "revenue_generated": agg["revenue"],
                "peak_orders":       peak_orders,
                "avg_delivery_mins": avg_mins,
                "csat_sum":          float(agg["csat_sum"] or 0),
                "csat_count":        agg["csat_count"],
            }
        )
        if created:
            created_count += 1
        else:
            updated_count += 1

    logger.info("Rider snapshots for %s: %d created, %d updated", snap_date, created_count, updated_count)
    return {"date": str(snap_date), "created": created_count, "updated": updated_count}


# ── Nightly Merchant Snapshot Aggregation ────────────────────────────────────

@shared_task
def aggregate_daily_merchant_snapshots(target_date: str = None):
    """
    Aggregate order metrics per merchant for target_date and upsert MerchantSnapshot.
    """
    from .models import Merchant, Order, MerchantSnapshot

    snap_date = date.fromisoformat(target_date) if target_date else date.today() - timedelta(days=1)
    logger.info("Aggregating merchant snapshots for %s", snap_date)

    merchants = Merchant.objects.all().select_related("zone")
    created_count = updated_count = 0

    for merchant in merchants:
        day_orders = Order.objects.filter(merchant=merchant, created_at__date=snap_date)
        total     = day_orders.count()
        fulfilled = day_orders.filter(status=Order.Status.DELIVERED).count()
        returned  = day_orders.filter(status=Order.Status.RETURNED).count()
        revenue   = day_orders.filter(status=Order.Status.DELIVERED).aggregate(
            total=Coalesce(Sum("order_value"), 0)
        )["total"]
        avg_val   = round(revenue / fulfilled) if fulfilled > 0 else 0

        snap, created = MerchantSnapshot.objects.update_or_create(
            merchant=merchant,
            date=snap_date,
            defaults={
                "orders_placed":    total,
                "orders_fulfilled": fulfilled,
                "orders_returned":  returned,
                "gross_revenue":    revenue,
                "avg_order_value":  avg_val,
            }
        )
        if created:
            created_count += 1
        else:
            updated_count += 1

    logger.info("Merchant snapshots for %s: %d created, %d updated", snap_date, created_count, updated_count)
    return {"date": str(snap_date), "created": created_count, "updated": updated_count}


# ── Ghost Rider Flagging ──────────────────────────────────────────────────────

@shared_task
def flag_ghost_riders(target_date: str = None):
    """
    Set has_ghost_flag=True on snapshots where ghost_minutes > threshold.
    Ghost rides = GPS movement while rider is marked offline.
    This task reads from telematics data — stub implementation marks random ones.
    Replace with real GPS vs. status reconciliation from your telematics feed.
    """
    from .models import RiderSnapshot

    snap_date = date.fromisoformat(target_date) if target_date else date.today() - timedelta(days=1)
    flagged = RiderSnapshot.objects.filter(date=snap_date, ghost_minutes__gt=30).update(has_ghost_flag=True)
    logger.info("Ghost flag: %d snapshots flagged for %s", flagged, snap_date)
    return {"date": str(snap_date), "flagged": flagged}


# ── Merchant Status Refresh ───────────────────────────────────────────────────

@shared_task
def refresh_merchant_status():
    """
    Recategorise merchants as active/watch/inactive based on last 30 days' orders.
    Runs nightly to keep status fresh for the dashboard.
    """
    from .models import Merchant, MerchantSnapshot
    from django.db.models import Sum

    cutoff = date.today() - timedelta(days=30)
    updated = 0

    for merchant in Merchant.objects.exclude(status="churned"):
        orders_30d = MerchantSnapshot.objects.filter(
            merchant=merchant,
            date__gte=cutoff,
        ).aggregate(total=Coalesce(Sum("orders_placed"), 0))["total"]

        new_status = (
            "active"   if orders_30d >= 3  else
            "watch"    if orders_30d >= 1  else
            "inactive"
        )
        if new_status != merchant.status:
            merchant.status = new_status
            merchant.save(update_fields=["status"])
            updated += 1

    logger.info("Merchant status refresh: %d merchants updated", updated)
    return {"updated": updated}


# ── Live Zone Leaderboard Push ────────────────────────────────────────────────

@shared_task
def push_zone_leaderboard_update():
    """
    Push live zone KPI update to the WebSocket 'dashboard' group.
    Run every 15 minutes during business hours (07:00–22:00 WAT).
    """
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    from .models import Zone, RiderSnapshot
    from .serializers import get_date_range

    now = timezone.localtime()
    if not (7 <= now.hour <= 22):
        return "Outside business hours, skipping"

    start, end = get_date_range("today")
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("No channel layer configured — skipping WS push")
        return "No channel layer"

    payload = {
        "type": "summary",
        "timestamp": now.isoformat(),
        "zones": [],
    }

    for zone in Zone.objects.filter(is_active=True):
        agg = RiderSnapshot.objects.filter(
            rider__zone=zone, date__range=[start, end]
        ).aggregate(
            orders  = Coalesce(Sum("orders_completed"), 0),
            revenue = Coalesce(Sum("revenue_generated"), 0),
        )
        pct = round((agg["orders"] / (zone.order_target or 1)) * 100)
        payload["zones"].append({"zone_id": zone.id, "orders": agg["orders"], "pct": pct})

    async_to_sync(channel_layer.group_send)(
        "dashboard",
        {"type": "dashboard_update", "payload": payload},
    )

    logger.info("Pushed leaderboard update to dashboard group: %d zones", len(payload["zones"]))
    return {"zones_pushed": len(payload["zones"])}


# ── Run All Nightly Tasks in Sequence ────────────────────────────────────────

@shared_task
def run_nightly_aggregation():
    """
    Convenience task: triggers the full nightly pipeline.
    Schedule this at 01:00 Africa/Lagos instead of individual tasks.
    """
    aggregate_daily_rider_snapshots.delay()
    aggregate_daily_merchant_snapshots.delay()
    flag_ghost_riders.delay()
    refresh_merchant_status.delay()
    logger.info("Nightly aggregation pipeline triggered")
    return "Pipeline dispatched"
