from django.contrib import admin
from .models import Vertical, Zone, Rider, Merchant, RiderSnapshot, MerchantSnapshot, Order


@admin.register(Vertical)
class VerticalAdmin(admin.ModelAdmin):
    list_display = ["name", "full_name", "is_active"]
    list_filter  = ["is_active"]


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display  = ["name", "vertical", "order_target", "revenue_target", "is_active"]
    list_filter   = ["vertical", "is_active"]
    search_fields = ["name", "slug"]


@admin.register(Rider)
class RiderAdmin(admin.ModelAdmin):
    list_display  = ["full_name", "zone", "phone", "status", "joined_at"]
    list_filter   = ["zone__vertical", "zone", "status"]
    search_fields = ["first_name", "last_name", "phone"]


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display  = ["business_name", "business_type", "zone", "status", "onboarded_at"]
    list_filter   = ["zone__vertical", "zone", "status", "business_type"]
    search_fields = ["business_name", "owner_name", "phone"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display  = ["reference", "merchant", "rider", "zone", "status", "created_at"]
    list_filter   = ["status", "zone__vertical", "zone"]
    search_fields = ["reference", "merchant__business_name", "rider__first_name"]
    date_hierarchy = "created_at"
    raw_id_fields = ["merchant", "rider", "zone"]


@admin.register(RiderSnapshot)
class RiderSnapshotAdmin(admin.ModelAdmin):
    list_display  = ["rider", "date", "orders_completed", "revenue_generated", "has_ghost_flag"]
    list_filter   = ["has_ghost_flag", "rider__zone__vertical"]
    date_hierarchy = "date"


@admin.register(MerchantSnapshot)
class MerchantSnapshotAdmin(admin.ModelAdmin):
    list_display  = ["merchant", "date", "orders_placed", "orders_fulfilled", "gross_revenue"]
    date_hierarchy = "date"
