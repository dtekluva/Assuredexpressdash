"""
Celery tasks for dispatching broadcast messages asynchronously.
Each recipient gets its own task so a single failure doesn't block others.
"""
from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger("apps.comms")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def dispatch_broadcast(self, broadcast_id: int):
    """
    Main task: resolve recipients, create BroadcastDelivery rows,
    then fan out to per-recipient subtasks.
    """
    from .models import Broadcast, BroadcastDelivery
    from apps.core.models import Merchant, Rider

    try:
        broadcast = Broadcast.objects.select_related("zone", "vertical").get(id=broadcast_id)
    except Broadcast.DoesNotExist:
        logger.error("Broadcast %s not found", broadcast_id)
        return

    broadcast.status = Broadcast.Status.SENDING
    broadcast.save(update_fields=["status"])

    # Resolve recipients
    if broadcast.audience == "merchant":
        qs = Merchant.objects.all()
        if broadcast.zone_id:
            qs = qs.filter(zone_id=broadcast.zone_id)
        elif broadcast.vertical_id:
            qs = qs.filter(zone__vertical_id=broadcast.vertical_id)

        flt = broadcast.recipient_filter
        if flt == "active":
            qs = qs.filter(status="active")
        elif flt == "watch":
            qs = qs.filter(status="watch")
        elif flt == "inactive":
            qs = qs.filter(status="inactive")

        for merchant in qs:
            for channel in broadcast.channels:
                delivery = BroadcastDelivery.objects.create(
                    broadcast=broadcast,
                    merchant=merchant,
                    channel=channel,
                )
                send_to_merchant.delay(delivery.id)

    else:  # rider
        qs = Rider.objects.select_related("user_account").filter(status="active")
        if broadcast.zone_id:
            qs = qs.filter(zone_id=broadcast.zone_id)
        elif broadcast.vertical_id:
            qs = qs.filter(zone__vertical_id=broadcast.vertical_id)

        flt = broadcast.recipient_filter
        if flt == "critical":
            # Can't filter by pct directly without snapshot join; fetch all and filter
            pass  # Advanced: add annotation in future
        elif flt == "flagged":
            qs = qs.filter(snapshots__has_ghost_flag=True).distinct()

        for rider in qs:
            delivery = BroadcastDelivery.objects.create(
                broadcast=broadcast,
                rider=rider,
                channel="inapp",
            )
            send_to_rider.delay(delivery.id)

    broadcast.status = Broadcast.Status.SENT
    broadcast.sent_at = timezone.now()
    broadcast.save(update_fields=["status", "sent_at"])
    logger.info("Broadcast %s dispatched", broadcast_id)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_to_merchant(self, delivery_id: int):
    from .models import BroadcastDelivery
    from .services import deliver_to_merchant

    try:
        delivery = BroadcastDelivery.objects.select_related(
            "broadcast", "merchant__zone"
        ).get(id=delivery_id)
        deliver_to_merchant(
            delivery,
            delivery.merchant,
            delivery.broadcast.body,
            delivery.broadcast.subject,
        )
    except Exception as exc:
        logger.exception("Failed to send delivery %s: %s", delivery_id, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_to_rider(self, delivery_id: int):
    from .models import BroadcastDelivery
    from .services import deliver_to_rider

    try:
        delivery = BroadcastDelivery.objects.select_related(
            "broadcast", "rider__zone", "rider__user_account"
        ).get(id=delivery_id)
        deliver_to_rider(
            delivery,
            delivery.rider,
            delivery.broadcast.body,
            delivery.broadcast.subject or "Message from Assured Express",
            delivery.broadcast.priority,
        )
    except Exception as exc:
        logger.exception("Failed to send rider delivery %s: %s", delivery_id, exc)
        raise self.retry(exc=exc)
