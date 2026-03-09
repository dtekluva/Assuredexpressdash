"""
Django-filter FilterSet classes for all core QuerySets.
These power the ?filter= parameters on list endpoints.
"""
import django_filters
from django.utils import timezone
from datetime import timedelta
from .models import Rider, Merchant, Order, RiderSnapshot


class RiderFilter(django_filters.FilterSet):
    zone        = django_filters.NumberFilter(field_name="zone")
    vertical    = django_filters.NumberFilter(field_name="zone__vertical")
    status      = django_filters.CharFilter(field_name="status")
    joined_after  = django_filters.DateFilter(field_name="joined_at", lookup_expr="gte")
    joined_before = django_filters.DateFilter(field_name="joined_at", lookup_expr="lte")

    class Meta:
        model  = Rider
        fields = ["zone", "vertical", "status"]


class MerchantFilter(django_filters.FilterSet):
    zone          = django_filters.NumberFilter(field_name="zone")
    vertical      = django_filters.NumberFilter(field_name="zone__vertical")
    status        = django_filters.CharFilter(field_name="status")
    business_type = django_filters.CharFilter(field_name="business_type", lookup_expr="icontains")
    onboarded_after  = django_filters.DateFilter(field_name="onboarded_at", lookup_expr="gte")
    onboarded_before = django_filters.DateFilter(field_name="onboarded_at", lookup_expr="lte")
    inactive_days = django_filters.NumberFilter(method="filter_inactive_days",
                                                 label="Days since last order (≥ N)")

    class Meta:
        model  = Merchant
        fields = ["zone", "vertical", "status", "business_type"]

    def filter_inactive_days(self, queryset, name, value):
        cutoff = timezone.now() - timedelta(days=int(value))
        return queryset.filter(last_order_at__lt=cutoff) | queryset.filter(last_order_at__isnull=True)


class OrderFilter(django_filters.FilterSet):
    zone      = django_filters.NumberFilter(field_name="zone")
    rider     = django_filters.NumberFilter(field_name="rider")
    merchant  = django_filters.NumberFilter(field_name="merchant")
    vertical  = django_filters.NumberFilter(field_name="zone__vertical")
    status    = django_filters.MultipleChoiceFilter(
        choices=Order.Status.choices,
        field_name="status",
    )
    date_from = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    date_to   = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model  = Order
        fields = ["zone", "rider", "merchant", "status"]


class RiderSnapshotFilter(django_filters.FilterSet):
    rider     = django_filters.NumberFilter(field_name="rider")
    zone      = django_filters.NumberFilter(field_name="rider__zone")
    vertical  = django_filters.NumberFilter(field_name="rider__zone__vertical")
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to   = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    ghost_only = django_filters.BooleanFilter(field_name="has_ghost_flag")

    class Meta:
        model  = RiderSnapshot
        fields = ["rider", "zone", "vertical", "has_ghost_flag"]
