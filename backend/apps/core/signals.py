from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Order, Merchant


@receiver(post_save, sender=Order)
def update_merchant_last_order(sender, instance, created, **kwargs):
    """Keep Merchant.last_order_at fresh every time an order is delivered."""
    if instance.status == Order.Status.DELIVERED and instance.merchant_id:
        Merchant.objects.filter(id=instance.merchant_id).update(
            last_order_at=instance.delivered_at or timezone.now()
        )
